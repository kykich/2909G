"""Обработчик POST /api/mcp — управление MCP и композицией."""
import threading
import urllib.parse

from rtk_app import config
from ..mcp_settings import mcp_state_payload, save_mcp_settings
from ..mcp_orchestrator import composition_run, format_composition_message, composition_report_text
from .. import state as srv_state


class McpHandler:
    """Миксин: обработчик POST /api/mcp + фоновый тик композиции."""

    def _handle_mcp(self):
        """Управление MCP: чтение/запись настроек и проверка статуса."""
        data = self._read_json_body() or {}
        action = str(data.get("action", "state")).strip().lower()

        if action == "set":
            with srv_state._ServerState.mcp_lock:
                if "enabled" in data and bool(data.get("enabled")):
                    if srv_state._ServerState.composition_running:
                        srv_state._ServerState.composition_running = False
                        _stop_composition_tick()
                        print("[MCP] включён режим MCP — композиция остановлена.",
                              flush=True)
                if "enabled" in data:
                    srv_state._ServerState.mcp_enabled = bool(data.get("enabled"))
                if "model" in data:
                    srv_state._ServerState.mcp_model = str(data.get("model") or "")
                if "server" in data:
                    srv_state._ServerState.mcp_server = str(data.get("server") or "")
                save_mcp_settings()
            return self._send_json(200, mcp_state_payload(check=False))

        if action == "status":
            return self._send_json(200, mcp_state_payload(check=True))

        if action == "compose":
            with srv_state._ServerState.mcp_lock:
                srv_state._ServerState.mcp_enabled = False
                srv_state._ServerState.composition_running = True
                save_mcp_settings()
            _start_composition_tick()
            report = composition_run(verbose=True)
            payload = mcp_state_payload(check=False)
            payload["composition"] = report
            template = format_composition_message(report)
            chooser = getattr(self, "agent", None)
            model_label = srv_state._ServerState.mcp_model or ""
            if chooser is not None and hasattr(chooser, "compose_message"):
                gen = chooser.compose_message(
                    composition_report_text(report), model=model_label or None,
                    fallback=template)
                payload["composition_message"] = gen.get("text") or template
                payload["composition_message_model"] = gen.get("model") or ""
                payload["composition_message_ok"] = bool(gen.get("ok"))
            else:
                payload["composition_message"] = template
                payload["composition_message_model"] = ""
                payload["composition_message_ok"] = False
            print("[COMPOSE] композиция запущена (MCP выключен); сообщение "
                  "сформировано моделью %r (ok=%s)"
                  % (payload.get("composition_message_model") or "шаблон",
                     payload.get("composition_message_ok")), flush=True)
            return self._send_json(200, payload)

        if action == "compose_stop":
            with srv_state._ServerState.mcp_lock:
                srv_state._ServerState.composition_running = False
                _stop_composition_tick()
                save_mcp_settings()
            print("[COMPOSE] режим композиции остановлен.", flush=True)
            return self._send_json(200, mcp_state_payload(check=False))

        return self._send_json(200, mcp_state_payload(check=False))


# ---------------------------------------------------------------------------
# Фоновый тик композиции
# ---------------------------------------------------------------------------

def _composition_tick_loop(interval, stop_event):
    """Фоновый ТИК композиции: раз в interval секунд прогоняет пайплайн."""
    from ..mcp_orchestrator import composition_run
    print("[COMPOSE] фоновый тик композиции: каждые %d c." % interval, flush=True)
    while not stop_event.is_set():
        if stop_event.wait(interval):
            break
        if not srv_state._ServerState.composition_running:
            break
        try:
            report = composition_run(verbose=False)
            if not report.get("ok"):
                print("[COMPOSE] тик: %s" % report.get("error"), flush=True)
        except Exception as exc:
            print("[COMPOSE] тик не удался: %s" % exc, flush=True)
    print("[COMPOSE] фоновый тик композиции остановлен.", flush=True)


def _start_composition_tick():
    """Запускает фоновый тик композиции (режим композиции ВКЛючён)."""
    interval = int(getattr(config, "COMPOSITION_TICK_SECONDS", 0) or 0)
    if interval <= 0:
        print("[COMPOSE] фоновый тик выключен (COMPOSITION_TICK_SECONDS=0).",
              flush=True)
        return
    if srv_state._ServerState.composition_thread and srv_state._ServerState.composition_thread.is_alive():
        return
    stop_event = threading.Event()
    srv_state._ServerState.composition_stop = stop_event
    th = threading.Thread(target=_composition_tick_loop,
                           args=(interval, stop_event), daemon=True)
    srv_state._ServerState.composition_thread = th
    th.start()


def _stop_composition_tick():
    """Останавливает фоновый тик композиции (режим композиции ВЫКЛючён)."""
    stop_event = srv_state._ServerState.composition_stop
    if stop_event is not None:
        stop_event.set()
    srv_state._ServerState.composition_stop = None
    srv_state._ServerState.composition_thread = None
