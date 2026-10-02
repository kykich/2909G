"""
Настройки RAG (Retrieval-Augmented Generation).

Содержит:
  - Путь к папке с документами
  - Параметры чанкинга
  - Параметры поиска (top-k, порог релевантности)
  - Параметры встраиваний (модель Ollama)
  - Путь к хранилищу ChromaDB
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Путь к папке с документами (задаёт пользователь в UI) ---
RAG_DOCS_DIR = ""

# --- Встраивания: модель Ollama ---
RAG_EMBED_MODEL = "nomic-embed-text-v2-moe"
RAG_OLLAMA_URL = "http://127.0.0.1:11434"

# --- Чанкинг ---
RAG_CHUNK_SIZE = 512       # размер чанка в токенах (приблизительно в символах)
RAG_CHUNK_OVERLAP = 64     # перекрытие между чанками

# --- Поиск ---
RAG_TOP_K = 5              # сколько чанков искать
RAG_SIMILARITY_THRESHOLD = 0.35  # минимальная косинусная близость (0..1)

# --- Хранилище ---
RAG_STORE_DIR = os.path.join(BASE_DIR, "session", "rag_store")

# --- Включение RAG по умолчанию ---
RAG_ENABLED = False
