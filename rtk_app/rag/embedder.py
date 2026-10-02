"""Встраивания (embeddings) через Ollama API.

Использует локальную модель nomic-embed-text-v2-moe.
Эндпоинт: POST /api/embed
"""
import json

__all__ = ["embed_text", "embed_texts_batch"]


def _ollama_post(path, data, timeout=60):
    """Отправляет POST-запрос к Ollama API."""
    import urllib.request
    url = f"http://127.0.0.1:11434{path}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Ollama API error: {exc}")


def embed_text(text, model="nomic-embed-text-v2-moe"):
    """Встраивает один текст.

    Возвращает список float (вектор) или None при ошибке.
    """
    try:
        result = _ollama_post("/api/embeddings", {
            "model": model,
            "prompt": text,
        })
        if isinstance(result, dict) and "embedding" in result:
            return result["embedding"]
        return None
    except Exception:
        return None


def embed_texts_batch(texts, model="nomic-embed-text-v2-moe"):
    """Встраивает список текстов (пакетно).

    Возвращает список списков float или None при ошибке.
    """
    try:
        # Ollama не поддерживает пакетные embeddings через /api/embeddings,
        # поэтому вызываем по одному
        results = []
        for text in texts:
            vec = embed_text(text, model)
            if vec is not None:
                results.append(vec)
            else:
                results.append([0.0] * 768)  # fallback zero vector
        return results
    except Exception:
        return None
