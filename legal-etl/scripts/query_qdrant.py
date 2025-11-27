#!/usr/bin/env python
"""
Hızlı arama denemesi:
  python legal-etl/scripts/query_qdrant.py --query "ceza davası görevsizlik" --top-k 5
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import os
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from sentence_transformers import SentenceTransformer, CrossEncoder
import cohere


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Query Qdrant collection with BGE embeddings")
    ap.add_argument("--query", help="Tek sorgu metni")
    ap.add_argument(
        "--queries",
        nargs="+",
        help="Birden çok sorgu (boşlukla ayrılmış). Eğer içinde boşluk varsa tırnakla.",
    )
    ap.add_argument(
        "--queries-file",
        type=str,
        help="Her satırda bir sorgu olacak metin dosyası (UTF-8).",
    )
    ap.add_argument("--collection", default="yargitay_chunks_local_v1", help="Qdrant koleksiyon adı")
    ap.add_argument("--top-k", type=int, default=5, help="Dönecek sonuç sayısı (final)")
    ap.add_argument("--retrieval-top-k", type=int, default=30, help="Rerank öncesi Qdrant limit")
    ap.add_argument("--model", default="BAAI/bge-m3", help="Aynı embedding modeli")
    ap.add_argument(
        "--reranker-model",
        default=None,
        help="Opsiyonel cross-encoder (örn. BAAI/bge-reranker-v2-m3); None → rerank yok",
    )
    ap.add_argument("--rerank-batch-size", type=int, default=4, help="Reranker batch")
    ap.add_argument("--rerank-max-length", type=int, default=512, help="Reranker max token length")
    ap.add_argument("--device", default="cuda", help="cuda/cpu/auto")
    ap.add_argument("--qdrant-url", default="http://localhost:6333", help="Qdrant URL")
    ap.add_argument(
        "--use-cohere",
        action="store_true",
        help="Cohere rerank-v3.5 ile ikinci aşama rerank (COHERE_API_KEY gerektirir).",
    )
    ap.add_argument("--cohere-model", default="rerank-v3.5", help="Cohere rerank modeli")
    ap.add_argument("--cohere-top-n", type=int, default=None, help="Cohere top_n (varsayılan top_k)")
    return ap.parse_args()


def main() -> None:
    args = parse_args()

    queries: List[str] = []
    if args.query:
        queries.append(args.query)
    if args.queries:
        queries.extend(args.queries)
    if args.queries_file:
        with open(args.queries_file, "r", encoding="utf-8") as fh:
            queries.extend([line.strip() for line in fh if line.strip()])
    if not queries:
        raise SystemExit("En az bir sorgu ver: --query veya --queries veya --queries-file")

    model = SentenceTransformer(args.model, device=args.device)
    reranker = None
    if args.reranker_model and not args.use_cohere:
        reranker = CrossEncoder(args.reranker_model, device=args.device, max_length=args.rerank_max_length)

    co = None
    if args.use_cohere:
        api_key = os.environ.get("COHERE_API_KEY")
        if not api_key:
            env_path = Path(".env")
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    if line.startswith("COHERE_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
        if not api_key:
            raise SystemExit("COHERE_API_KEY ortam değişkeni veya .env içinde set edilmeli.")
        co = cohere.ClientV2(api_key=api_key)

    client = QdrantClient(args.qdrant_url)
    limit = max(args.top_k, args.retrieval_top_k)

    for q in queries:
        qvec = model.encode([q], normalize_embeddings=True)[0].tolist()
        search_res = client.query_points(
            collection_name=args.collection,
            query=qvec,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        ).points

        rerank_scores = None
        if reranker:
            pairs = []
            kept = []
            for p in search_res:
                text = (p.payload or {}).get("text", "")
                if not text:
                    continue
                kept.append(p)
                pairs.append((q, text))
            scores = reranker.predict(pairs, batch_size=args.rerank_batch_size)
            rerank_scores = {p.id: float(s) for p, s in zip(kept, scores)}
            search_res = sorted(kept, key=lambda p: rerank_scores[p.id], reverse=True)
        elif co:
            docs = []
            kept = []
            for p in search_res:
                text = (p.payload or {}).get("text", "")
                if not text:
                    continue
                kept.append(p)
                docs.append(text)
            if not docs:
                final = []
            else:
                resp = co.rerank(
                    model=args.cohere_model,
                    query=q,
                    documents=docs,
                    top_n=args.cohere_top_n or args.top_k,
                )
                # Cohere dönen index sırasını kullanarak yeniden sırala
                ordered = []
                rerank_scores = {}
                for r in resp.results:
                    p = kept[r.index]
                    rerank_scores[p.id] = float(r.relevance_score)
                    ordered.append(p)
                search_res = ordered

        final = search_res[: args.top_k]

        print(f"\n=== QUERY: {q} ===")
        for i, point in enumerate(final, 1):
            payload = point.payload or {}
            text = payload.get("text", "")[:280].replace("\n", " ")
            rscore = f" rerank={rerank_scores.get(point.id):.4f}" if rerank_scores else ""
            print(f"[{i}] id={point.id} score={point.score:.4f}{rscore}")
            print(f"    meta: {payload.get('doc_id', '')} | {payload.get('chamber', '')} | {payload.get('decision_date', '')}")
            print(f"    text: {text}")


if __name__ == "__main__":
    main()
