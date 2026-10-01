"""Основной метод answer(): сборка ответов от моделей."""
import json
import time
from datetime import datetime

from .base import Ok

__all__ = ["AnswerAgent"]


class AnswerAgent:
    """Миксин: основной метод answer()."""

    def _coerce_temperature(self, value):
        """Приводит значение температуры к float в допустимом диапазоне."""
        try:
            t = float(value)
        except (TypeError, ValueError):
            return None
        from .. import config
        if t < config.TEMP_MIN:
            return float(config.TEMP_MIN)
        if t > config.TEMP_MAX:
            return float(config.TEMP_MAX)
        return t

    def _coerce_max_tokens(self, value):
        """Приводит значение max_tokens к int в допустимом диапазоне."""
        from .. import config
        try:
            v = int(value)
        except (TypeError, ValueError):
            return None
        if v < config.MAX_TOKENS_MIN:
            return int(config.MAX_TOKENS_MIN)
        if v > config.MAX_TOKENS_MAX:
            return int(config.MAX_TOKENS_MAX)
        return v

    def _selected_sources(self, selected):
        """Разрешает пользовательский выбор в кортежи источников."""
        chosen = {}
        if isinstance(selected, list) and selected:
            for opt in selected:
                if isinstance(opt, dict):
                    label = str(opt.get("label", ""))
                else:
                    label = str(opt)
                base = self.by_label.get(label)
                if base is None:
                    continue
                temp = self._coerce_temperature(
                    opt.get("temperature") if isinstance(opt, dict) else None)
                chosen[label] = (base, temp)
        if not chosen:
            for base in self.sources:
                chosen[base[2]] = (base, None)
        return chosen

    def answer(self, question, history=None, selected=None, max_tokens=None,
               compact=None, memory=None, profile=None, answer_title=None,
               task_state=None, invariants=None):
        """Обрабатывает запрос пользователя и возвращает результат."""
        from .. import config
        trace = []
        question = str(question or "").strip()
        trace.append({"kind": "enter",
                      "title": "Агент принял запрос пользователя"})
        print("[TRACE] Agent.answer() ВХОД. question=%r" % question, flush=True)
        if not question:
            step = {"kind": "exit", "ok": False,
                    "title": "Агент: пустой вопрос",
                    "detail": "вернул {ok:False, error:'Пустой вопрос.'}"}
            trace.append(step)
            print("[TRACE] Agent.answer() пустой вопрос -> ранний выход", flush=True)
            return Ok(self).value(ok=False, error="Пустой вопрос.", trace=trace)

        # Сжатие истории.
        already_compacted = (
            isinstance(history, list) and history
            and isinstance(history[0], dict)
            and history[0].get("role") == "system"
        )
        if (not already_compacted and compact
                and compact.get("enabled") and compact.get("summary")):
            history = self._apply_compact(history, compact)
            trace.append({"kind": "act", "title": "Агент: применено сжатие истории",
                          "detail": "сохранено %d последних сообщений, остальное — summary"
                                    % compact.get("keep", config.COMPACT_KEEP)})
        elif already_compacted:
            trace.append({"kind": "act",
                          "title": "Агент: контекст уже сжат (summary + последние)",
                          "detail": "сжатие применено на сервере, повторно не выполняется"})

        messages = self._build_messages(history, question, profile=profile,
                                        task_state=task_state,
                                        invariants=invariants)
        hlen = len(history) if isinstance(history, list) else 0
        prof_note = ""
        if isinstance(profile, dict) and (profile.get("character")
                                          or profile.get("style")):
            prof_note = " | профиль: %s" % (profile.get("name") or "без имени")
        task_note = ""
        if isinstance(task_state, dict) and task_state.get("active"):
            task_note = " | задача: %s%s" % (
                task_state.get("stage", ""),
                " (пауза)" if task_state.get("paused") else "")
        inv_list = [i for i in (invariants or [])
                    if isinstance(i, dict) and str(i.get("text") or "").strip()]
        inv_note = (" | инвариантов: %d" % len(inv_list)) if inv_list else ""
        trace.append({"kind": "act", "title": "Агент собрал сообщения для API",
                      "detail": "%d сообщений (%d из истории + текущий) | системный "
                                "промпт добавлен%s%s%s" % (len(messages), hlen,
                                                          prof_note, task_note,
                                                          inv_note)})
        print("[TRACE] Agent.answer() собрал %d сообщений для API" % len(messages),
              flush=True)

        sources = self._selected_sources(selected)
        trace.append({"kind": "branch", "title": "Агент -> запрос к LLM",
                      "detail": "агент опрашивает %d модель(ей) из выбранных"
                                % len(sources)})
        print("[TRACE] Agent.answer() опрашивает %d источника:"
              % len(sources), flush=True)

        blocks, text_parts, collected = [], [], []
        ok_any = False
        input_total = 0
        output_total = 0
        memory_used = {"working": 0, "longterm": 0}
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        mt = self._coerce_max_tokens(max_tokens)
        mt_note = ("max_tokens=%d" % mt) if mt is not None else "max_tokens=auto"

        for label, (base, temperature) in sources.items():
            provider, model, _lbl, cls = base
            temp_note = ("temperature=%.2f" % temperature
                         if temperature is not None else "temperature=auto")
            node = {"kind": "llm", "model": label,
                    "title": "LLM: %s" % label,
                    "detail": "отправка… " + temp_note + " · " + mt_note}
            trace.append(node)
            print("[TRACE]   -> вызов модели label=%r %s %s"
                  % (label, temp_note, mt_note), flush=True)
            single = self._call_one(provider, model, messages, label, temperature,
                                    max_tokens=mt)
            node["ok"] = single["ok"]
            node["detail"] = ("запрос выполнен за %.2f c · ввод %d/вывод %d ток"
                              % (single["elapsed"], single["prompt_tokens"],
                                 single["completion_tokens"]))
            node["dur"] = round(single["elapsed"], 2)
            node["dur_ms"] = int(single["elapsed"] * 1000)
            print("[TRACE]   <- результат %r: ok=%s" % (label, single["ok"]),
                  flush=True)
            input_total += single["prompt_tokens"]
            output_total += single["completion_tokens"]

            # ДЕТЕРМИНИРОВАННАЯ ПОСТ-ПРОВЕРКА ИНВАРИАНТОВ
            check = None
            if inv_list and single["ok"] and str(single["content"]).strip():
                check = self.check_invariants(question, single["content"],
                                              inv_list, model=model)
                if check.get("violated"):
                    trace.append({
                        "kind": "act",
                        "title": "Инвариант нарушен — ответ заменён отказом",
                        "detail": "модель %s: %s"
                                  % (label, check.get("invariant") or "инвариант")})
                    ref_html = self._invariant_refusal_html(check,
                                                            title=answer_title
                                                            or label)
                    ref_text = self._invariant_refusal_text(check,
                                                            title=answer_title
                                                            or label)
                    blocks.append(ref_html)
                    text_parts.append(ref_text)
                    collected.append({
                        "label": answer_title or label,
                        "model": label,
                        "text": ref_text,
                        "temperature": temperature,
                        "input": single["prompt_tokens"],
                        "output": single["completion_tokens"],
                        "cost": self._estimate_cost(provider, model,
                                                    single["prompt_tokens"],
                                                    single["completion_tokens"]),
                        "invariant_violation": check,
                    })
                    continue

            block_html, mem_counts = self._render_block(
                provider, model, label, cls, single, memory,
                title=answer_title)
            blocks.append(block_html)
            memory_used["working"] += mem_counts["working"]
            memory_used["longterm"] += mem_counts["longterm"]
            text_parts.append(self._render_text(provider, model, label, single,
                                                title=answer_title))
            collected.append({
                "label": answer_title or label,
                "model": label,
                "text": single["content"],
                "temperature": temperature,
                "input": single["prompt_tokens"],
                "output": single["completion_tokens"],
                "cost": self._estimate_cost(provider, model,
                                            single["prompt_tokens"],
                                            single["completion_tokens"]),
            })

        total_tokens = input_total + output_total
        history_tokens = self._history_token_estimate(messages, input_total)
        meta = self._build_meta(ts, total_tokens, ok_any)
        html = "".join(blocks)
        text = "\n\n".join(text_parts)
        trace.append({"kind": "exit", "ok": ok_any,
                      "title": "Агент возвращает ответ",
                      "detail": "собрано %d ответов · суммарно %d ток · ok=%s"
                                % (len(collected), total_tokens, ok_any)})
        print("[TRACE] Agent.answer() ГОТОВО. ok=%s, токенов=%d, история~%d"
              % (ok_any, total_tokens, history_tokens), flush=True)
        usage = {
            "input": input_total,
            "output": output_total,
            "total": total_tokens,
            "history": history_tokens,
        }
        return Ok(self).value(ok=ok_any, html=html, text=text,
                              answers=collected, meta=meta, trace=trace,
                              usage=usage, memory_used=memory_used)
