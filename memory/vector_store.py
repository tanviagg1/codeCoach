"""
VectorStore — ChromaDB wrapper for storing and querying past code reviews.

This is a Phase 4 component. In Phase 1-3, this module exists but is not
connected to the pipeline. In Phase 4, it gets wired into ReviewAgent to
inject relevant past reviews into the prompt (RAG).

See AI_CONCEPTS.md "Retrieval-Augmented Generation (RAG)" for the concept.
See PHASES.md Phase 4 for the full implementation plan.
"""

from dataclasses import asdict
from agents.context import AgentContext


class VectorStore:
    """
    Stores and retrieves code reviews using ChromaDB vector embeddings.

    Phase 4 implementation:
    - Store a review by embedding the code and saving the full context
    - Query similar past reviews by embedding a new piece of code
    - Inject top-K results into the ReviewAgent prompt for better reviews

    Phase 1-3: This class exists as a stub — methods log instead of acting.
    """

    def __init__(self, collection_name: str = "code_reviews", persist_dir: str = "chroma_db"):
        self.collection_name = collection_name
        self.persist_dir = persist_dir
        self._client = None
        self._collection = None
        self._phase4_enabled = False

    def _init_chroma(self):
        """Lazily initialize ChromaDB client (Phase 4)."""
        try:
            import chromadb
            self._client = chromadb.PersistentClient(path=self.persist_dir)
            self._collection = self._client.get_or_create_collection(self.collection_name)
            self._phase4_enabled = True
        except ImportError:
            print("ChromaDB not available. Install in Phase 4: pip install chromadb")

    def store_review(self, context: AgentContext) -> str:
        """
        Store a completed review in the vector store.

        In Phase 4: embeds the code, stores context as metadata.
        In Phase 1-3: no-op, returns a placeholder ID.

        Args:
            context: Fully run AgentContext with review results

        Returns:
            The ID of the stored review
        """
        if not self._phase4_enabled:
            print("  [VectorStore] Phase 4 not enabled — skipping storage.")
            return "phase4-not-enabled"

        # Phase 4 implementation:
        # 1. Embed context.code using Anthropic embeddings
        # 2. Store in ChromaDB with metadata from context
        # 3. Return the generated ID
        raise NotImplementedError("Implement in Phase 4")

    def find_similar_reviews(self, code: str, top_k: int = 3) -> list[dict]:
        """
        Find the K most similar past reviews for a given piece of code.

        In Phase 4: embeds the code, queries ChromaDB, returns past contexts.
        In Phase 1-3: returns empty list (no-op).

        Args:
            code: The new code to find similar reviews for
            top_k: How many past reviews to retrieve

        Returns:
            List of past review dicts (subset of AgentContext fields)
        """
        if not self._phase4_enabled:
            return []

        # Phase 4 implementation:
        # 1. Embed the new code
        # 2. Query ChromaDB for top_k nearest neighbors
        # 3. Return the stored review metadata
        raise NotImplementedError("Implement in Phase 4")

    def list_reviews(self, limit: int = 20) -> list[dict]:
        """
        List the most recent reviews stored.

        Args:
            limit: Maximum number of reviews to return

        Returns:
            List of stored review summaries
        """
        if not self._phase4_enabled:
            return []
        raise NotImplementedError("Implement in Phase 4")
