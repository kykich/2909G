"""Объединённый HTTP-обработчик.

Собирает do_GET из StaticHandler и do_POST из AskHandler (который делегирует
остальное ApiHandler, которая делегирует McpHandler). Все классы-миксины + BaseHandler.
"""
from http.server import BaseHTTPRequestHandler
from .base import BaseHandler
from .static_handler import StaticHandler
from .ask_handler import AskHandler
from .api_handler import ApiHandler
from .mcp_handler import McpHandler


class WebRequestHandler(BaseHandler, StaticHandler, AskHandler, ApiHandler, McpHandler, BaseHTTPRequestHandler):
    """Объединённый обработчик: наследует do_GET и do_POST."""
    pass
