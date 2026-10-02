"""
Настройки веб-сервера: хост, порт, корень.
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WEB_HOST = "127.0.0.1"
WEB_PORT = 8000
WEB_ROOT = BASE_DIR
