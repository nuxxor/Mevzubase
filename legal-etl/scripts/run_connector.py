#!/usr/bin/env python

from __future__ import annotations

"""
Quick manual runner for Yargitay/Emsal connectors.

Examples:
  PLAYWRIGHT_BROWSERS_PATH=./.playwright-browsers \
  PW_CHROMIUM_PATH=./.playwright-browsers/chromium-1194/chrome-linux/chrome \
  poetry run python scripts/run_connector.py --connector yargitay --days 3 --limit 3 --live

Without --live it uses bundled HTML fixtures (offline sanity).
"""

import argparse
import json
import random
import sys
import time
from collections import deque
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.connectors.yargitay import YargitayConnector
from src.connectors.emsal import EmsalConnector
from src.core.state import StateStore
from src.core.schema import ItemRef


CONNECTORS = {
    "yargitay": YargitayConnector,
    "emsal": EmsalConnector,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--connector", choices=CONNECTORS.keys(), required=True)
    parser.add_argument("--days", type=int, default=2, help="Look back this many days for live mode.")
    parser.add_argument("--limit", type=int, default=0, help="Max refs to process (0 = no limit).")
    parser.add_argument("--live", action="store_true", help="Use Playwright to hit the real site.")
    parser.add_argument("--resume", action="store_true", help="Resume from saved state (if available).")
    parser.add_argument("--buffer-days", type=int, default=3, help="Overlap window when resuming (default: 3).")
    parser.add_argument("--max-errors", type=int, default=50, help="Abort after this many consecutive errors.")
    parser.add_argument("--state-db", type=str, default=None, help="Custom state DB path (default: state.db).")
    parser.add_argument("--stale-after", type=int, default=180, help="Seconds before marking run as stalled.")
    parser.add_argument("--window-start", type=str, help="Override window start date (YYYY-MM-DD).")
    parser.add_argument("--window-end", type=str, help="Override window end date (YYYY-MM-DD).")
    parser.add_argument("--show-browser", action="store_true", help="Disable headless mode to observe the browser.")
    parser.add_argument("--log-heartbeat", action="store_true", help="Print heartbeat/log lines regularly.")
    parser.add_argument("--max-attempts", type=int, default=5, help="Retry limit per item before marking failed.")
    parser.add_argument("--full-text", action="store_true", help="Print full decision text for each doc (noisy).")
    args = parser.parse_args()

    connector_cls = CONNECTORS[args.connector]
    connector = connector_cls(use_live=args.live, headless=not args.show_browser)

    store = StateStore(args.state_db)
    store.mark_stale_runs(args.connector, stale_after=args.stale_after)

    window_start = _parse_cli_date(args.window_start) if args.window_start else None
    window_end = _parse_cli_date(args.window_end) if args.window_end else None
    today = date.today()
    if window_start is None:
        window_start = today - timedelta(days=args.days)
    if window_end is None:
        window_end = today
    if window_end < window_start:
        raise ValueError("window_end cannot be earlier than window_start")
    since = window_start
    shard_key = f"{args.connector}:{window_start.isoformat()}->{window_end.isoformat()}"

    progress = store.load_progress(args.connector) if args.resume else None
    if progress and progress.get("last_decision_date"):
        last_dt = _parse_date(progress.get("last_decision_date"))
        if last_dt:
            resume_start = last_dt - timedelta(days=args.buffer_days)
            if resume_start < since:
                since = resume_start

    print(
        f"[{args.connector}] listing since {since} (live={args.live}, resume={bool(progress)})"
    )

    run_id = store.start_run(
        args.connector,
        window_start=datetime.combine(window_start, datetime.min.time()),
        window_end=datetime.combine(window_end, datetime.min.time()),
        params={
            "days": args.days,
            "limit": args.limit,
            "live": args.live,
            "resume": bool(progress),
        },
    )

    recent_keys: deque[str] = deque(maxlen=128)
    consecutive_errors = 0
    processed = 0

    try:
        refs = list(connector.list_items(since, window_end))
        store.enqueue_items(
            args.connector,
            shard_key,
            [json.loads(ref.model_dump_json()) for ref in refs],
        )
        print(f"[RUN {run_id}] Enqueued {len(refs)} refs for {shard_key}")

        while True:
            queued = store.checkout_next_item(args.connector, shard_key)
            if not queued:
                break
            queue_id = queued.pop("_queue_id")
            attempts = queued.pop("_attempts", 0)
            ref = ItemRef.model_validate(queued)

            if args.limit > 0 and processed >= args.limit:
                break

            store.heartbeat(run_id, stage="list", last_item_key=ref.key)
            if args.log_heartbeat:
                print(
                    f"[RUN {run_id}] stage=list shard={shard_key} item={ref.key} decision_date={ref.metadata.get('decision_date')}"
                )
            if ref.key in recent_keys:
                print(f"[WARN] repeated key {ref.key} detected.")
            recent_keys.append(ref.key)
            try:
                raw = connector.fetch(ref)
                doc = connector.parse(raw)
                chunks = connector.chunk(doc)
                processed += 1
                decision_iso = _decision_date_iso(doc, ref)
                store.mark_item_processed(
                    connector=args.connector,
                    run_id=run_id,
                    shard_key=shard_key,
                    item_key=ref.key,
                    decision_date=decision_iso,
                    doc_id=doc.doc_id,
                )
                store.mark_queue_done(queue_id)
                consecutive_errors = 0

                if args.log_heartbeat:
                    print(
                        f"[RUN {run_id}] processed={processed} quality={doc.meta.get('quality_flag','ok')} last_doc={doc.doc_id}"
                    )
                else:
                    print(f"ref: {ref}")
                    print(
                        f"doc_id={doc.doc_id} title={doc.title!r} chunks={len(chunks)} checksum={doc.checksum[:10]}..."
                    )
                    if args.full_text:
                        text = doc.meta.get("full_text") or "\n\n".join(chunk.content for chunk in chunks)
                        print("- FULL TEXT START ".ljust(40, "-"))
                        print(text)
                        print("- FULL TEXT END ".ljust(40, "-"))
                    for idx, chunk in enumerate(chunks):
                        preview = chunk.content[:80].replace("\n", " ")
                        print(f"  chunk[{idx}] tokens={chunk.token_count} preview={preview!r}")
                    print("-" * 40)

            except Exception as exc:  # noqa: BLE001
                consecutive_errors += 1
                store.record_error(run_id, str(exc))
                print(f"[ERROR] Failed processing {ref.key}: {exc}")
                delay = min(3600, int(5 * (2 ** attempts))) + int(random.uniform(1, 5))
                store.mark_queue_retry(queue_id, str(exc), delay, args.max_attempts)
                if consecutive_errors >= args.max_errors:
                    raise RuntimeError(
                        f"Aborting after {consecutive_errors} consecutive errors."
                    ) from exc

        status = "completed" if consecutive_errors == 0 else "completed_with_warnings"
        store.finish_run(run_id, status=status)
        stats = store.queue_counts(args.connector, shard_key)
        print(f"[RUN {run_id}] queue summary: {stats}")

    except KeyboardInterrupt:
        print("Stopping... progress saved.")
        store.finish_run(run_id, status="cancelled")
    except Exception:  # noqa: BLE001
        store.finish_run(run_id, status="failed")
        raise
    finally:
        connector.close()


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None


def _decision_date_iso(doc, ref) -> Optional[str]:
    dt = doc.decision_date or _parse_date(ref.metadata.get("decision_date"))
    if dt:
        return dt.isoformat()
    text_date = doc.meta.get("decision_date_text")
    parsed = _parse_date(text_date)
    return parsed.isoformat() if parsed else None


def _parse_cli_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:  # noqa: BLE001
        raise ValueError(f"Invalid date format: {value}; expected YYYY-MM-DD") from exc


if __name__ == "__main__":
    main()
