"""RAG (Retrieval-Augmented Generation) — индексация и управление.

Центральный модуль:
  - index_documents() — индексация папки с документами
  - retrieve() — поиск релевантных чанков
  - get_status() — статус хранилища
"""
import os
import hashlib

from .loader import load_directory
from .embedder import embed_texts_batch
from .store import RagStore
from .retriever import chunk_text, retrieve as _retrieve, build_context

from rtk_app import config

__all__ = [
    "index_documents", "retrieve", "get_status", "reset_store",
    "build_context", "chunk_text",
]


def _get_store():
    """Возвращает экземпляр хранилища ChromaDB."""
    return RagStore(config.RAG_STORE_DIR)


def _make_chunk_id(file_path, chunk_index):
    """Создаёт уникальный ID для чанка."""
    raw = f"{file_path}:{chunk_index}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def index_documents(docs_dir=None):
    """Индексирует все документы в директории.

    docs_dir: путь к папке (если None — берётся из конфига).

    Возвращает dict:
      {
        "ok": True/False,
        "total_files": N,
        "total_chunks": N,
        "errors": [...],
        "detail": "...",
      }
    """
    if docs_dir is None:
        docs_dir = config.RAG_DOCS_DIR

    if not docs_dir or not os.path.isdir(docs_dir):
        return {
            "ok": False,
            "total_files": 0,
            "total_chunks": 0,
            "errors": ["Директория не указана или не существует"],
            "detail": "",
        }

    # Загружаем файлы
    files = load_directory(docs_dir)
    if not files:
        return {
            "ok": True,
            "total_files": 0,
            "total_chunks": 0,
            "errors": [],
            "detail": "Файлов для индексации не найдено.",
        }

    errors = []
    all_chunks = []
    file_ok_count = 0

    for f in files:
        if not f["ok"]:
            errors.append(f"{f['name']}: {f['error']}")
            continue

        file_ok_count += 1
        # Разбиваем на чанки
        chunks = chunk_text(
            f["text"],
            chunk_size=config.RAG_CHUNK_SIZE,
            overlap=config.RAG_CHUNK_OVERLAP,
        )

        for ci, chunk in enumerate(chunks):
            all_chunks.append({
                "id": _make_chunk_id(f["path"], ci),
                "text": chunk["text"],
                "metadata": {
                    "file": f["name"],
                    "chunk_index": ci,
                    "total_chunks": len(chunks),
                },
            })

    if not all_chunks:
        return {
            "ok": True,
            "total_files": file_ok_count,
            "total_chunks": 0,
            "errors": errors,
            "detail": "Файлы загружены, но чанков не создано (слишком короткие).",
        }

    # Создаём/очищаем хранилище
    store = _get_store()
    store.reset()

    # Пакетное встраивание
    texts = [c["text"] for c in all_chunks]
    embeddings = embed_texts_batch(texts, config.RAG_EMBED_MODEL)

    if embeddings is None:
        return {
            "ok": False,
            "total_files": file_ok_count,
            "total_chunks": len(all_chunks),
            "errors": ["Ошибка встраивания через Ollama"],
            "detail": "Ollama недоступен или модель не отвечает.",
        }

    # Сохраняем в ChromaDB
    store.add_with_embeddings(all_chunks, embeddings)

    return {
        "ok": True,
        "total_files": file_ok_count,
        "total_chunks": len(all_chunks),
        "errors": errors,
        "detail": f"Индексировано {file_ok_count} файлов, "
                  f"{len(all_chunks)} чанков.",
    }


def retrieve(query, top_k=None, threshold=None):
    """Ищет релевантные чанки для запроса.

    Возвращает список dict с полями text, metadata, similarity.
    """
    if top_k is None:
        top_k = config.RAG_TOP_K
    if threshold is None:
        threshold = config.RAG_SIMILARITY_THRESHOLD

    store = _get_store()
    if store.count() == 0:
        return []

    return _retrieve(
        store, query,
        top_k=top_k,
        threshold=threshold,
        model=config.RAG_EMBED_MODEL,
    )


def build_context(matches, max_tokens=2000):
    """Формирует контекст из найденных чанков."""
    return build_context(matches, max_tokens)


def get_status():
    """Возвращает статус RAG-хранилища."""
    store = _get_store()
    status = store.get_status()
    status["docs_dir"] = config.RAG_DOCS_DIR
    status["enabled"] = config.RAG_ENABLED
    return status


def reset_store():
    """Сбрасывает хранилище (удаляет все документы)."""
    store = _get_store()
    store.reset()
    return {"ok": True, "detail": "Хранилище сброшено."}
