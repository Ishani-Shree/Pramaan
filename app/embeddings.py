"""Text -> vector. The rest of the app only depends on the Embedder protocol,
so tests can swap in a fake embedder that needs no model download."""

from __future__ import annotations

from typing import Protocol, Sequence

import numpy as np

EMBEDDING_DIM = 384  # must match vector(384) in schema.sql


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """Return an array of shape (len(texts), EMBEDDING_DIM), L2-normalised."""
        ...


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, batch_size: int = 32):
        # Imported here, not at module top: it pulls in PyTorch (slow), and
        # tests using a fake embedder should never pay that cost.
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name, device="cpu")
        self.batch_size = batch_size

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)
        vectors = self.model.encode(
            list(texts),
            batch_size=self.batch_size,
            normalize_embeddings=True,  # unit length: cosine == dot product
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        if vectors.shape[1] != EMBEDDING_DIM:
            raise ValueError(f"model gives {vectors.shape[1]}-d vectors, schema expects {EMBEDDING_DIM}")
        return vectors.astype(np.float32)
