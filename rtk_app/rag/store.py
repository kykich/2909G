"""Хранилище ChromaDB для RAG.

Персистентное хранилище векторных встраиваний с метаданными.
"""
import os

__all__ = ["RagStore"]


class RagStore:
    """Обёртка над ChromaDB для RAG-документов."""

    def __init__(self, persist_directory, collection_name="documents"):
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self._client = None
        self._collection = None

    @property
    def client(self):
        if self._client is None:
            import chromadb
            os.makedirs(self.persist_directory, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=self.persist_directory
            )
        return self._client

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def add_documents(self, documents):
        """Добавляет документы в коллекцию.

        documents: список dict с полями:
          - id: str (уникальный ID)
          - text: str (текст чанка)
          - metadata: dict (файл, chunk_index и т.д.)
        """
        if not documents:
            return 0

        ids = [d["id"] for d in documents]
        texts = [d["text"] for d in documents]
        metadatas = [d.get("metadata", {}) for d in documents]

        # ChromaDB требует embeddings на этапе добавления
        # (используем пустые, заполним позже при индексации)
        self.collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
            embeddings=[],  # заполним позже
        )
        return len(ids)

    def add_with_embeddings(self, documents, embeddings):
        """Добавляет документы с готовыми встраиваниями.

        documents: список dict
        embeddings: список списков float (должен совпадать по длине с documents)
        """
        if not documents or not embeddings:
            return 0

        ids = [d["id"] for d in documents]
        texts = [d["text"] for d in documents]
        metadatas = [d.get("metadata", {}) for d in documents]

        self.collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        return len(ids)

    def query(self, query_embedding, top_k=5, where=None):
        """Ищет похожие чанки по вектору запроса.

        Возвращает dict:
          {
            "ids": [...],
            "documents": [...],
            "metadatas": [...],
            "distances": [...],  # косинусное расстояние (0 = идеально)
            "similarity": [...],  # 1 - distance
          }
        """
        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self.count()),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        if not result["ids"] or not result["ids"][0]:
            return {"ids": [], "documents": [], "metadatas": [],
                    "distances": [], "similarity": []}

        distances = result["distances"][0]
        similarities = [1.0 - d for d in distances]

        return {
            "ids": result["ids"][0],
            "documents": result["documents"][0],
            "metadatas": result["metadatas"][0],
            "distances": distances,
            "similarity": similarities,
        }

    def count(self):
        """Возвращает число документов в коллекции."""
        return self.collection.count()

    def reset(self):
        """Удаляет коллекцию и создаёт заново."""
        if self._client:
            self._client.delete_collection(self.collection_name)
            self._collection = None

    def get_status(self):
        """Возвращает статус хранилища."""
        return {
            "ok": True,
            "count": self.count(),
            "directory": self.persist_directory,
        }
