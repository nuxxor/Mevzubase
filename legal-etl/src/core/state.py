from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

DEFAULT_DB = Path(__file__).resolve().parents[2] / "state.db"


class StateStore:
    """Lightweight SQLite-based run/progress tracker."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ingest_runs (
                    run_id TEXT PRIMARY KEY,
                    connector TEXT NOT NULL,
                    window_start TEXT NOT NULL,
                    window_end TEXT NOT NULL,
                    params TEXT NOT NULL,
                    stage TEXT NOT NULL DEFAULT 'init',
                    last_item_key TEXT,
                    processed_count INTEGER NOT NULL DEFAULT 0,
                    error_count INTEGER NOT NULL DEFAULT 0,
                    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_heartbeat TEXT,
                    finished_at TEXT,
                    status TEXT NOT NULL DEFAULT 'in_progress'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS connector_progress (
                    connector TEXT PRIMARY KEY,
                    shard_key TEXT NOT NULL,
                    last_decision_date TEXT,
                    last_doc_id TEXT,
                    last_item_key TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def start_run(
        self,
        connector: str,
        window_start: datetime,
        window_end: datetime,
        params: dict[str, Any],
    ) -> str:
        run_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ingest_runs
                    (run_id, connector, window_start, window_end, params, stage, last_heartbeat)
                VALUES (?, ?, ?, ?, ?, 'init', CURRENT_TIMESTAMP)
                """,
                (
                    run_id,
                    connector,
                    window_start.date().isoformat(),
                    window_end.date().isoformat(),
                    json.dumps(params),
                ),
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ingest_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    connector TEXT NOT NULL,
                    window_key TEXT NOT NULL,
                    item_key TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt_at TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(connector, window_key, item_key)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ingest_queue_lookup ON ingest_queue(connector, window_key, status)"
            )
        return run_id

    def mark_stale_runs(self, connector: str, stale_after: int = 120) -> None:
        threshold = datetime.utcnow() - timedelta(seconds=stale_after)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE ingest_runs
                   SET status = 'stalled'
                 WHERE connector = ?
                   AND status = 'in_progress'
                   AND (
                        last_heartbeat IS NULL
                        OR datetime(last_heartbeat) < ?
                   )
                """,
                (connector, threshold.isoformat()),
            )

    def heartbeat(
        self,
        run_id: str,
        stage: str,
        last_item_key: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE ingest_runs
                   SET last_heartbeat = CURRENT_TIMESTAMP,
                       stage = ?,
                       last_item_key = COALESCE(?, last_item_key)
                 WHERE run_id = ?
                """,
                (stage, last_item_key, run_id),
            )

    def mark_item_processed(
        self,
        connector: str,
        run_id: str,
        shard_key: str,
        item_key: str,
        decision_date: str | None,
        doc_id: str | None,
        inc_count: int = 1,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO connector_progress
                    (connector, shard_key, last_decision_date, last_doc_id, last_item_key, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(connector) DO UPDATE SET
                    shard_key = excluded.shard_key,
                    last_decision_date = excluded.last_decision_date,
                    last_doc_id = excluded.last_doc_id,
                    last_item_key = excluded.last_item_key,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (connector, shard_key, decision_date, doc_id, item_key),
            )
            conn.execute(
                """
                UPDATE ingest_runs
                   SET processed_count = processed_count + ?,
                       last_item_key = ?,
                       last_heartbeat = CURRENT_TIMESTAMP,
                       stage = 'processing'
                 WHERE run_id = ?
                """,
                (inc_count, item_key, run_id),
            )

    def record_error(self, run_id: str, note: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE ingest_runs
                   SET error_count = error_count + 1,
                       last_heartbeat = CURRENT_TIMESTAMP
                 WHERE run_id = ?
                """,
                (run_id,),
            )

    def finish_run(self, run_id: str, status: str = "completed") -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE ingest_runs
                   SET status = ?,
                       finished_at = CURRENT_TIMESTAMP
                 WHERE run_id = ?
                """,
                (status, run_id),
            )

    def load_progress(self, connector: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT shard_key, last_decision_date, last_doc_id, last_item_key, updated_at
                  FROM connector_progress
                 WHERE connector = ?
                """,
                (connector,),
            ).fetchone()
            if not row:
                return None
            return dict(row)

    def enqueue_items(self, connector: str, window_key: str, refs: list[dict[str, Any]]) -> None:
        rows = [
            (
                connector,
                window_key,
                ref["key"],
                json.dumps(ref),
            )
            for ref in refs
        ]
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO ingest_queue (connector, window_key, item_key, payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(connector, window_key, item_key) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = CURRENT_TIMESTAMP
                """,
                rows,
            )

    def checkout_next_item(self, connector: str, window_key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, payload, attempts
                  FROM ingest_queue
                 WHERE connector = ?
                   AND window_key = ?
                   AND (
                        status = 'PENDING'
                        OR (status = 'RETRY' AND (next_attempt_at IS NULL OR datetime(next_attempt_at) <= CURRENT_TIMESTAMP))
                   )
                 ORDER BY created_at
                 LIMIT 1
                """,
                (connector, window_key),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                """
                UPDATE ingest_queue
                   SET status = 'IN_PROGRESS',
                       updated_at = CURRENT_TIMESTAMP
                 WHERE id = ?
                """,
                (row["id"],),
            )
            payload = json.loads(row["payload"])
            payload["_attempts"] = row["attempts"]
            payload["_queue_id"] = row["id"]
            return payload

    def mark_queue_done(self, item_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE ingest_queue
                   SET status = 'DONE',
                       updated_at = CURRENT_TIMESTAMP
                 WHERE id = ?
                """,
                (item_id,),
            )

    def mark_queue_retry(self, item_id: int, error: str, delay_seconds: int, max_attempts: int) -> None:
        next_attempt = datetime.utcnow() + timedelta(seconds=delay_seconds)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT attempts FROM ingest_queue WHERE id = ?",
                (item_id,),
            ).fetchone()
            attempts = (row["attempts"] if row else 0) + 1
            status = "FAILED" if attempts >= max_attempts else "RETRY"
            conn.execute(
                """
                UPDATE ingest_queue
                   SET attempts = ?,
                       status = ?,
                       next_attempt_at = ?,
                       last_error = ?,
                       updated_at = CURRENT_TIMESTAMP
                 WHERE id = ?
                """,
                (
                    attempts,
                    status,
                    next_attempt.isoformat(),
                    error[:500],
                    item_id,
                ),
            )

    def queue_counts(self, connector: str, window_key: str) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT status, COUNT(*) as cnt
                  FROM ingest_queue
                 WHERE connector = ? AND window_key = ?
                 GROUP BY status
                """,
                (connector, window_key),
            ).fetchall()
            stats = {row["status"]: row["cnt"] for row in rows}
            return {
                "PENDING": stats.get("PENDING", 0),
                "IN_PROGRESS": stats.get("IN_PROGRESS", 0),
                "RETRY": stats.get("RETRY", 0),
                "DONE": stats.get("DONE", 0),
                "FAILED": stats.get("FAILED", 0),
            }
