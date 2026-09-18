"""
Vector Database for Sage Multi-Agentic AI Architecture.
Provides semantic search, embedding generation, and document indexing
using pure-Python normalized term-frequency vectors and cosine similarity.
"""
import re
import math
import logging
from collections import Counter
from typing import List, Dict, Any, Optional

from database.db_manager import get_db

logger = logging.getLogger(__name__)


class VectorDatabase:
    """Lightweight pure-Python semantic vector database with SQLite persistence."""

    def __init__(self):
        self._db = get_db()
        self._vocabulary: Dict[str, int] = {}
        self._doc_vectors: Dict[str, Dict[str, Any]] = {}
        self._load_from_db()

    def _tokenize(self, text: str) -> List[str]:
        words = re.findall(r"\b[a-zA-Z0-9_]{2,}\b", text.lower())
        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with",
            "is", "was", "are", "were", "be", "been", "this", "that", "it", "of", "from"
        }
        return [w for w in words if w not in stopwords]

    def _load_from_db(self):
        try:
            records = self._db.get_all_vector_knowledge()
            for r in records:
                self._doc_vectors[r["id"]] = {
                    "title": r["title"],
                    "content": r["content"],
                    "tags": r.get("tags"),
                    "embedding": r.get("embedding", [])
                }
        except Exception as e:
            logger.debug("Error loading vector knowledge: %s", e)

    def embed_text(self, text: str, dimension: int = 128) -> List[float]:
        """
        Generates a deterministic normalized term frequency hash embedding vector.
        Uses feature hashing (the hashing trick) for fixed-length dense representations.
        """
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * dimension

        vec = [0.0] * dimension
        counts = Counter(tokens)
        total = float(len(tokens))

        for token, count in counts.items():
            # Hash into dimension space
            h = hash(token) % dimension
            sign = 1.0 if (hash(token + "_sign") % 2 == 0) else -1.0
            tf = (count / total) * math.log(1.0 + total)
            vec[h] += sign * tf

        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0.0:
            vec = [round(v / norm, 5) for v in vec]
        return vec

    @staticmethod
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        return max(0.0, min(1.0, dot))

    def add_document(
        self,
        doc_id: str,
        title: str,
        content: str,
        tags: Optional[str] = None
    ) -> List[float]:
        """Indexes a document chunk and persists its embedding."""
        full_text = f"{title} {content} {tags or ''}"
        vector = self.embed_text(full_text)

        self._doc_vectors[doc_id] = {
            "title": title,
            "content": content,
            "tags": tags,
            "embedding": vector
        }

        try:
            self._db.save_vector_knowledge(
                doc_id=doc_id,
                title=title,
                content=content,
                embedding_vector=vector,
                tags=tags
            )
        except Exception as e:
            logger.warning("Could not persist vector document %s: %s", doc_id, e)

        return vector

    def search(self, query: str, top_k: int = 5, min_score: float = 0.05) -> List[Dict[str, Any]]:
        """Finds most semantically relevant documents using cosine similarity."""
        query_vec = self.embed_text(query)
        scored = []

        for doc_id, doc in self._doc_vectors.items():
            emb = doc.get("embedding")
            if not emb:
                continue
            sim = self.cosine_similarity(query_vec, emb)
            if sim >= min_score:
                scored.append({
                    "id": doc_id,
                    "title": doc["title"],
                    "content": doc["content"],
                    "tags": doc.get("tags"),
                    "score": round(sim, 4)
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def delete_document(self, doc_id: str) -> bool:
        """Removes a document from memory cache and persistent vector store."""
        existed = doc_id in self._doc_vectors
        if existed:
            del self._doc_vectors[doc_id]
        db_deleted = self._db.delete_vector_knowledge(doc_id)
        return existed or db_deleted

    def list_all_documents(self) -> List[Dict[str, Any]]:
        """Returns all documents indexed in the vector store."""
        return [
            {
                "id": doc_id,
                "title": data["title"],
                "content": data["content"],
                "tags": data.get("tags"),
            }
            for doc_id, data in self._doc_vectors.items()
        ]


_vector_db_instance: Optional[VectorDatabase] = None

def get_vector_db() -> VectorDatabase:
    global _vector_db_instance
    if _vector_db_instance is None:
        _vector_db_instance = VectorDatabase()
    return _vector_db_instance
