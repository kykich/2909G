"""Агент чата — разбитый на модули.

Этот файл — точка входа. Реальная логика разбита по модулям:
  - agents/base.py        — константы, Ok, parse_facts_json
  - agents/llm_calls.py   — вызовы моделей, рендеринг
  - agents/mcp_agent.py   — MCP-ветка
  - agents/invariant_checker.py — проверка инвариантов
  - agents/task_agent.py  — управление задачами
  - agents/compact.py     — компактификация
  - agents/facts.py       — обновление фактов
  - agents/answer.py      — основной метод answer()
"""
from .agents.base import (
    Ok, SOURCES, SYSTEM_PROMPT, json_dumps_safe, parse_facts_json,
)

# Agent импортируется из agents.base — там собраны все миксины.
# Переопределяем класс Agent, объединяя все миксины.
from .agents.llm_calls import LLMCaller
from .agents.mcp_agent import MCPAgent
from .agents.invariant_checker import InvariantChecker
from .agents.task_agent import TaskAgent
from .agents.compact import CompactAgent
from .agents.facts import FactsAgent
from .agents.answer import AnswerAgent


class Agent(
    AnswerAgent,
    MCPAgent,
    InvariantChecker,
    TaskAgent,
    CompactAgent,
    FactsAgent,
    LLMCaller,
):
    """Единая точка общения пользователя с большими языковыми моделями.

    Состоит из миксинов:
      - AnswerAgent: answer() — основной метод
      - MCPAgent: answer_via_mcp(), compose_message()
      - InvariantChecker: check_invariants()
      - TaskAgent: advance_task(), task_system_prompt(), profile_system_prompt()
      - CompactAgent: compact_history(), compact_update(), _apply_compact()
      - FactsAgent: update_facts()
      - LLMCaller: _call_one(), _chat_text(), _resolve_model(), _build_messages()
    """

    def __init__(self, api_key, sources=None):
        """Создаёт агента.

        api_key — ключ DeepSeek; sources — последовательность кортежей
        (provider, model, label, css_class), если нужен свой набор моделей.
        """
        self.api_key = api_key
        self.sources = list(sources or SOURCES)
        self.enabled_models = [s[2] for s in self.sources]
        self.by_label = {s[2]: s for s in self.sources}

    @property
    def label(self):
        """Краткое описание состава агента (для интерфейса)."""
        return " | ".join(self.enabled_models)

    def available(self):
        """Список моделей, которые умеет обслуживать агент (метаданные для UI)."""
        out = []
        for provider, model, label, cls in self.sources:
            out.append({
                "label": label,
                "cls": cls,
                "provider": provider,
                "model": model,
            })
        return out


__all__ = ["Agent", "Ok", "SOURCES", "SYSTEM_PROMPT",
           "json_dumps_safe", "parse_facts_json"]
