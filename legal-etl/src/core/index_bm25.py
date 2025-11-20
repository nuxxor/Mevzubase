from __future__ import annotations

import os
from typing import Iterable

import structlog
from opensearchpy import OpenSearch

from .schema import Chunk

logger = structlog.get_logger()


class OpenSearchIndexer:
    def __init__(self, url: str | None = None, index: str = "legal_chunks_bm25") -> None:
        self.url = url or os.environ.get("OPENSEARCH_URL", "http://admin:admin@localhost:9200")
        self.index = index
        self.client = OpenSearch(self.url, verify_certs=False)

    def ensure_index(self) -> None:
        if self.client.indices.exists(index=self.index):
            return
        logger.warning("opensearch.index_missing", index=self.index)

    def upsert(self, chunks: Iterable[Chunk]) -> None:
        actions = []
        for chunk in chunks:
            actions.append(
                {
                    "_op_type": "index",
                    "_index": self.index,
                    "_id": chunk.chunk_id,
                    "_source": {
                        "doc_id": chunk.doc_id,
                        "version": chunk.version,
                        "title": chunk.payload.get("title"),
                        "content": chunk.content,
                        "article_no": chunk.article_no,
                        "paragraph_no": chunk.paragraph_no,
                        "e_no": chunk.payload.get("e_no"),
                        "k_no": chunk.payload.get("k_no"),
                        "rg_no": chunk.payload.get("rg_no"),
                        "rg_date": chunk.payload.get("rg_date"),
                        "court": chunk.payload.get("court"),
                        "chamber": chunk.payload.get("chamber"),
                        "source": chunk.payload.get("source"),
                        "doc_type": chunk.payload.get("doc_type"),
                        "url": chunk.payload.get("url"),
                        "is_current": chunk.payload.get("is_current", True),
                    },
                }
            )
        if not actions:
            return
        # Bulk API is available but avoided to keep dependency surface small for this skeleton.
        for action in actions:
            self.client.index(index=action["_index"], id=action["_id"], body=action["_source"])
        logger.info("opensearch.upserted", count=len(actions))
