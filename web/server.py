"""Встроенный HTTP-сервер (стандартная библиотека).

Тонкий entry-point: роутинг + создание сервера.
Вся логика вынесена в модули:
  - web/state.py        — глобальное состояние (агент, сессия, MCP)
  - web/mcp_settings.py — загрузка/сохранение настроек MCP
  - web/mcp_helpers.py  — вызовы MCP, напоминания, парсинг календаря
  - web/mcp_orchestrator.py — композиция пайплайна
  - web/handlers/       — HTTP-обработчики (GET/POST)
"""
import threading
import time
import webbrowser

from http.server import ThreadingHTTPServer

from rtk_app.agent import Agent
from rtk_app.session_store import SessionStore
from . import state
from .mcp_settings import load_mcp_settings
from .handlers.combined import WebRequestHandler
from .mcp_helpers import parse_calendar_events, mcp_text, collect_due_reminders, board_direct_result
from .mcp_orchestrator import composition_run as _composition_run, format_composition_message as _format_composition_message, composition_report_text
from . import state

# Backward-compat aliases for tests.
_parse_calendar_events = parse_calendar_events
_ServerState = state._ServerState

# mcp_client — опциональная зависимость; тесты мокают этот атрибут.
try:
    from rtk_app import mcp_client as _mc
    mcp_client = _mc
except Exception:
    mcp_client = None


def create_server(agent, host=None, port=None):
    """Создаёт HTTP-сервер, связанный с конкретным экземпляром агента."""
    if agent is None:
        raise ValueError("create_server: требуется экземпляр агента (Agent).")
    state.set_agent(agent)
    state._ServerState.session = SessionStore()
    from rtk_app import config
    addr = (host or config.WEB_HOST,
            config.WEB_PORT if port is None else port)
    return ThreadingHTTPServer(addr, WebRequestHandler)


def _open_browser_later(url, delay=1.0):
    def _job():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception as exc:
            print("[WEB] браузер: %s" % exc)
    threading.Thread(target=_job, daemon=True).start()


def serve(agent_or_key, host=None, port=None, open_page=True, agent=None):
    """Запускает сервер, используя агента в качестве единой сущности.

    agent_or_key — либо строка API-ключа DeepSeek (тогда создаётся агент),
    либо уже готовый экземпляр rtk_app.agent.Agent.
    agent — ещё один способ передать готового агента явно.
    """
    from rtk_app import config
    from .handlers.mcp_handler import _start_composition_tick

    if agent is None:
        agent = agent_or_key

    load_mcp_settings()

    if not isinstance(agent, Agent):
        agent = Agent(agent)

    httpd = create_server(agent, host, port)
    shown_host, shown_port = httpd.server_address[:2]
    url = "http://%s:%s/" % (shown_host, shown_port)
    print("[WEB] Сервер запущен: %s" % url)
    print("[WEB] Агент обслуживает модели: %s" % agent.label)
    if state._ServerState.composition_running and not state._ServerState.mcp_enabled:
        print("[COMPOSE] восстановлен режим композиции из настроек.", flush=True)
        _start_composition_tick()
    else:
        state._ServerState.composition_running = False
        print("[COMPOSE] режим композиции не активен (работают отдельные "
              "серверы по выбору).", flush=True)
    if open_page:
        _open_browser_later(url)
    print("[WEB] Остановка: нажмите Ctrl+C.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[WEB] Остановка...")
    finally:
        _stop_composition_tick()
        httpd.server_close()


def _stop_composition_tick():
    """Останавливает фоновый тик композиции."""
    from .handlers.mcp_handler import _stop_composition_tick as _stop
    _stop()


def main():
    """Точка входа: читает ключ, запускает сервер."""
    import sys
    from rtk_app.key_store import read_api_key
    from rtk_app import config
    try:
        api_key = read_api_key(config.DS_KEY_FILE)
        print("[OK] Ключ DeepSeek прочитан из %s" % config.DS_KEY_FILE)
    except FileNotFoundError:
        api_key = ""
        print("[!] Файл %s не найден. DeepSeek-flash в чате станет "
              "недоступен до тех пор, пока вы не впишете ключ в apidpsk.txt."
              % config.DS_KEY_FILE)
    args = sys.argv[1:]
    host, port = config.WEB_HOST, config.WEB_PORT
    if args and args[0].isdigit():
        port = int(args[0])
        if len(args) > 1:
            host = args[1]
    sys.exit(serve(api_key, host, port) or 0)
