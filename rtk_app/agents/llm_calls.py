"""Вызовы моделей: _call_one, _chat_text, _resolve_model, _build_messages,
рендеринг, оценка стоимости.
"""
import time
from datetime import datetime

from .base import SYSTEM_PROMPT
from .. import config, deepseek, gigachat, html_report

__all__ = ["LLMCaller"]


class LLMCaller:
    """Миксин: вызовы LLM, построение сообщений, рендеринг ответов."""

    def _resolve_model(self, model):
        """Определяет (провайдер, имя модели) по метке или откатывается."""
        label = str(model or "").strip()
        base = self.by_label.get(label)
        if base is None:
            for provider, name, _lbl, _cls in self.sources:
                if name == label:
                    return provider, name
            return "gigachat", config.GC_MODEL
        provider, name, _lbl, _cls = base
        return provider, name

    def _chat_text(self, provider, model, messages, temperature=None,
                   max_tokens=None):
        """Вызывает одну модель и возвращает её ответ (dict с content/tokens)."""
        if provider == "deepseek":
            return deepseek.chat(self.api_key, messages, model=model,
                                 temperature=temperature, max_tokens=max_tokens)
        return gigachat.chat(messages, model=model,
                             temperature=temperature, max_tokens=max_tokens)

    def _call_one(self, provider, model, messages, label, temperature=None,
                  max_tokens=None):
        """Вызывает одну конкретную модель через API и фиксирует результат."""
        t0 = time.perf_counter()
        try:
            if provider == "deepseek":
                res = deepseek.chat(self.api_key, messages,
                                    model=model, temperature=temperature,
                                    max_tokens=max_tokens)
            else:
                res = gigachat.chat(messages, model=model,
                                    temperature=temperature,
                                    max_tokens=max_tokens)
            return {
                "ok": True,
                "content": res.get("content", ""),
                "prompt_tokens": int(res.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(res.get("completion_tokens", 0) or 0),
                "elapsed": time.perf_counter() - t0,
                "error": None,
            }
        except Exception as exc:
            return {
                "ok": False,
                "content": "[Ошибка модели %s: %s]" % (label, exc),
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "elapsed": time.perf_counter() - t0,
                "error": str(exc),
            }

    def _build_messages(self, history, question, profile=None, task_state=None,
                        invariants=None, rag_enabled=False, rag_query=None):
        """Собирает полный список сообщений для API."""
        system_parts = [SYSTEM_PROMPT]
        prof_prompt = self.profile_system_prompt(profile)
        if prof_prompt:
            system_parts.append(prof_prompt)
        task_prompt = self.task_system_prompt(task_state)
        if task_prompt:
            system_parts.append(task_prompt)
        inv_prompt = self.invariants_system_prompt(invariants)
        if inv_prompt:
            system_parts.append(inv_prompt)

        # RAG: добавляем релевантные чанки из документов
        rag_context = ""
        if rag_enabled and rag_query:
            try:
                from ..rag import retrieve, build_context
                matches = retrieve(rag_query)
                if matches:
                    rag_context = build_context(matches)
                    system_parts.append(
                        "ОСНОВЫВАЙСЯ НА СЛЕДУЮЩИХ ФАКТАХ ИЗ ДОКУМЕНТОВ:\n"
                        + rag_context
                    )
            except Exception:
                pass  # RAG не критичен — молча пропускаем

        dialog = []
        if isinstance(history, list):
            for m in history:
                if (isinstance(m, dict)
                        and isinstance(m.get("content"), str)
                        and m["content"]):
                    role = m.get("role")
                    if role == "system":
                        system_parts.append(m["content"])
                    elif role in ("user", "assistant"):
                        dialog.append({"role": role, "content": m["content"]})
        messages = [{"role": "system", "content": "\n\n".join(system_parts)}]
        messages.extend(dialog)
        messages.append({"role": "user", "content": question})
        return messages

    @staticmethod
    def _history_token_estimate(messages, input_tokens):
        """Оценка числа входных токенов, приходящихся на историю диалога."""
        try:
            total_chars = sum(len(str(m.get("content", ""))) for m in messages)
            hist_chars = sum(len(str(m.get("content", "")))
                             for m in messages[1:-1])
        except Exception:
            return 0
        if total_chars <= 0 or input_tokens <= 0:
            return 0
        return int(round(input_tokens * hist_chars / total_chars))

    @staticmethod
    def _estimate_cost(provider, model, prompt_tokens, completion_tokens):
        """Оценка стоимости запроса в юанях."""
        if provider != "deepseek":
            return None
        in_price = config.DS_PRICE_INPUT_PER_M.get(model)
        out_price = config.DS_PRICE_OUTPUT_PER_M.get(model)
        if in_price is None or out_price is None:
            return None
        return (prompt_tokens * in_price
                + completion_tokens * out_price) / 1_000_000.0

    def _render_block(self, provider, model, label, cls, single, memory=None,
                      title=None):
        """HTML-блок (карточка ответа одной модели) и счётчики памяти."""
        content = single["content"]
        counts = {"working": 0, "longterm": 0}
        try:
            frag, counts = html_report.render_with_memory_counts(
                content, memory=memory)
        except Exception:
            frag = html_report.escape_html(content)
        block = (
            "<div class='variant variant-%s'>"
            "<div class='variant-head'>"
            "<span class='variant-name'>%s</span>"
            "</div>"
            "<div class='variant-body'>%s</div></div>"
            % (cls, title or label, frag)
        )
        return block, counts

    def _render_text(self, provider, model, label, single, title=None):
        """Текстовая строка-представление ответа одной модели."""
        return "%s:\n%s" % (title or label, single["content"])

    def _build_meta(self, ts, total_tokens, ok_any):
        """Служебная строка с информацией о генерации."""
        sources = ", ".join(self.enabled_models)
        if not ok_any:
            return ("Сгенерировано: %s · есть ошибки моделей · моделей: %s"
                    % (ts, sources))
        return ("Сгенерировано: %s · суммарно токенов: %d · моделей: %s"
                % (ts, total_tokens, sources))
