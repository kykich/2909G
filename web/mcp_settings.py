"""Настройки и состояние MCP (загрузка/сохранение, payload, проверка статуса).

Модуль отвечает за:
- Загрузку/сохранение настроек MCP из файла
- Формирование JSON-payload для клиента
- Проверку статуса MCP-сервера
"""
import json
import os

from . import state
from rtk_app import config

try:
    from rtk_app import mcp_client
except Exception:
    mcp_client = None


def _mcp_settings_file():
    """Путь к файлу настроек MCP (в папке сессии)."""
    return getattr(config, "MCP_SETTINGS_FILE", None)


def load_mcp_settings():
    """Загружает настройки MCP из файла (если есть), заполняя состояние."""
    path = _mcp_settings_file()
    if not path or not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            state._ServerState.mcp_enabled = bool(data.get("enabled",
                                                   state._ServerState.mcp_enabled))
            model = data.get("model")
            if isinstance(model, str):
                state._ServerState.mcp_model = model
            server = data.get("server")
            if isinstance(server, str) and server:
                state._ServerState.mcp_server = server
            # Режим композиции (взаимоисключающий с MCP).
            comp = data.get("composition")
            if comp is not None:
                state._ServerState.composition_running = bool(comp)
    except Exception as exc:
        print("[MCP] не удалось загрузить настройки: %s" % exc, flush=True)


def save_mcp_settings():
    """Сохраняет настройки MCP на диск (в папку сессии)."""
    path = _mcp_settings_file()
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"enabled": state._ServerState.mcp_enabled,
                       "model": state._ServerState.mcp_model,
                       "server": state._ServerState.mcp_server,
                       "composition": state._ServerState.composition_running}, f,
                       ensure_ascii=False, indent=2)
    except Exception as exc:
        print("[MCP] не удалось сохранить настройки: %s" % exc, flush=True)


def mcp_state_payload(check=False):
    """Собирает состояние MCP для ответа клиенту.

    check=True — предварительно ПРОВЕРЯЕТ статус сервера (подключение +
    список инструментов) и обновляет сохранённый статус.
    """
    if check:
        state._ServerState.mcp_status = probe_mcp_status()
    status = state._ServerState.mcp_status
    servers = []
    if mcp_client is not None:
        try:
            servers = mcp_client.mcp_servers()
        except Exception:
            servers = []
    return {
        "ok": True,
        "enabled": bool(state._ServerState.mcp_enabled),
        "model": state._ServerState.mcp_model or "",
        "server": state._ServerState.mcp_server or "",
        "servers": servers,
        "available": mcp_client is not None,
        "status": status,
        # Режим композиции (взаимоисключающий с «Использовать MCP»).
        "composition_running": bool(state._ServerState.composition_running),
    }


def probe_mcp_status():
    """Проверяет статус MCP-сервера (через mcp_client.mcp_status)."""
    if mcp_client is None:
        return {"ok": False, "connected": False, "tools_count": 0,
                "tools": [], "server": "",
                "error": "MCP-клиент недоступен (не установлен пакет mcp)."}
    try:
        return mcp_client.mcp_status(server_id=(state._ServerState.mcp_server or None))
    except Exception as exc:
        return {"ok": False, "connected": False, "tools_count": 0,
                "tools": [], "server": "", "error": str(exc)}
