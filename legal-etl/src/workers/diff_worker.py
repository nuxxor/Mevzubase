from __future__ import annotations

import structlog

from src.core.schema import Chunk
from src.core.versioning import chunk_hash

logger = structlog.get_logger()


def diff_chunks(existing_hashes: dict[str, str], new_chunks: list[Chunk]) -> list[Chunk]:
    changed: list[Chunk] = []
    for chunk in new_chunks:
        if existing_hashes.get(chunk.chunk_id) == chunk.content_hash:
            continue
        changed.append(chunk)
    logger.info("diff.changed", count=len(changed))
    return changed
