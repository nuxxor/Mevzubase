#!/usr/bin/env python
"""Create Qdrant collection for legal chunks if it does not exist."""
from __future__ import annotations

import os

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm


def main() -> None:
    url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    client = QdrantClient(url)
    collection = "legal_chunks_v1"
    if client.collection_exists(collection):
        print(f"Collection {collection} already exists")
        return

    print(f"Creating collection {collection}")
    client.recreate_collection(
        collection_name=collection,
        vectors_config=qm.VectorParams(size=1024, distance=qm.Distance.COSINE),
        optimizers_config=qm.OptimizersConfigDiff(indexing_threshold=20000),
    )


if __name__ == "__main__":
    main()
