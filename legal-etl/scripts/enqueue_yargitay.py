#!/usr/bin/env python

from __future__ import annotations

"""
Yargıtay ingest kuyruğunu (RQ) doldurmak için hafif CLI.

Örnek:
  # Docker redis ile:
  REDIS_URL=redis://localhost:6379/0 \
  YARGITAY_USE_LIVE=1 \
  poetry run python scripts/enqueue_yargitay.py --start 2005-01-01 --end 2009-12-31

Notlar:
- İşler 'fetch' kuyruğuna job_id=fetch:<ref_key> ile atılır; böylece aynı ref için tekrar enqueue dursa bile mükerrer çalışmaz.
- Fetch işçileri tamamlayınca parse kuyruğuna job_id=parse:<ref_key> ekler.
- Redis çalışmıyorsa önce docker ile redis'i ayağa kaldır: `cd docker && docker compose up -d redis`
"""

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.workers.fetch_worker import enqueue_yargitay_range


def parse_date(val: str) -> date:
    return datetime.strptime(val, "%Y-%m-%d").date()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="YYYY-MM-DD (dahil)")
    parser.add_argument("--end", help="YYYY-MM-DD (dahil). Boş ise bugünün tarihi.")
    args = parser.parse_args()

    start = parse_date(args.start)
    end = parse_date(args.end) if args.end else None

    enqueue_yargitay_range(start, end)
    print(f"Enqueued Yargıtay refs {start} -> {end or date.today()}")


if __name__ == "__main__":
    main()
