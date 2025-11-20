from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

import psycopg
import structlog

from .schema import CanonDoc, Chunk, RawDoc

logger = structlog.get_logger()


class Storage:
    """Tiny Postgres helper. Tables are expected to exist."""

    def __init__(self, dsn: str, raw_dir: str = "raw") -> None:
        self.dsn = dsn
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> psycopg.Connection:
        with psycopg.connect(self.dsn, autocommit=True) as conn:
            yield conn

    def upsert_doc(self, doc: CanonDoc) -> None:
        sql = """
        INSERT INTO docs (doc_id, source, doc_type, title, url, checksum, version, is_current,
                          decision_date, rg_no, rg_date, chamber, court, meta)
        VALUES (%(doc_id)s, %(source)s, %(doc_type)s, %(title)s, %(url)s, %(checksum)s,
                %(version)s, %(is_current)s, %(decision_date)s, %(rg_no)s, %(rg_date)s,
                %(chamber)s, %(court)s, %(meta)s)
        ON CONFLICT (doc_id, version)
        DO UPDATE SET checksum = EXCLUDED.checksum,
                      is_current = EXCLUDED.is_current,
                      meta = EXCLUDED.meta,
                      title = EXCLUDED.title;
        """
        with self.connect() as conn:
            conn.execute(sql, doc.model_dump())
        logger.info("doc.upserted", doc_id=doc.doc_id, version=doc.version)

    def upsert_chunks(self, chunks: Iterable[Chunk]) -> None:
        sql = """
        INSERT INTO chunks (chunk_id, doc_id, version, content, content_hash, token_count,
                            article_no, paragraph_no, payload)
        VALUES (%(chunk_id)s, %(doc_id)s, %(version)s, %(content)s, %(content_hash)s,
                %(token_count)s, %(article_no)s, %(paragraph_no)s, %(payload)s)
        ON CONFLICT (chunk_id)
        DO UPDATE SET content = EXCLUDED.content,
                      content_hash = EXCLUDED.content_hash,
                      token_count = EXCLUDED.token_count,
                      payload = EXCLUDED.payload;
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                for chunk in chunks:
                    cur.execute(sql, chunk.model_dump())
        logger.info("chunks.upserted")

    def mark_versions(
        self,
        doc_id: str,
        current_version: int,
        mark_current: bool = True,
    ) -> None:
        sql = """
        UPDATE docs
           SET is_current = case when version = %(current)s then %(mark)s else false end
        WHERE doc_id = %(doc_id)s;
        """
        with self.connect() as conn:
            conn.execute(sql, {"doc_id": doc_id, "current": current_version, "mark": mark_current})

    def save_raw(self, raw: RawDoc, file_name: str | None = None) -> Path | None:
        if raw.content_html is None and raw.content_pdf is None:
            return None
        name = file_name or raw.ref.key.replace(":", "_")
        if raw.content_pdf:
            path = self.raw_dir / f"{name}.pdf"
            path.write_bytes(raw.content_pdf)
        else:
            path = self.raw_dir / f"{name}.html"
            path.write_text(raw.content_html or "", encoding="utf-8")
        logger.info("raw.saved", path=str(path))
        return path
