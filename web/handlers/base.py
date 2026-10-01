"""Базовый класс HTTP-обработчика с общими методами."""
import json
import mimetypes
import os
import urllib.parse

from rtk_app import config
from .. import state


class BaseHandler:
    """Базовый класс для HTTP-обработчиков."""
    server_version = "MultiModelChat/1.0"

    @property
    def agent(self):
        """Единый агент (rtk_app.agent.Agent), созданный при запуске сервера."""
        return state._ServerState.agent

    @property
    def session(self):
        """Хранилище сессии диалога."""
        return state._ServerState.session

    def _send_bytes(self, status, body, content_type):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status, obj):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, payload, "application/json; charset=utf-8")

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return None
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def _serve_static_safe(self, rel):
        root_real = os.path.realpath(config.WEB_ROOT)
        full = os.path.realpath(os.path.join(root_real, os.path.normpath(rel)))
        if not (full.startswith(root_real + os.sep) or full == root_real):
            return self._send_bytes(403, "Forbidden", "text/plain")
        if not os.path.isfile(full):
            return self._send_bytes(404, "Not Found", "text/plain")
        ctype, _ = mimetypes.guess_type(full)
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
