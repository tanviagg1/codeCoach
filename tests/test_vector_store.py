"""
Tests for VectorStore and EmbeddingService (Phase 4).

Unit tests mock Ollama embeddings and ChromaDB — no real calls.
Integration tests require Ollama running with nomic-embed-text.

Run: pytest tests/test_vector_store.py -m "not integration" -v
"""

import json
import pytest
from unittest.mock import MagicMock, patch, call

from agents.context import AgentContext
from memory.embedding_service import EmbeddingService
from memory.vector_store import VectorStore, OllamaEmbeddingFunction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_context(debt_score: int = 45, issue_count: int = 2) -> AgentContext:
    ctx = AgentContext(code="def foo(): pass", filename="test.py", language="python")
    ctx.review_summary = "Two issues found."
    ctx.review_issues = [
        {"line": 1, "message": "No docstring", "severity": "LOW"},
        {"line": 5, "message": "Hardcoded value", "severity": "MEDIUM"},
    ][:issue_count]
    ctx.debt_score = debt_score
    ctx.debt_hotspots = []
    return ctx


FAKE_EMBEDDING = [0.1] * 768  # nomic-embed-text produces 768-dim vectors


# ---------------------------------------------------------------------------
# EmbeddingService tests
# ---------------------------------------------------------------------------

class TestEmbeddingService:

    def test_embed_calls_ollama(self):
        """EmbeddingService.embed() should call ollama client with the right model."""
        mock_resp = MagicMock()
        mock_resp.embedding = FAKE_EMBEDDING

        with patch("ollama.Client") as MockClient:
            MockClient.return_value.embeddings.return_value = mock_resp
            service = EmbeddingService(model="nomic-embed-text")
            result = service.embed("def foo(): pass")

        MockClient.return_value.embeddings.assert_called_once_with(
            model="nomic-embed-text", prompt="def foo(): pass"
        )
        assert result == FAKE_EMBEDDING

    def test_embed_many_calls_embed_per_text(self):
        """embed_many() should embed each text individually."""
        mock_resp = MagicMock()
        mock_resp.embedding = FAKE_EMBEDDING

        with patch("ollama.Client") as MockClient:
            MockClient.return_value.embeddings.return_value = mock_resp
            service = EmbeddingService()
            results = service.embed_many(["code1", "code2", "code3"])

        assert len(results) == 3
        assert MockClient.return_value.embeddings.call_count == 3


# ---------------------------------------------------------------------------
# OllamaEmbeddingFunction tests
# ---------------------------------------------------------------------------

class TestOllamaEmbeddingFunction:

    def test_callable_returns_list_of_embeddings(self):
        """OllamaEmbeddingFunction.__call__ should return one embedding per input."""
        mock_service = MagicMock()
        mock_service.embed_many.return_value = [FAKE_EMBEDDING, FAKE_EMBEDDING]

        fn = OllamaEmbeddingFunction(mock_service)
        result = fn(["text1", "text2"])

        assert len(result) == 2
        mock_service.embed_many.assert_called_once_with(["text1", "text2"])


# ---------------------------------------------------------------------------
# VectorStore tests (ChromaDB mocked)
# ---------------------------------------------------------------------------

