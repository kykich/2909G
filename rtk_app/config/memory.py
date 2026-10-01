"""
Настройки памяти агента.

Память разделена на ТРИ типа:
  "short"    — краткосрочная: текущий диалог (messages/ветки);
  "working"  — рабочая: данные текущей задачи;
  "longterm" — долговременная: профиль, решения, знания.
"""

MEMORY_TYPES = ("short", "working", "longterm")
MEMORY_VALUE_CAP = 4000
MEMORY_MAX_KEYS = 200
