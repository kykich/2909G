"""
Пакет конфигурации rtk_app.config.

Все публичные константы переэкспортируются из подмодулей для
обратной совместимости. Любой код, использующий
`from rtk_app.config import X` или `config.X`, продолжает работать.

Подмодули:
  api         — DeepSeek / GigaChat API (эндпоинты, ключи, модели, цены)
  web         — хост, порт, корень
  compact     — сжатие истории (summary, keep, cap)
  strategies  — стратегии контекста (none/sliding/facts/branch)
  memory      — лимиты памяти
  profiles    — профили (персоны)
  invariants  — инварианты (жёсткие правила)
  mcp         — MCP-серверы, композиция
  calendar    — Яндекс.Календарь (CalDAV)
"""

from .api import (
    DS_API_URL, DS_KEY_FILE, DS_MODELS,
    GC_KEY_FILE, GC_TOKEN_URL, GC_API_BASE, GC_SCOPE,
    GC_MODEL, GC_TOKEN_TTL,
    DS_PRICE_INPUT_PER_M, DS_PRICE_OUTPUT_PER_M,
    KEY_FILE, API_URL, MODEL,
    REQUEST_TIMEOUT,
)
from .web import (
    WEB_HOST, WEB_PORT, WEB_ROOT,
)
from .compact import (
    COMPACT_ENABLED, COMPACT_MIN, COMPACT_MSG_CAP, COMPACT_MODEL,
)
from .strategies import (
    STRATEGY, STRATEGY_WINDOW, BRANCH_DEFAULT_COUNT,
)
from .memory import (
    MEMORY_TYPES, MEMORY_VALUE_CAP, MEMORY_MAX_KEYS,
)
from .profiles import (
    PROFILES_FILE, PROFILE_NAME_CAP, PROFILE_ATTR_CAP, PROFILE_MAX,
)
from .invariants import (
    INVARIANT_CATEGORIES, INVARIANT_TEXT_CAP, INVARIANT_MAX, INVARIANT_CHECK_MODEL,
)
from .mcp import (
    MCP_ENABLED, MCP_SERVER_CMD, MCP_SERVER_ARGS, MCP_TIMEOUT,
    MCP_SERVER_DEFAULT, MCP_MODEL, MCP_SETTINGS_FILE,
    MCP_SERVERS,
    COMPOSITION_CALENDAR_SERVER, COMPOSITION_ZAMPOLIT_SERVER,
    COMPOSITION_ZAVHOZ_SERVER, COMPOSITION_TICK_SECONDS,
    COMPOSITION_DAYS_AHEAD, COMPOSITION_CALL_TIMEOUT,
    COMPOSITION_DOSKA_SERVER, COMPOSITION_SERVERS,
)
from .calendar import (
    YANDEX_CALDAV_URL, YA_CRED_FILE, CALENDAR_TZ,
)
from .rag import (
    RAG_DOCS_DIR, RAG_EMBED_MODEL, RAG_OLLAMA_URL,
    RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP,
    RAG_TOP_K, RAG_SIMILARITY_THRESHOLD,
    RAG_STORE_DIR, RAG_ENABLED,
)

# --- Параметры генерации по умолчанию ---
DEFAULT_TEMPERATURE = 0.7
TEMP_MIN = 0.0
TEMP_MAX = 1.0
TEMP_STEP = 0.05

# --- Максимальное число новых токенов (max_tokens) ---
DEFAULT_MAX_TOKENS = 2048
MAX_TOKENS_MIN = 1
MAX_TOKENS_MAX = 100000
MAX_TOKENS_STEP = 50

# --- Сессии диалога ---
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION_DIR = os.path.join(BASE_DIR, "..", "session")
SESSION_FILE = os.path.join(SESSION_DIR, "session.json")

# --- Сжатие истории: keep = 0 означает «сжатие не применять» ---
COMPACT_KEEP = 0

# --- Валидные стратегии ---
VALID_STRATEGIES = ("none", "sliding", "facts", "branch")
