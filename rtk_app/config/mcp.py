"""
Настройки MCP (Model Context Protocol).

Содержит:
  - Включение/выключение MCP
  - Список MCP-серверов
  - Таймауты
  - Файл настроек
  - Параметры композиции (пайплайн календарь → замполит → завхоз)
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Базовые настройки MCP ---
MCP_ENABLED = False
MCP_SERVER_CMD = ""
MCP_SERVER_ARGS = ["yandex_calendar_server.py"]
MCP_TIMEOUT = 30
MCP_SERVER_DEFAULT = "calendar"
MCP_MODEL = ""
MCP_SETTINGS_FILE = os.path.join(os.path.join(BASE_DIR, "session"), "mcp.json")

# --- Список доступных MCP-серверов ---
MCP_SERVERS = [
    {"id": "calendar", "label": "Яндекс.Календарь (CalDAV)",
     "args": ["yandex_calendar_server.py"]},
    {"id": "currency", "label": "Время",
     "args": ["currency_server.py"]},
    {"id": "weather", "label": "Погода",
     "args": ["weather_server.py"]},
    {"id": "zampolit", "label": "Замполит",
     "args": ["zampolit_server.py"]},
    {"id": "zavhoz", "label": "Завхоз",
     "args": ["zavhoz_server.py"]},
    {"id": "doska", "label": "Доска",
     "args": ["doska_server.py"]},
]

# --- КОМПОЗИЦИЯ MCP ---
COMPOSITION_CALENDAR_SERVER = "calendar"
COMPOSITION_ZAMPOLIT_SERVER = "zampolit"
COMPOSITION_ZAVHOZ_SERVER = "zavhoz"
COMPOSITION_TICK_SECONDS = 60
COMPOSITION_DAYS_AHEAD = 7
COMPOSITION_CALL_TIMEOUT = 30
COMPOSITION_DOSKA_SERVER = "doska"

COMPOSITION_SERVERS = [
    {"id": "calendar", "label": "Календарь",
     "desc": "смотрит события на ближайшие 7 дней"},
    {"id": "currency", "label": "Время",
     "desc": "время от начала дня (HH:MM:SS, минуты, десятичные часы)"},
    {"id": "zampolit", "label": "Замполит",
     "desc": "по времени события выбирает формат (до 12:00 — минуты, "
            "после — часы, весь день — HH:MM:SS)"},
    {"id": "zavhoz", "label": "Завхоз",
     "desc": "сохраняет пары «событие + время» в JSON-файл"},
    {"id": "doska", "label": "Доска",
     "desc": "по запросу выводит таблицу «событие ↔ время»"},
]
