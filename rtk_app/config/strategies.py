"""
Стратегии управления контекстом.

Взаимоисключающие стратегии (переключаются в интерфейсе):
  "none"    — без стратегии: полная история;
  "sliding" — Sliding Window: только последние N сообщений;
  "facts"   — Sticky Facts: блок facts + последние N сообщений;
  "branch"  — Branching: независимые ветки от checkpoint.
"""

STRATEGY = "none"
STRATEGY_WINDOW = 10
BRANCH_DEFAULT_COUNT = 2
