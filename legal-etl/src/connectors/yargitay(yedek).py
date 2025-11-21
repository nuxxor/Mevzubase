from __future__ import annotations

# Not: Yargıtay sitesinde Detaylı Arama çağrıları JSON döndüren iki endpoint kullanıyor:
#   - aramadetaylist   => liste (daire, esas/karar no, tarih, doküman id)
#   - getDokuman       => doküman gövdesi (HTML string) id ile
# Bu konektör önce bu JSON'ları yakalar, yoksa DOM'dan devam eder. JSON sayesinde liste+detay
# başka isteğe gerek kalmadan çekilebiliyor ve hızlanıyor.

import json
import os
import random
import re
import time
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional

import structlog
from playwright.sync_api import TimeoutError
from selectolax.parser import HTMLParser, Node
from urllib.parse import parse_qsl, urlencode

from src.core.chunking import chunk_decision
from src.core.decision_chunker import chunk_sections, normalize_text, split_sections
from src.core.legal import infer_topic_tags, normalize_case_number, normalize_chamber
from src.core.schema import CanonDoc, ItemRef, RawDoc, build_decision_doc_id
from src.core.versioning import doc_checksum

from .base import BaseConnector
from .playwright_session import PlaywrightSession


DATE_FMT_UI = "%d.%m.%Y"


