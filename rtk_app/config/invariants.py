"""
Настройки инвариантов (жёстких правил).

Инварианты — ограничения (архитектура, техрешения, стек, бизнес-правила),
которые ассистент НЕ вправе нарушать. При конфликте — отказ с пояснением.
"""
from .strategies import *  # для VALID_STRATEGIES

INVARIANT_CATEGORIES = (
    ("architecture", "Архитектура"),
    ("tech", "Технические решения"),
    ("stack", "Ограничения по стеку"),
    ("business", "Бизнес-правила"),
)
INVARIANT_TEXT_CAP = 500
INVARIANT_MAX = 100
INVARIANT_CHECK_MODEL = "GigaChat"
