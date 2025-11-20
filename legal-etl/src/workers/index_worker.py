from __future__ import annotations

import structlog

from src.core.index_bm25 import OpenSearchIndexer
from src.core.schema import Chunk

logger = structlog.get_logger()


def process_index(chunks_data: list[dict]) -> None:
    chunks = [Chunk.model_validate(c) for c in chunks_data]
    if not chunks:
        return
    indexer = OpenSearchIndexer()
    indexer.ensure_index()
    indexer.upsert(chunks)
    logger.info("index.upserted", count=len(chunks))