class YargitayConnector(BaseConnector):
    source = "YARGITAY"
    # Arama listesi ve doküman XHR yolları
    LIST_ENDPOINT_HINT = "aramadetaylist"
    DOC_ENDPOINT_HINT = "getDokuman"

    logger = structlog.get_logger(__name__)

    def __init__(
        self,
        fixture_dir: str | Path | None = None,
        use_live: bool = False,
        headless: bool = True,
        executable_path: str | None = None,
    ) -> None:
        self.fixture_dir = Path(
            fixture_dir or Path(__file__).resolve().parents[2] / "tests/fixtures/sample_html"
        )
        self.use_live = use_live
        self.headless = headless
        self.executable_path = executable_path or os.environ.get("PW_CHROMIUM_PATH")
        self.session = PlaywrightSession(
            headless=self.headless,
            executable_path=self.executable_path,
        )

    def list_items(self, since: date, until: date | None = None) -> Iterable[ItemRef]:
        if not self.use_live:
            yield ItemRef(
                key=f"{self.source}:3HD:E2024/1083-K2025/1439:2025-03-10",
                url="https://karararama.yargitay.gov.tr/sample",
                metadata={"fixture": "yargitay_sample.html"},
            )
            return
        for item in self._list_items_live(since, until):
            yield item

    def fetch(self, ref: ItemRef) -> RawDoc:
        if not self.use_live:
            path = self.fixture_dir / ref.metadata.get("fixture", "yargitay_sample.html")
            html = path.read_text(encoding="utf-8")
            return RawDoc(ref=ref, content_html=html)
        
        html = self._fetch_detail_live(ref)
        return RawDoc(ref=ref, content_html=html)

    def parse(self, raw: RawDoc) -> CanonDoc:
        tree = HTMLParser(raw.content_html or "")
        
        # Metadata
        chamber = _text_or(tree.css_first(".court")) or raw.ref.metadata.get("chamber", "")
        e_no = (_text_or(tree.css_first(".e")) or raw.ref.metadata.get("e_no", "")).replace("E.", "").strip()
        k_no = (_text_or(tree.css_first(".k")) or raw.ref.metadata.get("k_no", "")).replace("K.", "").strip()
        date_txt = (_text_or(tree.css_first(".t")) or raw.ref.metadata.get("decision_date", "")).replace("T.", "").strip()
        decision_date, decision_date_text = _parse_decision_date(date_txt)

        title = _text_or(tree.css_first(".title")) or "Karar"
        
        summary = _text_or(tree.css_first(".summary"))
        reasoning_nodes = tree.css(".reasoning p")
        reasoning = [p.text(separator="\n", strip=True) for p in reasoning_nodes]

        processed_text = "\n".join(part for part in [summary, *reasoning] if part.strip())

        if not processed_text:
            processed_text = _extract_body(tree)

        if not processed_text and raw.content_html:
            processed_text = _clean_html_text(raw.content_html)

        processed_text = normalize_text(unicodedata.normalize("NFKC", processed_text))

        junk_indicators = ["recordsTotal", "lengthMenu", "kayıt göster", "DataTable"]
        if any(ind in processed_text for ind in junk_indicators):
            processed_text = "Metin alınamadı"

        normalized_chamber = normalize_chamber(chamber) or chamber or "unknown"
        quality_flag = "ok"
        checksum_text = processed_text
        doc_id_date = decision_date or decision_date_text or "unknown"
        if processed_text in ("", "Metin alınamadı"):
            quality_flag = "no_text"
            fallback = "|".join(
                part
                for part in [normalized_chamber or chamber, e_no or "", k_no or "", str(doc_id_date)]
                if part
            )
            checksum_text = fallback or "no_text"

        checksum = doc_checksum(checksum_text)
        doc_id = build_decision_doc_id(self.source, normalized_chamber, e_no, k_no, doc_id_date)
        self._log_case_mismatch(raw.ref.metadata, "e_no", e_no)
        self._log_case_mismatch(raw.ref.metadata, "k_no", k_no)

        legal_topic_tags = infer_topic_tags(processed_text)

        return CanonDoc(
            doc_id=doc_id,
            source=self.source,
            doc_type="karar",
            title=title,
            url=raw.ref.url,
            checksum=checksum,
            decision_date=decision_date,
            chamber=normalized_chamber,
            court="Yargıtay",
            text=processed_text,
            meta={
                "e_no": e_no,
                "k_no": k_no,
                "decision_date_text": decision_date_text,
                "legal_topic_tags": legal_topic_tags,
                "chunk_version": 1,
                "embed_version": 1,
                "quality_flag": quality_flag,
                "decision_status": raw.ref.metadata.get("decision_status"),
            },
            raw=raw,
        )

    def chunk(self, doc: CanonDoc):
        text = doc.text or ""
        if text == "Metin alınamadı":
            return chunk_decision(doc, "", [])
        sections = split_sections(text)
        return chunk_sections(doc, sections)

    def _list_items_live(
        self, since: date, until: date | None = None, allow_split: bool = True
    ) -> List[ItemRef]:
        items: List[ItemRef] = []
        json_rows: list[dict] = []
        json_consumed = False
        seen_keys: set[str] = set()
        paging_meta: dict = {}
        page = self.session.new_page()

        def _capture(resp):
            try:
                ct = (resp.headers.get("content-type") or "").lower()
                if "application/json" in ct and self.LIST_ENDPOINT_HINT in resp.url:
                    data = resp.json()
                    json_rows.extend(_extract_json_rows(data))
                    self.session.remember_list_request(resp)
                    paging_meta["url"] = resp.url
                    payload = resp.request.post_data or ""
                    paging_meta["raw_payload"] = payload
                    if payload.strip().startswith("{"):
                        try:
                            paging_meta["json_payload"] = json.loads(payload)
                        except ValueError:
                            paging_meta["json_payload"] = None
                    else:
                        paging_meta["pairs"] = parse_qsl(payload, keep_blank_values=True)
                    paging_meta["records_filtered"] = None
                    paging_meta["records_total"] = None
                    if isinstance(data, dict):
                        paging_meta["records_filtered"] = data.get("recordsFiltered")
                        paging_meta["records_total"] = data.get("recordsTotal")
                        inner = data.get("data") or {}
                        if paging_meta["records_filtered"] is None and isinstance(inner, dict):
                            paging_meta["records_filtered"] = inner.get("recordsFiltered")
                        if paging_meta["records_total"] is None and isinstance(inner, dict):
                            paging_meta["records_total"] = inner.get("recordsTotal")
            except Exception:
                return

        def _consume_json_rows() -> None:
            nonlocal json_consumed
            if json_consumed or not json_rows:
                return
            json_consumed = True
            paging_meta["prefetched_count"] = len(json_rows)
            json_rows.extend(_fetch_additional_rows(page, paging_meta))
            for row in json_rows:
                item = _item_from_row(row, page.url, self.source)
                if item and item.key not in seen_keys:
                    items.append(item)
                    seen_keys.add(item.key)

        def _is_list_response(resp) -> bool:
            try:
                ct = (resp.headers.get("content-type") or "").lower()
            except Exception:
                return False
            return "application/json" in ct and self.LIST_ENDPOINT_HINT in resp.url

        page.on("response", _capture)
        try:
            page.goto("https://karararama.yargitay.gov.tr/", wait_until="domcontentloaded")
            self._human_delay()
            page.get_by_text("DETAYLI ARAMA", exact=False).click()
            self._human_delay()

            start_val = since.strftime(DATE_FMT_UI)
            end_target = until or date.today()
            end_val = end_target.strftime(DATE_FMT_UI)

            _force_input(page, "Başlama tarihini giriniz.", start_val)
            _force_input(page, "Bitiş tarihini giriniz.", end_val)

            self._human_delay()
            search_btn = page.get_by_role("button", name=re.compile("Ara", re.I))
            try:
                with page.expect_response(_is_list_response, timeout=20000):
                    search_btn.click()
            except TimeoutError:
                search_btn.click()

            page.wait_for_timeout(300)
            _consume_json_rows()
            if items:
                return items

            try:
                page.wait_for_selector("table tbody tr", timeout=15000)
            except TimeoutError:
                _consume_json_rows()
                if items:
                    return items
                if not items:
                    self.logger.warning("yargitay_list_timeout")
                return items

            self._set_page_size(page, 100)
            table = page.locator("table tbody tr")

            while True:
                page.wait_for_timeout(800)
                row_count = table.count()
                if row_count == 0:
                    break

                for i in range(row_count):
                    row = table.nth(i)
                    cells = row.locator("td")
                    if cells.count() < 5:
                        continue

                    daire = cells.nth(1).inner_text().strip()
                    e_no = cells.nth(2).inner_text().strip()
                    k_no = cells.nth(3).inner_text().strip()
                    dt = cells.nth(4).inner_text().strip()

                    normalized_chamber = normalize_chamber(daire) or daire
                    normalized_e_no = normalize_case_number(e_no)
                    normalized_k_no = normalize_case_number(k_no)
                    key = f"{self.source}:{normalized_chamber}:{normalized_e_no}-{normalized_k_no}:{dt}"
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    items.append(
                        ItemRef(
                            key=key,
                            url=page.url,
                            metadata={
                                "chamber": normalized_chamber,
                                "e_no": normalized_e_no,
                                "k_no": normalized_k_no,
                                "decision_date": dt,
                            },
                        )
                    )

                next_candidates = page.get_by_role("button", name=re.compile("Sonraki", re.I))
                if next_candidates.count() == 0:
                    break
                next_btn = next_candidates.first
                if not next_btn.is_visible() or not next_btn.is_enabled():
                    break
                with page.expect_response(lambda response: response.status == 200, timeout=10000):
                    next_btn.click()
                self._human_delay()

        except Exception as exc:
            self.logger.warning("yargitay_list_error", error=str(exc))
        finally:
            page.close()
        _consume_json_rows()
        expected = (
            paging_meta.get("records_filtered")
            or paging_meta.get("records_total")
            or len(items)
        )
        self.logger.info(
            "yargitay_list_summary",
            start=str(since),
            end=str(until or date.today()),
            expected=expected,
            found=len(items),
            first_page_len=paging_meta.get("prefetched_count"),
        )
        if (
            allow_split
            and expected
            and len(items) < expected
            and until
            and (until - since).days >= 1
        ):
            # Günlük bölerek tamamlamayı dene
            merged: list[ItemRef] = []
            merged_keys: set[str] = set()
            current = since
            while current <= (until or current):
                for it in self._list_items_live(current, current, allow_split=False):
                    if it.key in merged_keys:
                        continue
                    merged_keys.add(it.key)
                    merged.append(it)
                current += timedelta(days=1)
            return merged
        return items

    def _set_page_size(self, page, size: int) -> None:
        try:
            page.evaluate(
                """(size) => {
                    const selects = Array.from(document.querySelectorAll('select'));
                    const target = selects.find(sel => sel.outerHTML.includes('length') || sel.innerText.includes('kayıt'));
                    if (target) {
                        target.value = String(size);
                        target.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }""",
                size,
            )
        except Exception:
            return

    def _fetch_detail_live(self, ref: ItemRef) -> str:
        doc_id = ref.metadata.get("doc_id")
        html_content = self._fetch_via_template(doc_id)
        if html_content:
            return html_content

        resolved_doc_id = self._resolve_doc_id_via_list(ref)
        if resolved_doc_id:
            ref.metadata["doc_id"] = resolved_doc_id
            doc_id = resolved_doc_id
            html_content = self._fetch_via_template(resolved_doc_id)
            if html_content:
                return html_content

        for attempt in range(3):
            page = self.session.new_page()
            page.set_default_timeout(60000)
            doc_payload: list = []

            def _capture(resp):
                try:
                    if self.DOC_ENDPOINT_HINT in resp.url:
                        self.session.remember_doc_request(resp, doc_id)
                        ct = (resp.headers.get("content-type") or "").lower()
                        if "application/json" in ct:
                            doc_payload.append(resp.json())
                        else:
                            doc_payload.append(resp.text())
                    if self.LIST_ENDPOINT_HINT in resp.url:
                        self.session.remember_list_request(resp)
                except Exception:
                    return

            page.on("response", _capture)
            try:
                page.goto("https://karararama.yargitay.gov.tr/", wait_until="domcontentloaded")
                self._human_delay()
                page.get_by_text("DETAYLI ARAMA", exact=False).click()
                self._human_delay()

                if ref.metadata.get("decision_date"):
                    d_date = ref.metadata["decision_date"]
                    _force_input(page, "Başlama tarihini giriniz.", d_date)
                    _force_input(page, "Bitiş tarihini giriniz.", d_date)

                if ref.metadata.get("e_no"):
                    _fill_file_numbers(page, ref.metadata["e_no"], year_ph="Esas yıl", start_idx=0)

                if ref.metadata.get("k_no"):
                    _fill_file_numbers(page, ref.metadata["k_no"], year_ph="Karar yıl", start_idx=1)

                search_btn = page.get_by_role("button", name=re.compile("Ara", re.I))
                search_btn.click()
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    page.wait_for_timeout(500)

                try:
                    page.wait_for_selector("table tbody tr", timeout=60000)
                except TimeoutError:
                    page.reload(wait_until="domcontentloaded", timeout=30000)
                    self._human_delay()
                    page.wait_for_selector("table tbody tr", timeout=30000)
                row = page.locator("table tbody tr").first
                try:
                    row.scroll_into_view_if_needed()
                    row.click(timeout=7000)
                except Exception:
                    row.click(force=True, timeout=7000)

                page.get_by_text("İçtihat Metni", exact=False).wait_for(timeout=20000)
                page.wait_for_timeout(800)

                if doc_payload:
                    html_content = _doc_from_payload(doc_payload[0])

                if not html_content.strip():
                    html_content = _extract_dom_text(page)

                if html_content.strip():
                    return html_content

            except Exception as exc:
                self.logger.warning(
                    "yargitay_detail_error",
                    error=str(exc),
                    key=ref.key,
                    attempt=attempt + 1,
                )
                if isinstance(exc, TimeoutError):
                    resolved_doc_id = self._resolve_doc_id_via_list(ref)
                    if resolved_doc_id:
                        ref.metadata["doc_id"] = resolved_doc_id
                        doc_id = resolved_doc_id
                        direct_html = self._fetch_via_template(resolved_doc_id)
                        if direct_html:
                            return direct_html
                    # İlk time-out'ta sadece context'i temizle, tekrarı bozma
                    if attempt == 0:
                        self.session.reset_context()
                    else:
                        # Üst üste time-out'larda tarayıcıyı da tazele
                        self.session.reset_context(restart_browser=True)
            finally:
                try:
                    page.close()
                except Exception:
                    pass

            delay = (1.5 ** attempt) + random.uniform(0.3, 0.8)
            time.sleep(delay)

        return self._fetch_via_template(doc_id) or ""

    def _resolve_doc_id_via_list(self, ref: ItemRef) -> str | None:
        rows = self.session.fetch_list_rows(
            chamber=ref.metadata.get("chamber"),
            e_no=ref.metadata.get("e_no"),
            k_no=ref.metadata.get("k_no"),
            decision_date=ref.metadata.get("decision_date"),
        )
        if not rows:
            return None
        list_url = self.session.list_url or ref.url
        target_e = normalize_case_number(ref.metadata.get("e_no", ""))
        target_k = normalize_case_number(ref.metadata.get("k_no", ""))
        target_dt = ref.metadata.get("decision_date")

        for row in rows:
            item = _item_from_row(row, list_url, self.source)
            if not item:
                continue
            doc_id = item.metadata.get("doc_id")
            if not doc_id:
                continue
            if target_e and normalize_case_number(item.metadata.get("e_no", "")) != target_e:
                continue
            if target_k and normalize_case_number(item.metadata.get("k_no", "")) != target_k:
                continue
            if target_dt and item.metadata.get("decision_date") != target_dt:
                continue
            return doc_id
        return None

    def _fetch_via_template(self, doc_id: str | None) -> str:
        response = self.session.fetch_document(doc_id)
        if not response:
            return ""
        ct = (response.headers.get("content-type") or "").lower()
        try:
            if "application/json" in ct:
                return _doc_from_payload(response.json())
            return response.text()
        except Exception:
            return ""

    def _log_case_mismatch(self, metadata: dict | None, field: str, parsed_value: str | None) -> None:
        if not metadata:
            return
        expected = metadata.get(field)
        if not expected or not parsed_value:
            return
        if normalize_case_number(expected) != normalize_case_number(parsed_value):
            self.logger.warning(
                "yargitay_meta_mismatch",
                field=field,
                expected=expected,
                parsed=parsed_value,
            )

    def _human_delay(self, min_ms: int = 300, max_ms: int = 1200) -> None:
        time.sleep(random.uniform(min_ms, max_ms) / 1000)

    def close(self) -> None:
        if hasattr(self, "session"):
            self.session.close()


