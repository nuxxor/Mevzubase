# Legal ETL

Ingest, normalize, version, embed, and index legal content from Turkish public sources. The stack uses Airflow for scheduling, Redis+RQ for task queues, PostgreSQL for canonical storage, Qdrant for dense retrieval, and OpenSearch for BM25.

## Getting started

1. Copy `.env.example` to `.env` and set secrets.
2. Install Poetry (`pipx install poetry`) and install deps: `poetry install --with playwright`.
3. Install browser binaries: `poetry run playwright install chromium`.
4. Start the stack: `cd docker && docker-compose up -d`.
5. Run smoke tests: `poetry run pytest tests/test_connectors_smoke.py -q`.

## Services

- PostgreSQL: document + version metadata.
- Redis + RQ: workers (`fetch/parse/diff/embed/index`).
- Airflow: schedules DAGs to push jobs onto queues.
- Qdrant: dense vector store (Cohere embeddings, 1024-dim).
- OpenSearch: BM25/lexical index with TR analyzer and synonyms.

## Code layout

- `src/core`: HTTP client, robots politeness, storage, versioning, text extraction, chunking, embedding, indexers, schemas, utils.
- `src/connectors`: Source-specific connectors (Yargıtay, SPK, and skeletons for others).
- `src/workers`: Task handlers for each pipeline stage.
- `src/dags`: Airflow DAGs to enqueue ingestion jobs.
- `tests`: Smoke tests and fixtures.