class TestVectorStore:

    def _make_store(self, mock_client_cls):
        """Helper: create VectorStore with mocked chromadb and ollama."""
        mock_collection = MagicMock()
        mock_client_cls.return_value.get_or_create_collection.return_value = mock_collection
        return mock_collection

    def test_store_review_adds_to_collection(self):
        """store_review() should call collection.add() with code as document."""
        with patch("chromadb.PersistentClient") as MockChroma, \
             patch("ollama.Client") as MockOllama:

            MockOllama.return_value.embeddings.return_value = MagicMock(embedding=FAKE_EMBEDDING)
            mock_collection = self._make_store(MockChroma)
            mock_collection.count.return_value = 0

            store = VectorStore()
            ctx = make_context()
            review_id = store.store_review(ctx)

        mock_collection.add.assert_called_once()
        call_kwargs = mock_collection.add.call_args.kwargs
        assert call_kwargs["documents"] == [ctx.code]
        assert len(call_kwargs["ids"]) == 1
        assert review_id == call_kwargs["ids"][0]
        assert ctx.review_id == review_id

    def test_store_review_saves_metadata(self):
        """store_review() metadata should include filename, debt_score, issue_count."""
        with patch("chromadb.PersistentClient") as MockChroma, \
             patch("ollama.Client") as MockOllama:

            MockOllama.return_value.embeddings.return_value = MagicMock(embedding=FAKE_EMBEDDING)
            mock_collection = self._make_store(MockChroma)
            mock_collection.count.return_value = 0

            store = VectorStore()
            ctx = make_context(debt_score=72, issue_count=2)
            store.store_review(ctx)

        meta = mock_collection.add.call_args.kwargs["metadatas"][0]
        assert meta["filename"] == "test.py"
        assert meta["debt_score"] == 72
        assert meta["issue_count"] == 2

    def test_find_similar_returns_empty_when_no_reviews(self):
        """find_similar_reviews() should return [] when collection is empty."""
        with patch("chromadb.PersistentClient") as MockChroma, \
             patch("ollama.Client") as MockOllama:

            MockOllama.return_value.embeddings.return_value = MagicMock(embedding=FAKE_EMBEDDING)
            mock_collection = self._make_store(MockChroma)
            mock_collection.count.return_value = 0

            store = VectorStore()
            results = store.find_similar_reviews("def foo(): pass")

        assert results == []
        mock_collection.query.assert_not_called()

    def test_find_similar_returns_formatted_results(self):
        """find_similar_reviews() should format ChromaDB results correctly."""
        with patch("chromadb.PersistentClient") as MockChroma, \
             patch("ollama.Client") as MockOllama:

            MockOllama.return_value.embeddings.return_value = MagicMock(embedding=FAKE_EMBEDDING)
            mock_collection = self._make_store(MockChroma)
            mock_collection.count.return_value = 2
            mock_collection.query.return_value = {
                "metadatas": [[
                    {
                        "filename": "old.py",
                        "language": "python",
                        "debt_score": 60,
                        "issue_count": 3,
                        "critical_count": 1,
                        "review_summary": "Found SQL injection.",
                        "reviewed_at": "2026-01-01T10:00:00",
                        "issues_json": json.dumps([{"line": 1, "message": "SQL injection", "severity": "CRITICAL"}]),
                    }
                ]],
                "distances": [[0.1]],
            }

            store = VectorStore()
            results = store.find_similar_reviews("def foo(): pass", top_k=1)

        assert len(results) == 1
        assert results[0]["filename"] == "old.py"
        assert results[0]["debt_score"] == 60
        assert results[0]["similarity_score"] == 0.9  # 1 - 0.1
        assert results[0]["issues"][0]["severity"] == "CRITICAL"

    def test_list_reviews_returns_sorted_newest_first(self):
        """list_reviews() should sort by reviewed_at descending."""
        with patch("chromadb.PersistentClient") as MockChroma, \
             patch("ollama.Client") as MockOllama:

            MockOllama.return_value.embeddings.return_value = MagicMock(embedding=FAKE_EMBEDDING)
            mock_collection = self._make_store(MockChroma)
            mock_collection.count.return_value = 2
            mock_collection.get.return_value = {
                "ids": ["id1", "id2"],
                "metadatas": [
                    {"filename": "old.py", "reviewed_at": "2026-01-01T10:00:00",
                     "language": "python", "debt_score": 50, "issue_count": 1,
                     "critical_count": 0, "review_summary": "Old review."},
                    {"filename": "new.py", "reviewed_at": "2026-05-01T10:00:00",
                     "language": "python", "debt_score": 30, "issue_count": 0,
                     "critical_count": 0, "review_summary": "New review."},
                ],
            }

            store = VectorStore()
            results = store.list_reviews()

        assert results[0]["filename"] == "new.py"
        assert results[1]["filename"] == "old.py"

    def test_list_reviews_empty_when_no_data(self):
        """list_reviews() should return [] when collection is empty."""
        with patch("chromadb.PersistentClient") as MockChroma, \
             patch("ollama.Client") as MockOllama:

            MockOllama.return_value.embeddings.return_value = MagicMock(embedding=FAKE_EMBEDDING)
            mock_collection = self._make_store(MockChroma)
            mock_collection.count.return_value = 0

            store = VectorStore()
            results = store.list_reviews()

        assert results == []