def _text_or(node: Optional[Node]) -> str:
    return node.text(strip=True) if node else ""


def _normalize_date(dt: str) -> str:
    parts = dt.split(".")
    if len(parts) != 3:
        return dt
    return f"{parts[2]}-{parts[1]}-{parts[0]}"


def _parse_decision_date(value: str) -> tuple[date | None, str | None]:
    cleaned = (value or "").strip()
    if not cleaned:
        return None, None

    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt).date(), None
        except ValueError:
            continue

    return None, cleaned


def _extract_body(tree: HTMLParser) -> str:
    # Önce "İçtihat Metni" çevresini dene
    anchor = None
    for tag in tree.css("h1, h2, h3, h4, h5, b, strong, span, p, div"):
        if "İçtihat Metni" in tag.text(strip=True):
            anchor = tag
            break

    if anchor:
        current = anchor
        for _ in range(5):
            text_content = current.text(separator="\n", strip=True)
            if len(text_content) > 200:
                lines = [ln.strip() for ln in text_content.splitlines() if ln.strip()]
                return "\n".join(lines)
            if current.parent is None:
                break
            current = current.parent

    # Son çare: paragraf uzunluğuna göre seç
    paras = [p.text(separator="\n", strip=True) for p in tree.css("p") if len(p.text(strip=True)) > 40]
    if paras:
        return "\n".join(paras)
    return ""


