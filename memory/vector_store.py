"""
VectorStore — ChromaDB wrapper for storing and querying past code reviews.

RAG flow:
  1. After a review completes → store_review(context)
     - Embeds context.code using nomic-embed-text
     - Saves review metadata (issues, summary, debt_score) alongside the vector

  2. Before ReviewAgent runs → find_similar_reviews(code, top_k=3)
     - Embeds the new code
     - Queries ChromaDB for top-K nearest neighbors
     - Returns past review metadata to inject into the prompt

Why does this improve reviews?
  If a similar file was reviewed before, the LLM sees "last time we reviewed
  similar code, we found X and Y" — reducing hallucinations and improving
  consistency across reviews of the same codebase.

See AI_CONCEPTS.md "RAG" for the full concept explanation.
"""

import json
import uuid
from datetime import datetime
from typing import Optional

import chromadb
from chromadb import EmbeddingFunction, Embeddings

from memory.embedding_service import EmbeddingService


# ---------------------------------------------------------------------------
# Custom ChromaDB embedding function backed by Ollama
# ---------------------------------------------------------------------------

class OllamaEmbeddingFunction(EmbeddingFunction):
    """Wraps EmbeddingService so ChromaDB can use it for queries and storage."""

    def __init__(self, embedding_service: EmbeddingService):
        self._service = embedding_service

    def __call__(self, input: list[str]) -> Embeddings:
        return self._service.embed_many(input)


# ---------------------------------------------------------------------------
# VectorStore
# ---------------------------------------------------------------------------

class VectorStore:
    """
    Stores and retrieves code reviews using ChromaDB vector embeddings.

    Each stored review has:
    - document: the raw code (used for embedding similarity search)
    - metadata: filename, language, debt_score, issue_count, summary, reviewed_at
    - id: a unique UUID generated at storage time
    """

    def __init__(
        self,
        collection_name: str = "code_reviews",
        persist_dir: str = "chroma_db",
        embedding_model: str = "nomic-embed-text",
    ):
        self._embedding_service = EmbeddingService(model=embedding_model)
        self._embedding_fn = OllamaEmbeddingFunction(self._embedding_service)

        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._embedding_fn,
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def store_review(self, context) -> str:
        """
        Store a completed review in ChromaDB.

        Embeds context.code and saves review metadata alongside the vector.

        Args:
            context: Fully run AgentContext

        Returns:
            The UUID of the stored review (also written to context.review_id)
        """
        review_id = str(uuid.uuid4())

        metadata = {
            "filename": context.filename,
            "language": context.language,
            "debt_score": context.debt_score if context.debt_score is not None else -1,
            "issue_count": len(context.review_issues),
            "critical_count": sum(
                1 for i in context.review_issues if i.get("severity") == "CRITICAL"
            ),
            "review_summary": context.review_summary[:500],  # ChromaDB metadata limit
            "reviewed_at": datetime.now().isoformat(),
            "issues_json": json.dumps(context.review_issues[:10]),  # store top 10
        }

        self._collection.add(
            ids=[review_id],
            documents=[context.code],
            metadatas=[metadata],
        )

        context.review_id = review_id
        print(f"  [VectorStore] Review stored: {review_id[:8]}...")
        return review_id

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def find_similar_reviews(self, code: str, top_k: int = 3) -> list[dict]:
        """
        Find the K most similar past reviews for a given piece of code.

        Uses cosine similarity on nomic-embed-text vectors.

        Args:
            code: The new code to find similar reviews for
            top_k: How many past reviews to retrieve

        Returns:
            List of past review dicts with keys:
            filename, language, debt_score, issue_count, review_summary, reviewed_at, issues
        """
        count = self._collection.count()
        if count == 0:
            return []

        actual_k = min(top_k, count)
        results = self._collection.query(
            query_texts=[code],
            n_results=actual_k,
            include=["metadatas", "distances"],
        )

        reviews = []
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for meta, distance in zip(metadatas, distances):
            reviews.append({
                "filename": meta.get("filename", "unknown"),
                "language": meta.get("language", "python"),
                "debt_score": meta.get("debt_score", -1),
                "issue_count": meta.get("issue_count", 0),
                "critical_count": meta.get("critical_count", 0),
                "review_summary": meta.get("review_summary", ""),
                "reviewed_at": meta.get("reviewed_at", ""),
                "issues": json.loads(meta.get("issues_json", "[]")),
                "similarity_score": round(1 - distance, 3),  # cosine: 1=identical
            })

        return reviews

    def list_reviews(self, limit: int = 20) -> list[dict]:
        """
        List the most recent reviews stored, newest first.

        Args:
            limit: Maximum number of reviews to return

        Returns:
            List of review summary dicts
        """
        count = self._collection.count()
        if count == 0:
            return []

        actual_limit = min(limit, count)
        results = self._collection.get(
            limit=actual_limit,
            include=["metadatas"],
        )

        reviews = []
        for id_, meta in zip(results["ids"], results["metadatas"]):
            reviews.append({
                "id": id_,
                "filename": meta.get("filename", "unknown"),
                "language": meta.get("language", "python"),
                "debt_score": meta.get("debt_score", -1),
                "issue_count": meta.get("issue_count", 0),
                "critical_count": meta.get("critical_count", 0),
                "review_summary": meta.get("review_summary", ""),
                "reviewed_at": meta.get("reviewed_at", ""),
            })

        # Sort newest first
        reviews.sort(key=lambda r: r["reviewed_at"], reverse=True)
        return reviews

    def count(self) -> int:
        """Return the total number of reviews stored."""
        return self._collection.count()
