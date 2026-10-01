"""Компактификация: compact_history, compact_update, _apply_compact."""
import time

from .. import config, gigachat
from .base import SYSTEM_PROMPT

__all__ = ["CompactAgent"]


class CompactAgent:
    """Миксин: компактификация истории (summary)."""

    @staticmethod
    def _apply_compact(history, compact):
        """Применяет сжатие к истории диалога."""
        if not history or not compact.get("summary"):
            return history
        keep = max(0, compact.get("keep", config.COMPACT_KEEP))
        if keep <= 0:
            return history
        if keep >= len(history):
            return history
        recent = list(history[-keep:]) if keep > 0 else []
        summary_msg = {"role": "system", "content": compact["summary"]}
        return [summary_msg] + recent

    def compact_history(self, messages, keep=None):
        """Генерирует summary для ВЫТЕСНЯЕМОЙ части истории диалога."""
        keep = config.COMPACT_KEEP if keep is None else max(0, int(keep))
        tail = messages[-keep:] if keep > 0 else []
        head = messages[:-keep] if keep > 0 else list(messages)
        if len(head) < config.COMPACT_MIN:
            return None
        return self.compact_update("", head)

    def compact_update(self, prev_summary, new_messages):
        """Инкрементально ДОПИСЫВАЕТ вытесненные сообщения в summary."""
        new_messages = [m for m in (new_messages or []) if isinstance(m, dict)]
        if not new_messages:
            return None

        cap = config.COMPACT_MSG_CAP
        lines = [
            "Обнови краткое summary диалога, добавив в него новый фрагмент.",
            "Сохрани ключевые факты, темы, договорённости и решения,",
            "чтобы по summary можно было продолжить беседу.",
            "Не повторяйся, объедини прежнее и новое в единый связный текст.",
            "",
        ]
        if prev_summary:
            lines += ["Прежнее summary:", str(prev_summary), ""]
        lines.append("Новый фрагмент диалога (вытеснен из контекста):")
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

        prompt = "\n\n".join(lines)
        messages_for_compact = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        try:
            t0 = time.perf_counter()
            res = gigachat.chat(
                messages_for_compact,
                model=config.GC_MODEL,
                temperature=0.3,
            )
            elapsed = time.perf_counter() - t0
            summary = res.get("content", "") if isinstance(res, dict) else str(res)
            if summary:
                print("[COMPACT] summary дополнен %.2f c, длина %d, +%d сообщ."
                      % (elapsed, len(summary), len(new_messages)), flush=True)
            return summary
        except Exception as exc:
            print("[COMPACT] ошибка: %s" % exc, flush=True)
            return None
