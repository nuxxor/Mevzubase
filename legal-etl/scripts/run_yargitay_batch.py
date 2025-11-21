#!/usr/bin/env python
from __future__ import annotations

"""
Batch runner + lightweight monitor for Yargitay (Bedesten) ingestion.

Usage:
  poetry run python scripts/run_yargitay_batch.py \\
    --start-year 2005 --end-year 2025 --end-date 2025-11-20 \\
    --parallel 6 --log-dir logs --refresh 5

What it does:
  - Slices by year (last yıl end-date ile kısalır).
  - En fazla --parallel kadar pencereyi aynı anda çalıştırır.
  - Her pencereyi run_connector.py ile çalıştırır, log'u ayrı dosyaya yazar.
  - StateStore'dan (state.db) kuyruk durumlarını okuyup yüzde olarak gösterir.
"""

import argparse
import subprocess
import sys
import time
from collections import deque
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
RUN_CONNECTOR = ROOT / "scripts" / "run_connector.py"
DEFAULT_LOG_DIR = ROOT / "logs"

sys.path.insert(0, str(ROOT))
from src.core.state import StateStore  # noqa: E402


def build_windows(start_year: int, end_year: int, last_end: Optional[date]) -> List[Tuple[date, date]]:
    windows: List[Tuple[date, date]] = []
    for year in range(start_year, end_year + 1):
        ws = date(year, 1, 1)
        we = date(year, 12, 31)
        if last_end and year == end_year and last_end < we:
            we = last_end
        windows.append((ws, we))
    return windows


def fmt_bar(pct: float, width: int = 20) -> str:
    filled = int((pct / 100.0) * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


CONNECTOR = "yargitay"


def window_key(ws: date, we: date) -> str:
    return f"{CONNECTOR}:{ws.isoformat()}->{we.isoformat()}"


def monitor(store: StateStore, active: list, queued: deque, finished: list) -> str:
    lines = []
    lines.append("WINDOW                STATUS     DONE/TOTAL   %     PEND  INPR  RETRY  FAIL")
    lines.append("-" * 76)
    tracked = list(active) + list(queued) + list(finished)
    for ws, we in tracked:
        key = window_key(ws, we)
        counts = store.queue_counts(CONNECTOR, key)
        total = sum(counts.values())
        done = counts["DONE"] + counts["FAILED"]
        pct = (done / total * 100) if total else 0.0
        bar = fmt_bar(pct)
        status = "active" if (ws, we) in active else ("queued" if (ws, we) in queued else "done")
        lines.append(
            f"{ws}..{we} {status:<8} {done:6}/{total:<6} {pct:5.1f}% {counts['PENDING']:5} {counts['IN_PROGRESS']:5} {counts['RETRY']:5} {counts['FAILED']:5} {bar}"
        )
    return "\n".join(lines)


def launch_run(ws: date, we: date, log_dir: Path) -> subprocess.Popen:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{CONNECTOR}_{ws.year}.log"
    cmd = [
        sys.executable,
        str(RUN_CONNECTOR),
        "--connector",
        CONNECTOR,
        "--live",
        "--window-start",
        ws.isoformat(),
        "--window-end",
        we.isoformat(),
        "--log-heartbeat",
    ]
    return subprocess.Popen(cmd, stdout=log_file.open("w"), stderr=subprocess.STDOUT)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument(
        "--end-date",
        type=str,
        help="YYYY-MM-DD (sadece son yıl için kesme noktası)",
    )
    parser.add_argument("--parallel", type=int, default=4, help="Aynı anda kaç pencere koşsun")
    parser.add_argument("--refresh", type=int, default=5, help="Durum yenileme saniyesi")
    parser.add_argument("--log-dir", type=str, default=str(DEFAULT_LOG_DIR))
    args = parser.parse_args()

    last_end = datetime.strptime(args.end_date, "%Y-%m-%d").date() if args.end_date else None
    windows = build_windows(args.start_year, args.end_year, last_end)
    queue = deque(windows)
    active: list[Tuple[date, date]] = []
    finished: list[Tuple[date, date]] = []
    procs: dict[Tuple[date, date], subprocess.Popen] = {}
    store = StateStore()

    print(f"Launching {len(windows)} windows (parallel={args.parallel}, connector={CONNECTOR})")
    try:
        while queue or active:
            while queue and len(active) < args.parallel:
                ws, we = queue.popleft()
                proc = launch_run(ws, we, Path(args.log_dir))
                procs[(ws, we)] = proc
                active.append((ws, we))

            time.sleep(args.refresh)

            # Clean finished
            for ws_we in list(active):
                proc = procs.get(ws_we)
                if proc and proc.poll() is not None:
                    active.remove(ws_we)
                    finished.append(ws_we)

            # Print monitor view
            print("\033c", end="")  # clear screen
            print(monitor(store, active, queue, finished))
            if active:
                print(f"Active processes: {len(active)} | Queued: {len(queue)} | Finished: {len(finished)}")
                for ws, we in active:
                    print(f" - {ws}..{we}: pid {procs[(ws, we)].pid}")
    except KeyboardInterrupt:
        print("Stopping... sending SIGTERM to active runs.")
        for proc in procs.values():
            if proc.poll() is None:
                proc.terminate()
    finally:
        for proc in procs.values():
            if proc.poll() is None:
                proc.wait()


if __name__ == "__main__":
    main()
