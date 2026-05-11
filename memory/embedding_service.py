"""
EmbeddingService — wraps Ollama's nomic-embed-text model for vector embeddings.

Embeddings convert text (code, reviews) into dense numeric vectors so that
similar content can be found via nearest-neighbor search in ChromaDB.

Why nomic-embed-text?
- Runs locally via Ollama — no API key needed
- Optimized for code and technical text
- 768-dimensional embeddings, good balance of speed and quality

See AI_CONCEPTS.md "Embeddings" for the conceptual explanation.
"""

import ollama


class EmbeddingService:
    """
    Generates vector embeddings for text using Ollama's nomic-embed-text model.

    Usage:
        service = EmbeddingService()
        vector = service.embed("def foo(): pass")  # returns list[float]
        vectors = service.embed_many(["code1", "code2"])
    """

    def __init__(self, model: str = "nomic-embed-text"):
        self.model = model
        self.client = ollama.Client()

    def embed(self, text: str) -> list[float]:
        """
        Embed a single string into a vector.

        Args:
            text: The text to embed (code, review summary, etc.)

        Returns:
            A list of floats representing the embedding vector.
        """
        response = self.client.embeddings(model=self.model, prompt=text)
        return response.embedding

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple strings. Each is embedded individually.

        Args:
            texts: List of strings to embed.

        Returns:
            List of embedding vectors, one per input string.
        """
        return [self.embed(text) for text in texts]
