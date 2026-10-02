"""Поиск релевантных чанков (retriever).

Использует встраивания и ChromaDB для семантического поиска.
"""
import math

__all__ = ["retrieve", "chunk_text"]


def chunk_text(text, chunk_size=512, overlap=64):
    """Разбивает текст на перекрывающиеся чанки.

    Возвращает список dict:
      [
        {"text": "...", "index": 0},
        {"text": "...", "index": 1},
        ...
      ]
    """
    if not text:
        return []

    chunks = []
    start = 0
    idx = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end]

        # Пытаемся разбить по предложению/абзацу
        if end < text_len:
            # Ищем ближайшую точку конца предложения
            last_period = chunk.rfind(". ")
            last_newline = chunk.rfind("\n")
            split_pos = max(last_period + 2, last_newline)
            if split_pos > chunk_size * 0.5:
                chunk = chunk[:split_pos].rstrip()

        chunks.append({"text": chunk, "index": idx})
        idx += 1
        start = end - overlap

    return chunks


def _cosine_similarity(a, b):
    """Вычисляет косинусное сходство двух векторов."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def retrieve(store, query, top_k=5, threshold=0.35, model="nomic-embed-text-v2-moe"):
    """Ищет релевантные чанки для запроса.

    store: RagStore
    query: str — текст запроса
    top_k: int — макс. число результатов
    threshold: float — минимальное сходство (0..1)
    model: str — модель Ollama для встраиваний

    Возвращает список dict:
      [
        {
          "text": "...",
          "metadata": {...},
          "similarity": 0.85,
        },
        ...
      ]
    """
    from .embedder import embed_text

    # Встраиваем запрос
    query_vec = embed_text(query, model)
    if not query_vec:
        return []

    # Ищем в ChromaDB
    result = store.query(query_vec, top_k=top_k)

    # Фильтруем по порогу
    matches = []
    for i, sim in enumerate(result.get("similarity", [])):
        if sim >= threshold:
            matches.append({
                "text": result["documents"][i],
                "metadata": result["metadatas"][i],
                "similarity": round(sim, 4),
            })

    # Сортируем по убыванию сходства
    matches.sort(key=lambda m: m["similarity"], reverse=True)
    return matches


def build_context(matches, max_tokens=2000):
    """Формирует контекст из найденных чанков для вставки в промпт.

    Возвращает строку, готовую для вставки в system-промпт.
    """
    if not matches:
        return ""

    parts = []
    total_len = 0
    for i, m in enumerate(matches, 1):
        chunk_text = m.get("text", "")
        meta = m.get("metadata", {})
        source = meta.get("file", "неизвестно")
        sim = m.get("similarity", 0)

        parts.append(
            f"[{i}] Источник: {source} | Сходство: {sim:.3f}\n{chunk_text}"
        )
        total_len += len(parts[-1])
        if total_len > max_tokens * 3:  # примерная оценка
            break

    return "\n\n".join(parts)
