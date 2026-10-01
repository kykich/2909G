"""Проверка инвариантов: check_invariants, invariants_system_prompt,
refusal-рендеринг.
"""
import json

from .base import parse_facts_json, json_dumps_safe
from .. import config, html_report

__all__ = ["InvariantChecker"]


class InvariantChecker:
    """Миксин: проверка инвариантов ответа модели."""

    @staticmethod
    def invariants_system_prompt(invariants):
        """Собирает блок инвариантов для системного промпта (или "")."""
        items = [i for i in (invariants or []) if isinstance(i, dict)
                 and str(i.get("text") or "").strip()]
        if not items:
            return ""
        by_cat = {}
        for i in items:
            cat = str(i.get("category") or "business")
            by_cat.setdefault(cat, []).append(str(i.get("text")).strip())
        label_map = {c: label for c, label in config.INVARIANT_CATEGORIES}
        lines = ["ИНВАРИАНТЫ (жёсткие правила — НАРУШАТЬ НЕЛЬЗЯ):"]
        ordered = [c for c, _l in config.INVARIANT_CATEGORIES]
        for code in ordered:
            if code in by_cat:
                lines.append("%s:" % label_map.get(code, code))
                for t in by_cat[code]:
                    lines.append("  - %s" % t)
                by_cat.pop(code)
        for code, texts in by_cat.items():
            lines.append("%s:" % label_map.get(code, code))
            for t in texts:
                lines.append("  - %s" % t)
        lines.append(
            "Если запрос пользователя противоречит хотя бы одному "
            "инварианту — ОТКАЖИСЬ предлагать нарушающее решение и кратко "
            "объясни, какой именно инвариант нарушен и почему.")
        return "\n".join(lines)

    def check_invariants(self, question, answer_text, invariants, model=None):
        """ДЕТЕРМИНИРОВАННАЯ пост-проверка ответа на нарушение инвариантов."""
        items = [i for i in (invariants or []) if isinstance(i, dict)
                 and str(i.get("text") or "").strip()]
        answer_text = str(answer_text or "").strip()
        question = str(question or "").strip()
        if not items or not answer_text:
            return {"checked": False, "violated": False, "invariant": "",
                    "reason": "", "raw": "", "error": None}

        rules = []
        for i, it in enumerate(items, 1):
            rules.append("%d) [%s] %s" % (
                i, it.get("category", "business"),
                str(it.get("text")).strip()))
        prompt = "\n".join([
            "Ты — строгий контролёр инвариантов. Проверь, нарушает ли",
            "ОТВЕТ АССИСТЕНТА хотя бы один из ИНВАРИАНТОВ (жёстких правил).",
            "Инварианты — это ограничения (архитектура, техрешения, стек,",
            "бизнес-правила), которые НАРУШАТЬ НЕЛЬЗЯ.",
            "",
            "ИНВАРИАНТЫ:",
            "\n".join(rules),
            "",
            "ЗАПРОС ПОЛЬЗОВАТЕЛЯ:",
            question or "(нет)",
            "",
            "ОТВЕТ АССИСТЕНТА:",
            answer_text,
            "",
            "Если ответ нарушает или предлагает решение, нарушающее хотя бы",
            "один инвариант — верни STRICT JSON:",
            '  {"violated": true, "invariant": "<текст инварианта>", '
            '"reason": "<кратко, чем нарушен>"}',
            "Если нарушений НЕТ — верни STRICT JSON:",
            '  {"violated": false, "invariant": "", "reason": ""}',
            "Только JSON, без пояснений и markdown.",
        ])
        provider, model_name = self._resolve_model(model)
        try:
            res = self._chat_text(provider, model_name, [
                {"role": "system",
                 "content": "Ты проверяешь ответы на нарушение инвариантов и "
                            "отвечаешь строго JSON."},
                {"role": "user", "content": prompt},
            ], temperature=0.0)
            content = res.get("content", "") if isinstance(res, dict) else str(res)
            data = parse_facts_json(content)
            if not isinstance(data, dict):
                return {"checked": True, "violated": False, "invariant": "",
                        "reason": "", "raw": content,
                        "error": "Не удалось разобрать ответ контролёра."}
            violated = data.get("violated")
            if isinstance(violated, str):
                violated = violated.strip().lower() in ("true", "1", "да", "yes")
            else:
                violated = bool(violated)
            print("[INVARIANT] проверка: violated=%s" % violated, flush=True)
            return {"checked": True,
                    "violated": violated,
                    "invariant": str(data.get("invariant", "") or ""),
                    "reason": str(data.get("reason", "") or ""),
                    "raw": content,
                    "error": None}
        except Exception as exc:
            print("[INVARIANT] ошибка проверки: %s" % exc, flush=True)
            return {"checked": True, "violated": False, "invariant": "",
                    "reason": "", "raw": "", "error": str(exc)}

    @staticmethod
    def _invariant_refusal_html(check, title=None):
        """HTML-карточка ОТКАЗА от решения, нарушающего инвариант."""
        inv = (check or {}).get("invariant") or "(инвариант)"
        reason = (check or {}).get("reason") or ""
        title = title or "Ассистент"
        reason_html = ("<div class='invariant-refuse-reason'>%s</div>"
                       % html_report.escape_html(reason)) if reason else ""
        return (
            "<div class='variant variant-invariant-refuse'>"
            "<div class='variant-head'>"
            "<span class='variant-name'>%s</span>"
            "<span class='variant-badge'>отказ: нарушение инварианта</span>"
            "</div>"
            "<div class='variant-body'>"
            "<p><b>Не могу предложить такое решение</b> — оно нарушает "
            "инвариант:</p><blockquote>%s</blockquote>%s"
            "</div></div>"
            % (html_report.escape_html(title),
               html_report.escape_html(inv), reason_html)
        )

    @staticmethod
    def _invariant_refusal_text(check, title=None):
        """Текстовое представление отказа (для text-части результата)."""
        inv = (check or {}).get("invariant") or "(инвариант)"
        reason = (check or {}).get("reason") or ""
        title = title or "Ассистент"
        line = ("%s: отказ — решение противоречит инварианту: %s"
                % (title, inv))
        if reason:
            line += " Причина: %s" % reason
        return line