def _clean_html_text(html: str) -> str:
    try:
        parser = HTMLParser(html or "")
        for tag in parser.css("script, style, link, meta"):
            tag.remove()
        container = parser.css_first(".card-scroll") or parser.body or parser
        return container.text(separator="\n", strip=True)
    except Exception:
        return html or ""


def _extract_dom_text(page) -> str:
    try:
        container = page.locator(".card-scroll").first
        if container.count():
            return container.inner_text()
        printable = page.locator("xpath=//div[contains(@class,'card') and .//text()[contains(.,'Metni')]]").first
        if printable.count():
            return printable.inner_text()
        return page.content()
    except Exception:
        return ""


def _update_payload_pairs(
    pairs: list[tuple[str, str]],
    start: int,
    draw: int,
    length: int | None,
    force_add_length: bool = False,
) -> str:
    updated: list[tuple[str, str]] = []
    seen_length = False
    for key, value in pairs:
        if key == "start":
            updated.append((key, str(start)))
        elif key == "draw":
            updated.append((key, str(draw)))
        elif length is not None and key == "length":
            updated.append((key, str(length)))
            seen_length = True
        else:
            updated.append((key, value))
    if force_add_length and length is not None and not seen_length:
        updated.append(("length", str(length)))
    return urlencode(updated, doseq=True)


