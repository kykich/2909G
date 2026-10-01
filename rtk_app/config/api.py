"""
Настройки API: DeepSeek и GigaChat.

Содержит эндпоинты, файлы ключей, модели, цены и таймауты.
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- DeepSeek ---
DS_API_URL = "https://api.deepseek.com/chat/completions"
DS_KEY_FILE = os.path.join(BASE_DIR, "apidpsk.txt")
DS_MODELS = [
    "deepseek-flash",
]

# --- GigaChat (облачный Сбер) ---
GC_KEY_FILE = os.path.join(BASE_DIR, "gigakey.txt")
GC_TOKEN_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
GC_API_BASE = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
GC_SCOPE = "GIGACHAT_API_PERS"
GC_MODEL = "GigaChat"
GC_TOKEN_TTL = 1500

# --- Цены DeepSeek, юань за 1М токенов ---
DS_PRICE_INPUT_PER_M = {"deepseek-flash": 1.5}
DS_PRICE_OUTPUT_PER_M = {"deepseek-flash": 4.5}

# --- Alias / метки (для обратной совместимости) ---
KEY_FILE = DS_KEY_FILE
API_URL = DS_API_URL
MODEL = "DeepSeek-flash | GigaChat"

# --- Таймаут запросов ---
REQUEST_TIMEOUT = 90
