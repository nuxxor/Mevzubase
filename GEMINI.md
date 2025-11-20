# Project Overview

This project, "Legal ETL," is a data pipeline designed to ingest, normalize, version, embed, and index legal content from public Turkish sources. It uses a combination of web scraping, data processing, and indexing technologies to create a searchable database of legal documents.

The architecture consists of several key components:

*   **Airflow:** Used for scheduling and orchestrating the data ingestion pipelines (DAGs).
*   **Redis + RQ:** A combination for managing and executing background jobs for fetching, parsing, diffing, embedding, and indexing.
*   **PostgreSQL:** Serves as the primary storage for document and version metadata.
*   **Qdrant:** A vector database used for dense retrieval of documents based on Cohere embeddings (1024-dim).
*   **OpenSearch:** Used for BM25/lexical search with a Turkish analyzer and synonyms.
*   **Playwright:** Used for web scraping and extracting data from the source websites.
*   **Cohere:** Used for generating embeddings for the legal documents.

The project is structured as a Python application managed with Poetry.

# Building and Running

1.  **Environment Setup:**
    *   Copy the `.env.example` file to `.env` and fill in the necessary secrets, such as API keys and database credentials.

2.  **Install Dependencies:**
    *   Install Poetry: `pipx install poetry`
    *   Install project dependencies: `poetry install --with playwright`

3.  **Install Browser Binaries:**
    *   Install the necessary Playwright browser binaries: `poetry run playwright install chromium`

4.  **Start the Services:**
    *   Use Docker Compose to start all the required services (PostgreSQL, Redis, Qdrant, OpenSearch, and Airflow):
        ```bash
        cd docker
        docker-compose up -d
        ```

5.  **Run Tests:**
    *   To verify the setup, run the smoke tests:
        ```bash
        poetry run pytest tests/test_connectors_smoke.py -q
        ```

# Development Conventions

*   **Code Style:** The project uses `ruff` for linting and formatting. The configuration can be found in the `pyproject.toml` file.
*   **Type Checking:** `mypy` is used for static type checking. The configuration is also in the `pyproject.toml` file.
*   **Testing:** `pytest` is the testing framework. Tests are located in the `tests/` directory.
*   **Connectors:** Each data source has its own connector module in `src/connectors/`. Connectors are responsible for listing items, fetching raw data, parsing it into a canonical format, and chunking it for indexing.
*   **Workers:** The different stages of the ETL pipeline (fetch, parse, diff, embed, index) are implemented as RQ workers in the `src/workers/` directory.
*   **DAGs:** Airflow DAGs for scheduling the ingestion jobs are located in the `src/dags/` directory.
