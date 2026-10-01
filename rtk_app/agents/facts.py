"""Обновление фактов: update_facts."""
import json
import time

from .. import config, gigachat
from .base import json_dumps_safe, parse_facts_json

__all__ = ["FactsAgent"]


class FactsAgent:
    """Миксин: обновление блока facts (key-value) после нового фрагмента диалога."""

    def update_facts(self, prev_facts, new_messages):
        """Обновляет блок facts (key-value) после нового фрагмента диалога."""
        prev_facts = {str(k): str(v) for k, v in (prev_facts or {}).items()}
        new_messages = [m for m in (new_messages or []) if isinstance(m, dict)]
        if not new_messages:
            return prev_facts

        cap = config.COMPACT_MSG_CAP
        lines = [
            "Ты ведёшь блок фактов (key-value) о диалоге.",
            "Обнови факты, добавив/изменив важное из нового фрагмента диалога.",
            "Храни: цель, ограничения, предпочтения, решения, договорённости.",
            "Верни ТОЛЬКО валидный JSON-объект (словарь строка-строка),",
            "без пояснений и без markdown. Если факт устарел — убери его.",
            "",
        ]
        if prev_facts:
            lines += ["Текущие факты (JSON):",
                      json_dumps_safe(prev_facts), ""]
        else:
            lines += ["Текущих фактов нет.", ""]
        lines.append("Новый фрагмент диалога:")
        for m in new_messages:
            role = m.get("role", "unknown")
            content = str(m.get("content", ""))
            if not content:
                continue
            if len(content) > cap:
                content = content[:cap] + " […]"
            if role == "user":
                lines.append("Пользователь: " + content)
            elif role == "assistant":
                lines.append("Ассистент: " + content)

        prompt = "\n".join(lines)
        messages_for_facts = [
            {"role": "system",
             "content": "Ты извлекаешь факты из диалога и отвечаешь строго JSON."},
            {"role": "user", "content": prompt},
        ]

        try:
            t0 = time.perf_counter()
            res = gigachat.chat(
                messages_for_facts,
                model=config.GC_MODEL,
                temperature=0.2,
            )
            elapsed = time.perf_counter() - t0
            content = res.get("content", "") if isinstance(res, dict) else str(res)
            facts = parse_facts_json(content)
            if facts is not None:
                print("[FACTS] факты обновлены %.2f c: %d ключей"
                      % (elapsed, len(facts)), flush=True)
                return facts
            print("[FACTS] не удалось разобрать JSON, оставляем прежние факты",
                  flush=True)
            return prev_facts
        except Exception as exc:
            print("[FACTS] ошибка: %s" % exc, flush=True)
            return prev_facts
