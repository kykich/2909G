"""Базовые утилиты, константы и класс Ok для агента."""
import json

from .. import config

__all__ = ["SOURCES", "SYSTEM_PROMPT", "json_dumps_safe", "parse_facts_json", "Ok"]


def json_dumps_safe(obj):
    """Аккуратно сериализует объект в JSON (для промптов)."""
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)


def parse_facts_json(text):
    """Извлекает словарь фактов (key-value) из ответа модели.

    Принимает строку, возможно с обрамлением в markdown-блок ```json … ```.
    Возвращает dict строк или None, если разобрать не удалось.
    """
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
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    frag = s[start:end + 1]
    try:
        data = json.loads(frag)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return {str(k): ("" if v is None else str(v)) for k, v in data.items()}


# Источники "голосов": (провайдер, имя модели, метка для отображения, css-класс)
SOURCES = (
    ("deepseek", config.DS_MODELS[0], "DeepSeek-flash", "ds-flash"),
    ("gigachat", config.GC_MODEL, "GigaChat", "gc-base"),
)

# Системный промпт агента (роль). Ставится в начало каждого диалога.
SYSTEM_PROMPT = ("Ты — дружелюбный ассистент. Отвечай по-русски, понятно и "
                 "структурированно, следуя запросам пользователя.")


class Ok:
    """Маленький помощник конструирования единообразного результата агента."""

    def __init__(self, agent):
        self.agent = agent

    def value(self, **kwargs):
        d = {"ok": False, "html": "", "text": "", "answers": [],
             "meta": "", "model": self.agent.label,
             "usage": {"input": 0, "output": 0, "total": 0, "history": 0}}
        d.update(kwargs)
        d.setdefault("error", None)
        return d

    def error(self, message):
        return self.value(ok=False, error=message)
