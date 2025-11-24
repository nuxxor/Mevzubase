#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Yerel Yargıtay RAG hazırlığı:
- Chunk'lanmış NDJSON'ları okur
- Lokal embedding modeliyle (varsayılan BAAI/bge-m3) vektörler üretir
- Qdrant koleksiyonunu (int8 quantization + on-disk) oluşturup doldurur

Örnek kullanım:
python legal-etl/scripts/clean_yargitay.py --chunk-dir legal-etl/cleaned/chunks_2005 --max-chars 2200 --overlap-chars 300
python legal-etl/scripts/yargitay_local_pipeline.py --chunks-path legal-etl/cleaned/chunks_2005/yargitay_2005_chunks.ndjson --recreate --on-disk
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Yargıtay chunk → Qdrant yerel pipeline")
    ap.add_argument(
        "--chunks-path",
        default="legal-etl/cleaned/yargitay_2005_chunks.ndjson",
        help="Chunk NDJSON dosyası",
    )
    ap.add_argument(
        "--collection",
        default="yargitay_chunks_local_v1",
        help="Qdrant koleksiyon adı",
    )
    ap.add_argument(
        "--model",
        default="BAAI/bge-m3",
        help="SentenceTransformer embedding modeli",
    )
    ap.add_argument(
        "--device",
        default="cuda",
        help="Model cihazı (cuda/cpu/auto)",
    )
    ap.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Embedding batch boyutu",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Sadece ilk N kaydı işle (hızlı test için)",
    )
    ap.add_argument(
        "--qdrant-url",
        default="http://localhost:6333",
        help="Qdrant URL",
    )
    ap.add_argument(
        "--no-quantization",
        action="store_true",
        help="Int8 quantization kapat",
    )
    ap.add_argument(
        "--on-disk",
        action="store_true",
        help="Vektörleri diskte tut (önerilir; RAM tasarrufu)",
    )
    ap.add_argument(
        "--recreate",
        action="store_true",
        help="Koleksiyonu yeniden oluştur (varsa siler)",
    )
    return ap.parse_args()


def iter_chunks(path: Path, limit: int | None = None) -> Iterable[Tuple[str, str, Dict]]:
    with path.open("r", encoding="utf-8") as fh:
        for idx, line in enumerate(fh, 1):
            if limit is not None and idx > limit:
                break
            obj = json.loads(line)
            text = obj.get("text", "").strip()
            if not text:
                continue
            chunk_id = obj.get("chunk_id") or obj.get("doc_id") or f"chunk-{idx}"
            yield chunk_id, text, obj


def ensure_collection(
    client: QdrantClient,
    collection: str,
    dim: int,
    quantize: bool,
    on_disk: bool,
) -> None:
    quant_cfg = None
    if quantize:
        quant_cfg = qm.ScalarQuantization(
            scalar=qm.ScalarQuantizationConfig(
                type=qm.ScalarType.INT8,
                quantile=0.99,
                always_ram=True,
            )
        )

    client.recreate_collection(
        collection_name=collection,
        vectors_config=qm.VectorParams(
            size=dim,
            distance=qm.Distance.COSINE,
            on_disk=on_disk,
            quantization_config=quant_cfg,
        ),
        hnsw_config=qm.HnswConfigDiff(
            m=32,
            ef_construct=256,
        ),
    )


def upsert_batch(
    client: QdrantClient,
    collection: str,
    ids: Sequence[str],
    vectors: Sequence[Sequence[float]],
    payloads: Sequence[Dict],
) -> None:
    points = [
        qm.PointStruct(
            id=pid,
            vector=vec,
            payload=payload,
        )
        for pid, vec, payload in zip(ids, vectors, payloads)
    ]
    client.upsert(collection_name=collection, points=points, wait=True)


def main() -> None:
    args = parse_args()
    chunks_path = Path(args.chunks_path)
    if not chunks_path.exists():
        raise SystemExit(f"Chunk dosyası bulunamadı: {chunks_path}")

    model = SentenceTransformer(args.model, device=args.device)
    test_vec = model.encode(["ping"], normalize_embeddings=True)
    dim = len(test_vec[0])

    client = QdrantClient(args.qdrant_url)
    if args.recreate or not client.collection_exists(args.collection):
        ensure_collection(
            client=client,
            collection=args.collection,
            dim=dim,
            quantize=not args.no_quantization,
            on_disk=args.on_disk,
        )

    ids: List[str] = []
    texts: List[str] = []
    payloads: List[Dict] = []
    total = 0

    for chunk_id, text, payload in tqdm(iter_chunks(chunks_path, limit=args.limit), desc="embedding"):
        ids.append(chunk_id)
        texts.append(text)
        payloads.append(payload)
        if len(ids) >= args.batch_size:
            vectors = model.encode(texts, batch_size=args.batch_size, normalize_embeddings=True).tolist()
            upsert_batch(client, args.collection, ids, vectors, payloads)
            total += len(ids)
            ids.clear()
            texts.clear()
            payloads.clear()

    if ids:
        vectors = model.encode(texts, batch_size=args.batch_size, normalize_embeddings=True).tolist()
        upsert_batch(client, args.collection, ids, vectors, payloads)
        total += len(ids)

    print(f"Tamamlandı: {total} chunk yüklendi -> {args.collection} ({args.qdrant_url})")


if __name__ == "__main__":
    main()
