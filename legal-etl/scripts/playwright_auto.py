"""
Small helper to probe Yargitay / Emsal search flows and log any JSON responses.

Example (Chromium cache + path already downloaded):
  PW_CHROMIUM_PATH="$(pwd)/.playwright-browsers/chromium-1194/chrome-linux/chrome" \\
  PLAYWRIGHT_BROWSERS_PATH=./.playwright-browsers \\
  poetry run python scripts/playwright_auto.py --site yargitay --start 2024-01-01 --end 2024-01-07
"""

from __future__ import annotations

import argparse
import os
import re
from datetime import date, datetime, timedelta
from typing import Callable

from playwright.sync_api import Response, sync_playwright

DATE_FMT_UI = "%d.%m.%Y"
_VERBOSE_DUMP = False


def parse_date(val: str) -> date:
    return datetime.strptime(val, "%Y-%m-%d").date()


def default_range(days: int = 7) -> tuple[date, date]:
    end = date.today()
    start = end - timedelta(days=days)
    return start, end


def log_json_response(resp: Response) -> None:
    ct = (resp.headers.get("content-type") or "").lower()
    if "application/json" not in ct:
        return
    try:
        data = resp.json()
    except Exception:
        return
    print(f"[JSON] {resp.url} status={resp.status}")
    if isinstance(data, dict):
        keys = list(data)[:8]
        rows = data.get("data") or data.get("results") or data.get("rows") or []
        if isinstance(rows, dict):
            for k in ("data", "rows", "results"):
                if isinstance(rows.get(k), list):
                    rows = rows[k]
                    break
        print(f"       keys={keys} rows_len={len(rows) if isinstance(rows, list) else 'n/a'}")
        if _VERBOSE_DUMP and isinstance(rows, list) and rows:
            print("       first_row_keys:", list(rows[0].keys()))
            try:
                import json as _json
                print("       first_row_sample:", _json.dumps(rows[0], ensure_ascii=False)[:800])
            except Exception:
                pass
    elif isinstance(data, list):
        print(f"       list_len={len(data)}")
    else:
        print(f"       type={type(data)}")


def force_input(page, placeholder: str | re.Pattern, value: str) -> None:
    loc = page.get_by_placeholder(placeholder)
    if not loc.count():
        return
    force_input_loc(loc.first, value)


def force_input_loc(locator, value: str) -> None:
    try:
        locator.evaluate(
            f"""
            (el) => {{
                el.removeAttribute('readonly');
                el.value = '{value}';
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
            """
        )
    except Exception:
        try:
            locator.fill(value)
        except Exception:
            pass


def drive_yargitay(page, start: date, end: date) -> None:
    page.goto("https://karararama.yargitay.gov.tr/", wait_until="domcontentloaded")
    page.get_by_text("DETAYLI ARAMA", exact=False).click()
    page.wait_for_timeout(500)
    force_input(page, "Başlama tarihini giriniz.", start.strftime(DATE_FMT_UI))
    force_input(page, "Bitiş tarihini giriniz.", end.strftime(DATE_FMT_UI))
    try:
        page.get_by_label("Karar Tarihine Göre").check(timeout=1500)
        page.get_by_label("Küçükten Büyüğe Göre").check(timeout=1500)
    except Exception:
        pass
    page.get_by_role("button", name=re.compile("Ara", re.I)).click()
    # Bekleme: JSON yakalamaları için kısa bekleme yeterli.
    page.wait_for_timeout(2000)


def drive_emsal(page, start: date, end: date) -> None:
    page.goto("https://emsal.uyap.gov.tr/", wait_until="domcontentloaded")
    page.get_by_text("Detaylı Arama", exact=False).click()
    page.wait_for_timeout(300)
    force_input(page, "Başlama tarihini giriniz.", start.strftime(DATE_FMT_UI))
    force_input(page, "Bitiş tarihini giriniz.", end.strftime(DATE_FMT_UI))
    page.get_by_role("button", name=re.compile("Ara", re.I)).click()
    page.wait_for_timeout(2000)


def run(site: str, start: date, end: date, headless: bool) -> None:
    exec_path = os.environ.get("PW_CHROMIUM_PATH")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            executable_path=exec_path,
            args=["--no-sandbox"],
        )
        page = browser.new_page(locale="tr-TR", viewport={"width": 1280, "height": 800})
        page.on("response", log_json_response)

        drivers: dict[str, Callable] = {
            "yargitay": drive_yargitay,
            "emsal": drive_emsal,
        }
        drivers[site](page, start, end)
        browser.close()


def _enable_verbose_dump() -> None:
    global _VERBOSE_DUMP
    _VERBOSE_DUMP = True


def main() -> None:
    ap = argparse.ArgumentParser(description="Probe hidden JSON endpoints during search.")
    ap.add_argument("--site", choices=["yargitay", "emsal"], required=True)
    ap.add_argument("--start", type=parse_date, help="YYYY-MM-DD (default: 7 days ago)")
    ap.add_argument("--end", type=parse_date, help="YYYY-MM-DD (default: today)")
    ap.add_argument("--headless", action="store_true", default=False, help="Run headless (default: show browser)")
    ap.add_argument("--dump-first", action="store_true", help="Dump first JSON row for inspection")
    args = ap.parse_args()

    start, end = default_range()
    if args.start:
        start = args.start
    if args.end:
        end = args.end
    if args.dump_first:
        _enable_verbose_dump()
    run(args.site, start, end, args.headless)


if __name__ == "__main__":
    main()