def _fetch_additional_rows(page, meta: dict) -> list[dict]:
    url = meta.get("url")
    if not url:
        return []
    json_payload = meta.get("json_payload")
    if json_payload:
        return _fetch_additional_rows_json(page, url, json_payload)
    pairs = meta.get("pairs")
    if not pairs:
        return []
    length = None
    draw = 1
    for key, value in pairs:
        if key == "length":
            try:
                length = int(value)
            except ValueError:
                length = None
        elif key == "draw":
            try:
                draw = int(value)
            except ValueError:
                draw = 1
    if length is None or length <= 0:
        length = 100
    records_total = meta.get("records_filtered") or meta.get("records_total") or 0
    fetched = int(meta.get("prefetched_count") or 0)
    start = fetched
    rows: list[dict] = []
    while True:
        if records_total and start >= records_total:
            break
        payload = _update_payload_pairs(pairs, start, draw + 1, length, force_add_length=True)
        try:
            resp = page.context.request.fetch(
                url,
                method="POST",
                headers={
                    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "x-requested-with": "XMLHttpRequest",
                    "referer": "https://karararama.yargitay.gov.tr/",
                },
                data=payload,
                timeout=20000,
            )
        except Exception:
            break
        if not resp.ok:
            break
        data = resp.json()
        new_rows = _extract_json_rows(data)
        if not new_rows:
            break
        rows.extend(new_rows)
        fetched += len(new_rows)
        start = fetched
        records_total = (
            data.get("recordsFiltered")
            or (data.get("data") or {}).get("recordsFiltered")
            or records_total
        )
        draw += 1
        if len(new_rows) < length:
            break
    return rows


