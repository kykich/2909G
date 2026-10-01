"""MCP-ветка агента: выбор инструмента, вызов, compose_message."""
import json
import time
from datetime import datetime, timedelta

from .base import json_dumps_safe
from .. import config
from .. import html_report

__all__ = ["MCPAgent"]


class MCPAgent:
    """Миксин: MCP-ветка агента (answer_via_mcp, compose_message)."""

    def mcp_select_system_prompt(self, tools):
        """Системный промпт для выбора MCP-инструмента под запрос."""
        now = datetime.now()
        weekdays = ["понедельник", "вторник", "среда", "четверг",
                    "пятница", "суббота", "воскресенье"]
        today = now.strftime("%Y-%m-%d")
        weekday = weekdays[now.weekday()]
        upcoming = []
        for i in range(0, 7):
            d = now + timedelta(days=i)
            label = {0: "сегодня", 1: "завтра"}.get(i, "")
            upcoming.append("%s — %s%s" % (
                weekdays[d.weekday()], d.strftime("%Y-%m-%d"),
                (" (%s)" % label) if label else ""))
        lines = [
            "Ты — ассистент, который решает задачу, ВЫЗЫВАЯ инструменты MCP.",
            "Сегодня %s (%s), текущее время %s." % (today, weekday,
                                                    now.strftime("%H:%M")),
            "Ближайшие дни (день недели — дата): " + "; ".join(upcoming) + ".",
            "ВАЖНО: для дня недели («в субботу», «в воскресенье») бери дату "
            "из этой таблицы (ближайший такой день), НЕ считай вручную.",
            "Для относительных дат («сегодня», «завтра», «на этой неделе») "
            "вычисляй конкретные даты ОТНОСИТЕЛЬНО этой даты и подставляй "
            "именно текущий год (%s), а не год из примеров." % today[:4],
            "Если указано только время (например, «15:00»), длительность "
            "события по умолчанию — 1 час.",
            "Тебе доступны инструменты MCP-сервера:",
        ]
        for t in (tools or []):
            params = ", ".join(t.get("params") or []) or "без аргументов"
            desc = (t.get("description") or "").strip()
            lines.append("  * %s(%s) — %s" % (t.get("name"), params, desc))
        lines += [
            "",
            "По запросу пользователя выбери ОДИН наиболее подходящий инструмент",
            "и подбери аргументы. Ответь СТРОГО одним JSON-объектом без пояснений:",
            '  {"tool": "<имя инструмента>", "arguments": {<аргументы>}}',
            "Если ни один инструмент не подходит, верни:",
            '  {"tool": null, "answer": "<краткий ответ по существу>"}',
        ]
        return "\n".join(lines)

    def answer_via_mcp(self, question, tools, model=None, temperature=None,
                       max_tokens=None, server_id=None):
        """Отвечает на запрос через MCP: модель выбирает инструмент и аргументы."""
        from .. import mcp_client

        trace = []
        question = str(question or "").strip()
        trace.append({"kind": "enter",
                      "title": "Агент: запрос через MCP"})
        if not question:
            trace.append({"kind": "exit", "ok": False,
                          "title": "Стоп: пустой вопрос"})
            return Ok(self).value(ok=False, error="Пустой вопрос.", trace=trace)

        provider, model_name = self._resolve_model(model)
        label = str(model or "").strip() or model_name
        mt = self._coerce_max_tokens(max_tokens)
        temp = self._coerce_temperature(temperature)

        messages = [
            {"role": "system", "content": self.mcp_select_system_prompt(tools)},
            {"role": "user", "content": question},
        ]
        trace.append({"kind": "llm", "model": label,
                      "title": "LLM: выбор MCP-инструмента",
                      "detail": "инструментов: %d" % len(tools or [])})
        single = self._call_one(provider, model_name, messages, label, temp,
                                max_tokens=mt)
        input_total = single["prompt_tokens"]
        output_total = single["completion_tokens"]

        if not single["ok"]:
            trace.append({"kind": "exit", "ok": False,
                          "title": "Стоп: модель недоступна",
                          "detail": single.get("error") or ""})
            return Ok(self).value(
                ok=False, trace=trace,
                error=single.get("error") or "Модель выбора инструмента недоступна.",
                usage={"input": input_total, "output": output_total,
                       "total": input_total + output_total, "history": 0})

        decision = self._parse_mcp_decision(single["content"])
        tool_name = (decision or {}).get("tool")
        args = (decision or {}).get("arguments") or {}

        if not tool_name:
            direct = (decision or {}).get("answer") or single["content"]
            trace.append({"kind": "branch", "title": "MCP: инструмент не нужен",
                          "detail": "прямой ответ модели"})
            html = self._mcp_answer_html(question, direct, tool_name=None)
            text = "%s:\n%s" % (label, direct)
            trace.append({"kind": "exit", "ok": True,
                          "title": "Готово: ответ модели (без MCP)"})
            return Ok(self).value(
                ok=True, html=html, text=text,
                answers=[{"label": label, "model": label, "text": direct,
                          "temperature": temperature,
                          "input": input_total, "output": output_total,
                          "cost": self._estimate_cost(
                              provider, model_name, input_total, output_total)}],
                meta=self._build_meta(
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    input_total + output_total, True),
                trace=trace,
                usage={"input": input_total, "output": output_total,
                       "total": input_total + output_total, "history": 0},
                memory_used={"working": 0, "longterm": 0},
                mcp={"tool": None, "arguments": {}, "result": None})

        trace.append({"kind": "branch", "title": "MCP -> вызов инструмента",
                      "detail": "%s(%s)" % (tool_name, json_dumps_safe(args))})
        call = mcp_client.mcp_call_tool(tool_name, args, server_id=server_id)
        if not call.get("ok"):
            err = call.get("error") or "инструмент вернул ошибку"
            trace.append({"kind": "exit", "ok": False,
                          "title": "Стоп: ошибка MCP-инструмента",
                          "detail": err})
            html = self._mcp_answer_html(question, "Ошибка MCP: %s" % err,
                                         tool_name=tool_name, error=True)
            text = "%s:\nОшибка MCP: %s" % (label, err)
            return Ok(self).value(
                ok=False, html=html, text=text, trace=trace,
                error=err,
                usage={"input": input_total, "output": output_total,
                       "total": input_total + output_total, "history": 0},
                mcp={"tool": tool_name, "arguments": args,
                     "result": call.get("text", "")})

        result_text = call.get("text", "")
        trace.append({"kind": "llm", "model": tool_name,
                      "title": "MCP: результат инструмента",
                      "detail": result_text[:200]})
        html = self._mcp_answer_html(question, result_text, tool_name=tool_name,
                                     arguments=args)
        text = "%s (MCP: %s):\n%s" % (label, tool_name, result_text)
        trace.append({"kind": "exit", "ok": True,
                      "title": "Готово: ответ через MCP"})
        return Ok(self).value(
            ok=True, html=html, text=text,
            answers=[{"label": label, "model": label, "text": text,
                      "temperature": temperature,
                      "input": input_total, "output": output_total,
                      "cost": self._estimate_cost(
                          provider, model_name, input_total, output_total),
                      "mcp_tool": tool_name}],
            meta=self._build_meta(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                input_total + output_total, True),
            trace=trace,
            usage={"input": input_total, "output": output_total,
                   "total": input_total + output_total, "history": 0},
            memory_used={"working": 0, "longterm": 0},
            mcp={"tool": tool_name, "arguments": args, "result": result_text})

    def compose_message(self, report_text, model=None, fallback=""):
        """Формирует СООБЩЕНИЕ о запуске композиции MCP СИЛАМИ МОДЕЛИ."""
        provider, model_name = self._resolve_model(model)
        label = str(model or "").strip() or model_name
        system = ("Ты — ассистент, который кратко отчитывается о запуске "
                  "композиции MCP-серверов. Отвечай по-русски, дружелюбно, "
                  "1–3 предложениями, без markdown-таблиц.")
        user = ("Запущена КОМПОЗИЦИЯ MCP-серверов. Сводка прогона:\n\n"
                + str(report_text or "") +
                "\n\nСформируй короткое сообщение для чата: что сделала "
                "композиция и какой итог (сколько событий обработано и что "
                "сохранено). Не выдумывай данные, которых нет в сводке.")
        try:
            res = self._chat_text(provider, model_name, [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ], temperature=0.3)
            content = res.get("content", "") if isinstance(res, dict) else str(res)
            text = str(content or "").strip()
            if text:
                print("[COMPOSE] сообщение сгенерировано моделью %s" % label,
                      flush=True)
                return {"ok": True, "text": text, "model": label, "error": None}
            print("[COMPOSE] модель %s вернула пустой текст — fallback" % label,
                  flush=True)
            return {"ok": False, "text": fallback, "model": label,
                    "error": "Пустой ответ модели."}
        except Exception as exc:
            print("[COMPOSE] сообщение: модель %s недоступна (%s) — fallback"
                  % (label, exc), flush=True)
            return {"ok": False, "text": fallback, "model": label,
                    "error": str(exc)}

    @staticmethod
    def _parse_mcp_decision(text):
        """Разбирает JSON-решение модели о вызове MCP-инструмента."""
        if not text:
            return None
        s = str(text).strip()
        if s.startswith("```"):
            s = s.strip("`")
            if "\n" in s:
                first, rest = s.split("\n", 1)
                if first.strip().lower() in ("json", ""):
                    s = rest
            s = s.strip()

        def _pick(obj):
            if not isinstance(obj, dict):
                return None
            tool = obj.get("tool") or obj.get("name") or obj.get("tool_name")
            if tool:
                args = (obj.get("arguments") or obj.get("args")
                        or obj.get("params") or {})
                if not isinstance(args, dict):
                    args = {}
                return {"tool": str(tool), "arguments": args}
            ans = obj.get("answer") or obj.get("text") or obj.get("response")
            return {"tool": None, "answer": ("" if ans is None else str(ans))}

        try:
            data = json.loads(s)
            picked = _pick(data)
            if picked is not None:
                return picked
        except Exception:
            pass
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end > start:
            try:
                return _pick(json.loads(s[start:end + 1]))
            except Exception:
                return None
        return None

    @staticmethod
    def _mcp_answer_html(question, result_text, tool_name=None,
                         arguments=None, error=False):
        """HTML-карточка ответа через MCP (инструмент + результат)."""
        parts = ['<div class="mcp-answer%s">' %
                 (" mcp-answer-error" if error else "")]
        if tool_name:
            args = json_dumps_safe(arguments or {})
            parts.append('<div class="mcp-answer-head">MCP-инструмент: '
                         '<b>%s</b>(%s)</div>' % (html_report.escape_html(tool_name),
                                                  html_report.escape_html(args)))
        else:
            parts.append('<div class="mcp-answer-head">Ответ модели '
                         '(инструмент не задействован)</div>')
        parts.append('<div class="mcp-answer-body"><pre>%s</pre></div>'
                     % html_report.escape_html(result_text or ""))
        parts.append("</div>")
        return "".join(parts)
