from __future__ import annotations

import structlog

from src.core.embed import Embedder
from src.core.index_qdrant import QdrantIndexer
from src.core.schema import Chunk

logger = structlog.get_logger()


def process_embed(chunks_data: list[dict]) -> None:
    chunks = [Chunk.model_validate(c) for c in chunks_data]
    if not chunks:
        return
    embedder = Embedder()
    indexer = QdrantIndexer()
    chunk_vectors = embedder.embed_chunks(chunks)
    indexer.upsert(chunk_vectors)
    logger.info("embed.upserted", count=len(chunks))
