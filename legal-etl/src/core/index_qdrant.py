from __future__ import annotations

import os
from typing import Iterable, Sequence

import structlog
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from .schema import Chunk

logger = structlog.get_logger()


class QdrantIndexer:
    def __init__(self, url: str | None = None, collection: str = "legal_chunks_v1") -> None:
        self.url = url or os.environ.get("QDRANT_URL", "http://localhost:6333")
        self.collection = collection
        self.client = QdrantClient(self.url)

    def ensure_collection(self, vector_size: int = 1024) -> None:
        if self.client.collection_exists(self.collection):
            return
        self.client.recreate_collection(
            collection_name=self.collection,
            vectors_config=qm.VectorParams(size=vector_size, distance=qm.Distance.COSINE),
        )
        logger.info("qdrant.collection_created", collection=self.collection, vector_size=vector_size)

    def upsert(self, chunk_vectors: Sequence[tuple[Chunk, Sequence[float]]]) -> None:
        if not chunk_vectors:
            return
        self.ensure_collection(len(chunk_vectors[0][1]))
        points = []
        for chunk, vector in chunk_vectors:
            points.append(
                qm.PointStruct(
                    id=chunk.chunk_id,
                    vector=vector,
                    payload={
                        **chunk.payload,
                        "chunk_id": chunk.chunk_id,
                        "article_no": chunk.article_no,
                        "paragraph_no": chunk.paragraph_no,
                    },
                )
            )
        self.client.upsert(collection_name=self.collection, points=points)
        logger.info("qdrant.upserted", points=len(points))
