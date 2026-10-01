"""Состояние сервера и настройки MCP.

Глобальное состояние HTTP-сервера: агент, сессия, настройки MCP, композиция.
Выносится из web/server.py для уменьшения его размера.
"""
import threading


class _ServerState:
    """Глобальное состояние сервера: агент (единая сущность) и сессия."""
    agent = None
    session = None
    # Настройки MCP (включается чекбоксом в левой колонке):
    #   enabled — использовать ли инструменты MCP;
    #   model   — метка модели, применяемой при работе с MCP;
    #   status  — последний результат проверки статуса MCP-сервера.
    mcp_enabled = False
    mcp_model = ""
    # id выбранного MCP-сервера (см. config.MCP_SERVERS).
    mcp_server = "calendar"
    mcp_status = None
    mcp_lock = threading.Lock()
    # КОМПОЗИЦИЯ MCP: запущена ли она сейчас.
    # ВАЖНО: композиция и режим «Использовать MCP» — ВЗАИМОИСКЛЮЧАЮЩИЕ.
    #   * запуск композиции — выключает чекбокс «Использовать MCP»
    #     (композиция работает сама по себе);
    #   * включение чекбокса «Использовать MCP» — останавливает композицию
    #     и переводит сервер в режим отдельных серверов по выбору.
    composition_running = False
    # Поток фонового ТИКА композиции (запускается только в режиме композиции).
    composition_thread = None
    # Событие остановки тика композиции (устанавливается при выключении).
    composition_stop = None


def set_agent(agent):
    """Запоминает агента, который обслуживает все запросы."""
    _ServerState.agent = agent


def ensure_session(session_store_class, path=None):
    """Лениво создаёт единственное хранилище сессии диалога."""
    if _ServerState.session is None:
        _ServerState.session = session_store_class(path)
    return _ServerState.session
