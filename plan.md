Local RAG boot plan (Ubuntu)

1) Start Qdrant (Docker)
- `docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant:latest`
- Health-check: `curl -s http://localhost:6333/health` (expect “OK”)

2) (Optional if needed) Re-clean/chunk 2005
- `python legal-etl/scripts/clean_yargitay.py --input-glob "legal-etl/yargitaydocs/yargitay_2005.ndjson" --out-dir legal-etl/cleaned --chunk-dir legal-etl/cleaned/chunks_2005 --max-chars 2200 --overlap-chars 300`
- Output: `legal-etl/cleaned/yargitay_2005_clean.ndjson` + `legal-etl/cleaned/chunks_2005/yargitay_2005_chunks.ndjson`

3) Embed + load into Qdrant (CUDA torch nightly cu128 for RTX 5090)
- Ensure torch is `2.10.0.dev...+cu128` (installed from nightly index).
- Command:
  `python legal-etl/scripts/yargitay_local_pipeline.py --chunks-path legal-etl/cleaned/chunks_2005/yargitay_2005_chunks.ndjson --collection yargitay_chunks_local_v1 --model BAAI/bge-m3 --device cuda --batch-size 64 --on-disk --recreate`
- Quantization: INT8 + on_disk, HNSW M=32/ef_construct=256 (from script).

4) Quick verify
- `curl http://localhost:6333/collections` (see `yargitay_chunks_local_v1`)
- Optional search: use Qdrant API or a small script to query top-K.

5) If CUDA issues persist
- Fallback: run step 3 with `--device cpu` (2005 is small, works on CPU).

6) Next steps after 2005
- Repeat clean/chunk/embed/load for other years by changing input glob + chunk path.
- Hook reranker (local bge-reranker-v2-m3) + Qwen2.5 prompt once Qdrant populated.