def _fetch_additional_rows_json(page, url: str, template: dict) -> list[dict]:
    try:
        payload = json.loads(json.dumps(template))
    except Exception:
        return []
    data_obj = payload.get("data")
    if not isinstance(data_obj, dict):
        return []
    page_size = data_obj.get("pageSize") or 100
    page_number = data_obj.get("pageNumber") or 1
    rows: list[dict] = []
    while True:
        page_number += 1
        data_obj["pageNumber"] = page_number
        try:
            resp = page.context.request.fetch(
                url,
                method="POST",
                headers={
                    "content-type": "application/json; charset=UTF-8",
                    "x-requested-with": "XMLHttpRequest",
                    "referer": "https://karararama.yargitay.gov.tr/",
                },
                data=json.dumps(payload),
                timeout=20000,
            )
        except Exception:
            break
        if not resp.ok:
            break
        data = resp.json()
        new_rows = _extract_json_rows(data)
        if not new_rows:
            break
        rows.extend(new_rows)
        if len(new_rows) < page_size:
            break
    return rows




def _force_input(page, placeholder: str | re.Pattern, value: str) -> None:
    loc = page.get_by_placeholder(placeholder)
    if not loc.count():
        return
    _force_input_loc(loc.first, value)


def _force_input_loc(locator, value: str) -> None:
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


