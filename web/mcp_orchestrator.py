"""Оркестратор композиции MCP-серверов.

Пайплайн: календарь → замполит → завхоз.
Отвечает за запуск композиции, формирование отчётов и сообщений.
"""
import json
import time

from rtk_app import config
from . import mcp_helpers

__all__ = ["composition_run", "format_composition_message",
           "composition_report_text"]


def composition_run(verbose=False):
    """ЗАПУСКАЕТ КОМПОЗИЦИЮ MCP-серверов (пайплайн календарь → замполит → завхоз).

    Возвращает dict с отчётом: {ok, calendar, pairs, saved, error, steps}.
    События календаря передаются «Замполиту» строкой JSON.
    """
    timeout = getattr(config, "COMPOSITION_CALL_TIMEOUT", 30)
    days = int(getattr(config, "COMPOSITION_DAYS_AHEAD", 7) or 7)
    cal_srv = getattr(config, "COMPOSITION_CALENDAR_SERVER", "calendar")
    zam_srv = getattr(config, "COMPOSITION_ZAMPOLIT_SERVER", "zampolit")
    zav_srv = getattr(config, "COMPOSITION_ZAVHOZ_SERVER", "zavhoz")
    steps = []
    servers = list(getattr(config, "COMPOSITION_SERVERS", []) or [])

    # --- Шаг 1: события календаря на ближайшие N дней ---
    today = time.strftime("%Y-%m-%d")
    until = time.strftime("%Y-%m-%d", time.localtime(time.time() + days * 86400))
    ok, cal_text = mcp_helpers.mcp_text(cal_srv, "list_events",
                                        {"start": today, "end": until}, timeout=timeout)
    steps.append({"step": "calendar", "ok": ok, "detail": cal_text[:400]})
    if not ok:
        return {"ok": False, "error": "Календарь: %s" % cal_text,
                "steps": steps, "pairs": [], "count": 0, "servers": servers}
    events = mcp_helpers.parse_calendar_events(cal_text)
    steps.append({"step": "calendar_parsed", "ok": True,
                  "detail": "событий: %d" % len(events)})
    if not events:
        ok, sav_text = mcp_helpers.mcp_text(zav_srv, "save_pairs",
                                             {"pairs_json": json.dumps({"pairs": []}),
                                              "source": "composition"}, timeout=timeout)
        steps.append({"step": "zavhoz", "ok": ok, "detail": sav_text[:400]})
        return {"ok": True, "calendar": cal_text, "pairs": [], "count": 0,
                "saved": sav_text, "steps": steps, "servers": servers,
                "detail": "Событий на ближайшие %d дней нет." % days}

    # --- Шаг 2: замполит — пары «событие + время» ---
    ok, zam_text = mcp_helpers.mcp_text(zam_srv, "build_pairs",
                                         {"events_json": json.dumps(events, ensure_ascii=False)},
                                         timeout=timeout)
    steps.append({"step": "zampolit", "ok": ok, "detail": zam_text[:600]})
    if not ok:
        return {"ok": False, "error": "Замполит: %s" % zam_text,
                "steps": steps, "pairs": [], "count": 0, "servers": servers}
    try:
        built = json.loads(zam_text)
    except Exception as exc:
        return {"ok": False, "error": "Замполит вернул не JSON: %s" % exc,
                "steps": steps, "pairs": [], "count": 0, "servers": servers}
    pairs = built.get("pairs") if isinstance(built, dict) else None
    if not isinstance(pairs, list):
        pairs = []

    # --- Шаг 3: завхоз — сохранить снимок в JSON ---
    ok, sav_text = mcp_helpers.mcp_text(zav_srv, "save_pairs",
                                         {"pairs_json": json.dumps({"pairs": pairs},
                                                                   ensure_ascii=False),
                                          "source": "composition"}, timeout=timeout)
    steps.append({"step": "zavhoz", "ok": ok, "detail": sav_text[:400]})
    if not ok:
        return {"ok": False, "error": "Завхоз: %s" % sav_text,
                "steps": steps, "pairs": pairs, "count": len(pairs),
                "servers": servers}
    if verbose:
        print("[COMPOSE] пар: %d; %s" % (len(pairs), sav_text), flush=True)
    return {"ok": True, "calendar": cal_text, "pairs": pairs,
            "count": len(pairs), "saved": sav_text, "steps": steps,
            "servers": servers,
            "detail": "Событий: %d, пар сохранено: %d." % (len(events), len(pairs))}


def format_composition_message(report):
    """Формирует СООБЩЕНИЕ в чат после запуска композиции.

    Содержит: заголовок, список серверов с описаниями, итог прогона.
    """
    report = report or {}
    servers = report.get("servers") or list(
        getattr(config, "COMPOSITION_SERVERS", []) or [])
    lines = ["**Композиция MCP запущена.** Задействованы серверы:"]
    for s in servers:
        label = s.get("label") or s.get("id") or "?"
        desc = s.get("desc") or ""
        lines.append("- **%s** — %s" % (label, desc))
    if report.get("ok"):
        detail = report.get("detail") or ""
        if detail:
            lines.append("")
            lines.append("Итог: %s" % detail)
    else:
        lines.append("")
        lines.append("Внимание, ошибка прогона: %s"
                     % (report.get("error") or "неизвестно"))
    return "\n".join(lines)


def composition_report_text(report):
    """Готовит ТЕКСТОВУЮ сводку прогона композиции ДЛЯ МОДЕЛИ."""
    report = report or {}
    lines = []
    servers = report.get("servers") or list(
        getattr(config, "COMPOSITION_SERVERS", []) or [])
    if servers:
        lines.append("Задействованные MCP-серверы:")
        for s in servers:
            label = s.get("label") or s.get("id") or "?"
            desc = s.get("desc") or ""
            lines.append("  - %s — %s" % (label, desc))
    if report.get("ok"):
        lines.append("Результат: %s" % (report.get("detail") or "успешно"))
        if report.get("saved"):
            lines.append("Сохранено: %s" % report.get("saved"))
        pairs = report.get("pairs") or []
        if pairs:
            lines.append("Пары «событие + время» (до %d):" % len(pairs))
            for p in pairs[:10]:
                ev = p.get("event") or p.get("summary") or "?"
                tm = p.get("time") or ""
                mode = p.get("mode") or ""
                lines.append("  - %s → %s (%s)" % (ev, tm, mode))
    else:
        lines.append("Результат: ОШИБКА — %s" % (report.get("error") or "?"))
    return "\n".join(lines)
