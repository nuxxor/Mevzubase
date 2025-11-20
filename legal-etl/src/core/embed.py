from __future__ import annotations

import os
from typing import Iterable, Sequence

import cohere
import structlog

from .schema import Chunk
from .utils import chunked

logger = structlog.get_logger()


class Embedder:
    def __init__(self, api_key: str | None = None, model: str = "embed-multilingual-v3.0") -> None:
        key = api_key or os.environ.get("COHERE_API_KEY")
        if not key:
            raise ValueError("COHERE_API_KEY missing")
        self.client = cohere.ClientV2(key)
        self.model = model

    def embed_chunks(self, chunks: Sequence[Chunk], batch_size: int = 48) -> list[tuple[Chunk, list[float]]]:
        results: list[tuple[Chunk, list[float]]] = []
        for batch in chunked(chunks, batch_size):
            texts = [c.content for c in batch]
            resp = self.client.embed(model=self.model, input=texts)
            embeddings = resp.embeddings
            for chunk, vec in zip(batch, embeddings, strict=True):
                results.append((chunk, vec))
            logger.info("embed.batch", size=len(batch))
        return results