def _fill_file_numbers(page, number_str: str, year_ph: str, start_idx: int) -> None:
    year_match = re.search(r"(\d{4})", number_str or "")
    seq_match = re.search(r"/(\d+)", number_str or "")

    if year_match:
        _force_input(page, year_ph, year_match.group(1))

    if seq_match:
        seq_val = seq_match.group(1)
        first_inputs = page.get_by_placeholder("İlk sıra no")
        last_inputs = page.get_by_placeholder("Son sıra no")
        if first_inputs.count() > start_idx:
            _force_input_loc(first_inputs.nth(start_idx), seq_val)
        if last_inputs.count() > start_idx:
            _force_input_loc(last_inputs.nth(start_idx), seq_val)


def _extract_json_rows(data) -> list[dict]:
    rows: list[dict] = []
    try:
        if isinstance(data, list):
            for el in data:
                if isinstance(el, dict):
                    rows.append(el)
        elif isinstance(data, dict):
            for key in ("data", "results", "rows"):
                if isinstance(data.get(key), list):
                    rows.extend([el for el in data[key] if isinstance(el, dict)])
            # Bazı yanıtlar data içinde "data": {...} şeklinde olabilir
            inner = data.get("data")
            if isinstance(inner, dict):
                for key in ("data", "rows", "results"):
                    if isinstance(inner.get(key), list):
                        rows.extend([el for el in inner[key] if isinstance(el, dict)])
    except Exception:
        pass
    return rows


def _pick(row: dict, keys: list[str]) -> str:
    for k in keys:
        if k in row and row[k]:
            return str(row[k]).strip()
    return ""


def _item_from_row(row: dict, url: str, source: str) -> ItemRef | None:
    daire = _pick(row, ["daire", "daireAdi", "daireadi", "daireAd", "daire_ad"])
    e_no = _pick(row, ["esas", "esasNo", "esasno", "esasNoStr", "esas_numarasi", "esasNumarasi"])
    k_no = _pick(row, ["karar", "kararNo", "kararno", "kararNoStr", "karar_numarasi", "kararNumarasi"])
    dt = _pick(row, ["kararTarihi", "tarih", "kararTarih", "kararTarihiStr", "kararTarihStr", "decisionDate"])
    doc_id = _pick(row, ["id", "dokumanId", "dokumanID", "docId", "documentId", "kararId"])

    if not any([daire, e_no, k_no, dt]):
        return None

    normalized_chamber = normalize_chamber(daire) or daire
    normalized_e_no = normalize_case_number(e_no)
    normalized_k_no = normalize_case_number(k_no)
    key = f"{source}:{normalized_chamber}:{normalized_e_no}-{normalized_k_no}:{dt}"
    meta = {
        "chamber": normalized_chamber,
        "e_no": normalized_e_no,
        "k_no": normalized_k_no,
        "decision_date": dt,
    }
    if doc_id:
        meta["doc_id"] = doc_id
    return ItemRef(key=key, url=url, metadata=meta)


def _doc_from_payload(payload) -> str:
    if payload is None:
        return ""
    # Eğer dict ise data/icerik alanlarını ara
    if isinstance(payload, dict):
        data = payload.get("data", payload)
        if isinstance(data, dict):
            for key in ("icerik", "content", "html", "dokuman", "data"):
                val = data.get(key)
                if isinstance(val, str):
                    return val
        if isinstance(data, str):
            return data
    if isinstance(payload, str):
        return payload
    return ""
