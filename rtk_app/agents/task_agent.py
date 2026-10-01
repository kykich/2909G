"""Управление задачами: advance_task, task_system_prompt, profile_system_prompt."""
from .base import parse_facts_json

__all__ = ["TaskAgent"]


class TaskAgent:
    """Миксин: управление задачами (Task State Machine)."""

    @staticmethod
    def task_system_prompt(task_state):
        """Собирает блок системного промпта из формализованного состояния задачи."""
        try:
            from ..task_state import TaskState
            ts = TaskState(task_state)
        except Exception:
            return ""
        if not ts.active:
            return ""
        block = ts.system_prompt_block()
        block += ("\nИнструкция: веди ответ сообразно этапу и шагу задачи; "
                  "если задача на паузе — по запросу продолжай с текущего "
                  "места, не требуя повторно объяснять задачу.")
        return block

    @staticmethod
    def profile_system_prompt(profile):
        """Собирает системную инструкцию из профиля (характер + стиль)."""
        if not isinstance(profile, dict):
            return ""
        character = str(profile.get("character") or "").strip()
        style = str(profile.get("style") or "").strip()
        name = str(profile.get("name") or "").strip()
        parts = []
        if character:
            parts.append("Характер общения (тон): %s." % character)
        if style:
            parts.append("Характер ответов (формат и длина): %s." % style)
        if not parts:
            return ""
        head = "Персона, от лица которой ты отвечаешь"
        if name:
            head += " («%s»)" % name
        return head + ": " + " ".join(parts)

    def advance_task(self, task_state, question, answer="", model=None):
        """Определяет ПЕРЕХОД состояния задачи по ходу пользователя."""
        try:
            from ..task_state import TaskState, STAGES, STAGE_LABELS
        except Exception:
            return {}
        ts = TaskState(task_state)
        if not ts.active:
            return {}
        lines = [
            "Ты управляешь конечным автоматом ЗАДАЧИ (этапы: planning ->",
            "execution -> validation -> done). Определи НОВОЕ состояние",
            "задачи после нового сообщения пользователя.",
            "",
            "Текущее состояние задачи:",
            "Цель: %s" % (ts.goal or "не указана"),
            "Этап: %s" % ts.stage,
            "Шаг: %s" % (ts.step or "—"),
            "Ожидаемое действие: %s" % (ts.expected or "—"),
            "На паузе: %s" % ("да" if ts.paused else "нет"),
            "",
            "Новое сообщение пользователя: " + str(question or ""),
        ]
        if answer:
            lines += ["", "Ответ ассистента (кратко): " + str(answer)[:500]]
        lines += [
            "",
            "Верни СТРОГО JSON-объект с полями:",
            '  "stage": один из planning|execution|validation|done;',
            '  "step": краткое описание текущего шага;',
            '  "expected": что ожидается дальше (действие/ввод);',
            '  "note": короткое пояснение перехода.',
            "Разрешённые переходы: planning->execution;",
            "execution->validation; validation->done или validation->execution",
            "(если проверка нашла недочёт). Этап может остаться тем же.",
            "Только JSON, без пояснений и markdown.",
        ]
        prompt = "\n".join(lines)
        provider, model_name = self._resolve_model(model)
        try:
            res = self._chat_text(provider, model_name, [
                {"role": "system",
                 "content": "Ты ведёшь состояние задачи и отвечаешь строго JSON."},
                {"role": "user", "content": prompt},
            ], temperature=0.1)
            content = res.get("content", "") if isinstance(res, dict) else str(res)
            data = parse_facts_json(content)
            if not isinstance(data, dict):
                return {}
            stage = str(data.get("stage", "")).strip().lower()
            if stage not in STAGES:
                return {}
            return {
                "stage": stage,
                "step": str(data.get("step", "") or ""),
                "expected": str(data.get("expected", "") or ""),
                "note": str(data.get("note") or ""),
            }
        except Exception as exc:
            print("[TASK] не удалось определить переход: %s" % exc, flush=True)
            return {}
