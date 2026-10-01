"""Помощники для MCP-вызовов и парсинга календаря.

- mcp_text: обёртка над mcp_client.mcp_call_tool
- collect_due_reminders: автоматический сбор напоминаний
- board_direct_result: детерминированный вывод доски
- parse_calendar_events: разбор текстового вывода list_events
"""
import html as _html
import json
import re

from rtk_app import config

try:
    from rtk_app import mcp_client
except Exception:
    mcp_client = None


def mcp_text(server_id, tool, arguments=None, timeout=None):
    """Вызывает MCP-инструмент и возвращает текст результата.

    Возвращает (ok, text): ok=False, если клиент недоступен или инструмент
    сообщил об ошибке.
    """
    # Динамическая проверка: если тест мокает mcp_client на уровне web.server,
    # используем его; иначе — глобальный mcp_client.
    client = None
    try:
        from . import server as _ws
        client = getattr(_ws, "mcp_client", None)
    except Exception:
        pass
    if client is None:
        client = mcp_client
    if client is None:
        return False, "MCP-клиент недоступен (не установлен пакет mcp)."
    try:
        res = client.mcp_call_tool(tool, arguments or {},
                                    timeout=timeout, server_id=server_id)
    except Exception as exc:
        return False, "Ошибка вызова %s: %s" % (tool, exc)
    if not res.get("ok"):
        return False, res.get("error") or res.get("text") or "ошибка инструмента"
    return True, (res.get("text") or "")


def collect_due_reminders():
    """Собирает НАСТУПИВШИЕ напоминания календаря (для доставки в чат).

    Возвращает список строк-напоминаний (может быть пустым).
    """
    # Динамическая проверка для поддержки моков.
    client = None
    try:
        from . import server as _ws
        client = getattr(_ws, "mcp_client", None)
    except Exception:
        pass
    if client is None:
        client = mcp_client
    if client is None:
        return []
    from . import state
    server_id = state._ServerState.mcp_server or None
    try:
        res = client.mcp_call_tool("run_due", {}, server_id=server_id)
    except Exception as exc:
        print("[REMINDER] не удалось собрать напоминания: %s" % exc,
              flush=True)
        return []
    if not res.get("ok"):
        return []
    text = (res.get("text") or "").strip()
    if not text or "нет" in text.lower() and "напоминан" in text.lower():
        return []
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if lines and lines[0].lower().startswith("напоминаний:"):
        lines = lines[1:]
    return lines


def board_direct_result(server_id, model=None):
    """Формирует ответ для сервера «Доска» БЕЗ выбора инструмента LLM.

    Вызывает show_board_html + show_board детерминированно.
    Возвращает dict формы {ok, text, html, answers, meta}.
    """
    ok_html, html_text = mcp_text(server_id, "show_board_html", {})
    ok_txt, board_text = mcp_text(server_id, "show_board", {})
    if not ok_html and not ok_txt:
        err = board_text or html_text or "инструмент доски недоступен"
        return {"ok": False, "error": "Доска: %s" % err, "text": "",
                "html": "", "answers": [], "meta": ""}
    text = board_text if ok_txt else html_text
    html = ""
    if ok_html and "<table" in str(html_text):
        html = ('<div class="mcp-answer"><div class="mcp-answer-head">'
                'MCP-инструмент: <b>show_board_html</b>({})</div>'
                '<div class="mcp-answer-body">%s</div></div>'
                % html_text)
    else:
        html = ('<div class="mcp-answer"><div class="mcp-answer-head">'
                'MCP-инструмент: <b>show_board</b>({})</div>'
                '<div class="mcp-answer-body"><pre>%s</pre></div></div>'
                % _html.escape(str(board_text)))
    label = model or "MCP"
    return {"ok": True, "text": text, "html": html,
            "answers": [{"label": label, "model": label, "text": text}],
            "meta": "MCP: show_board"}


def parse_calendar_events(text):
    """Разбирает текстовый вывод list_events в список {summary, start, all_day}."""
    events = []
    pat_timed = re.compile(
        r"(?P<start>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2})\s*—\s*(?P<summary>.+)")
    pat_allday = re.compile(
        r"(?P<start>\d{4}-\d{2}-\d{2})\s*—\s*(?P<summary>.+)")
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("UID:"):
            continue
        if re.match(r"^\s*События за\b", line) or re.match(
                r"^\s*\d{4}-\d{2}-\d{2}\s+—\s+\d{4}-\d{2}-\d{2}\s*:", line):
            continue
        m = pat_timed.search(line)
        all_day = False
        if m:
            start = m.group("start").replace("T", " ")
        else:
            m = pat_allday.search(line)
            if not m:
                continue
            start = m.group("start").strip()
            all_day = True
        summary = m.group("summary").strip()
        for sep in (", до ", ", место:", ", место "):
            idx = summary.find(sep)
            if idx != -1:
                summary = summary[:idx].strip()
        summary = summary.strip().strip("«»\"'")
        events.append({"summary": summary, "start": start, "all_day": all_day})
    return events
