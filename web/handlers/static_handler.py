"""Обработчик статических файлов и GET-запросов к API (mixin)."""
import urllib.parse

from rtk_app import config


class StaticHandler:
    """Обработка GET-запросов: статика и GET-эндпоинты API."""

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
        if path in ("/", "/index.html"):
            return self._serve_static_safe("index.html")
        if path.startswith(("/css/", "/js/")):
            return self._serve_static_safe(path.lstrip("/"))
        if path == "/api/model":
            return self._send_json(200, {
                "ok": True,
                "model": self.agent.label if self.agent else config.MODEL,
                "models": [m["label"] for m in
                           (self.agent.available() if self.agent else [])],
                "available": (self.agent.available() if self.agent else []),
            })
        if path == "/api/session":
            has = self.session.has_history()
            return self._send_json(200, {
                "ok": True,
                "has_history": has,
                "messages": self.session.snapshot(),
                "compact": self.session.get_compact(),
                "context": self.session.context_stats(),
                "strategy": self.session.get_strategy(),
                "facts": self.session.get_facts(),
                "branches": self.session.branches_state(),
                "memory": self.session.memory_state(),
                "task": self.session.get_task_state(),
                "invariants": self.session.invariants_state(),
                "profiles": self.session.profiles_state(),
            })
        if path == "/api/profiles":
            state = self.session.profiles_state()
            return self._send_json(200, {
                "ok": True,
                "profiles": state["profiles"],
                "active": state["active"],
            })
        if path == "/api/invariants":
            return self._send_json(200, self.session.invariants_state())
        if path == "/api/mcp":
            from ..mcp_settings import mcp_state_payload
            return self._send_json(200, mcp_state_payload(check=False))
        self._send_json(404, {"ok": False, "error": "Not Found"})