# ---------------------------------------------------------------------------
# ReviewAgent RAG injection tests
# ---------------------------------------------------------------------------

class TestReviewAgentRAG:

    def test_rag_context_injected_into_prompt(self):
        """ReviewAgent should inject past reviews into prompt when vector_store provided."""
        import json as _json
        from agents.review_agent import ReviewAgent

        similar_reviews = [{
            "filename": "old.py",
            "similarity_score": 0.92,
            "debt_score": 70,
            "review_summary": "Found SQL injection.",
            "issues": [{"line": 5, "message": "SQL injection", "severity": "CRITICAL"}],
        }]

        mock_store = MagicMock()
        mock_store.find_similar_reviews.return_value = similar_reviews

        response_json = _json.dumps({"issues": [], "summary": "Clean."})
        mock_ollama_resp = MagicMock()
        mock_ollama_resp.message.content = response_json

        with patch("ollama.Client") as MockClient:
            MockClient.return_value.chat.return_value = mock_ollama_resp
            agent = ReviewAgent(vector_store=mock_store)
            ctx = AgentContext(code="def foo(): pass", filename="test.py", language="python")
            agent.run(ctx)

            call_kwargs = MockClient.return_value.chat.call_args.kwargs
            messages = call_kwargs.get("messages", [])
            user_content = next(m["content"] for m in messages if m["role"] == "user")

        assert "SQL injection" in user_content
        mock_store.find_similar_reviews.assert_called_once()

    def test_rag_failure_does_not_crash_agent(self):
        """ReviewAgent should continue without RAG if vector_store.find_similar_reviews fails."""
        import json as _json
        from agents.review_agent import ReviewAgent

        mock_store = MagicMock()
        mock_store.find_similar_reviews.side_effect = Exception("ChromaDB unavailable")

        response_json = _json.dumps({"issues": [], "summary": "Clean."})
        mock_ollama_resp = MagicMock()
        mock_ollama_resp.message.content = response_json

        with patch("ollama.Client") as MockClient:
            MockClient.return_value.chat.return_value = mock_ollama_resp
            agent = ReviewAgent(vector_store=mock_store)
            ctx = AgentContext(code="def foo(): pass", filename="test.py", language="python")
            result = agent.run(ctx)

        # Should still complete, with a RAG error logged
        assert any("RAG lookup failed" in e for e in result.errors)
        assert result.review_summary == "Clean."


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_embedding_service_real_ollama():
    """EmbeddingService should return a non-empty embedding from real Ollama."""
    service = EmbeddingService(model="nomic-embed-text")
    embedding = service.embed("def foo(): return 42")

    assert isinstance(embedding, list)
    assert len(embedding) > 0
    assert all(isinstance(v, float) for v in embedding)


@pytest.mark.integration
def test_vector_store_store_and_retrieve(tmp_path):
    """Full round-trip: store a review, then find it with similar code."""
    store = VectorStore(persist_dir=str(tmp_path))

    ctx = make_context(debt_score=65)
    ctx.code = "def authenticate(user, password): return password == 'secret'"
    store.store_review(ctx)

    results = store.find_similar_reviews(
        "def login(username, pwd): return pwd == 'admin'", top_k=1
    )

    assert len(results) == 1
    assert results[0]["debt_score"] == 65
    assert results[0]["filename"] == "test.py"
