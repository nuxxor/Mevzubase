from __future__ import annotations

import itertools
import os
import random
import time
import unicodedata
from datetime import date, datetime, timedelta
from typing import Iterable, List, Optional, Tuple

import httpx
import structlog
from selectolax.parser import HTMLParser, Node

from src.core.chunking import chunk_decision
from src.core.decision_chunker import chunk_sections, normalize_text, split_sections
from src.core.legal import infer_topic_tags, normalize_case_number, normalize_chamber
from src.core.schema import CanonDoc, ItemRef, RawDoc, build_decision_doc_id
from src.core.versioning import doc_checksum

from .base import BaseConnector
from .playwright_session import PlaywrightSession


ISO_WITH_MS = "%Y-%m-%dT%H:%M:%S.000Z"


class Yargitay2Connector(BaseConnector):
    """
    Bedesten / Mevzuat JSON tabanlı Yargıtay konektörü.

    List endpoint:
      POST https://bedesten.adalet.gov.tr/emsal-karar/searchDocuments
    Detail endpoint (HTML view):
      GET  https://mevzuat.adalet.gov.tr/ictihat/{id}
    """

    source = "YARGITAY"  # DocID uyumluluğu için aynı kaynak adı tutuluyor
    SEARCH_URL = "https://bedesten.adalet.gov.tr/emsal-karar/searchDocuments"
    DOC_URL = "https://bedesten.adalet.gov.tr/emsal-karar/getDocumentContent"
    VIEW_URL = "https://mevzuat.adalet.gov.tr/ictihat/{id}"

    logger = structlog.get_logger(__name__)
    MAX_ROWS_PER_WINDOW = 25000

    def __init__(
        self,
        page_size: int = 100,
        item_type_list: Optional[list] = None,
        use_live: bool = True,
        headless: bool = True,  # run_connector arayüzü ile uyum için tutuldu
        timeout: float = 30.0,
        window_days: int = 7,
        use_browser_fallback: bool = False,
    ) -> None:
        self.page_size = page_size
        self.item_type_list = item_type_list or ["YARGITAYKARARI"]
        self.window_days = window_days
        self.use_live = use_live
        self.headless = headless
        self.use_browser_fallback = use_browser_fallback
        self.base_headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate, br",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://mevzuat.adalet.gov.tr",
            "Referer": "https://mevzuat.adalet.gov.tr/",
            "Accept-Language": "tr-TR,tr;q=0.9",
            "adaletapplicationname": "UyapMevzuat",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        }
        self.timeout = timeout
        self.proxy_pool = _load_proxies_from_env()
        self._proxy_cycle = itertools.cycle(self.proxy_pool) if self.proxy_pool else None
        self.client = self._make_client()
        self.session: PlaywrightSession | None = None
        if self.use_browser_fallback:
            self.session = PlaywrightSession(headless=self.headless, executable_path=None)

    def list_items(self, since: date, until: date | None = None) -> Iterable[ItemRef]:
        end = until or date.today()
        cursor = since
        seen_keys: set[str] = set()

        while cursor <= end:
            win_start = cursor
            win_end = min(end, cursor + timedelta(days=self.window_days) - timedelta(days=1))
            yield from self._list_window(win_start, win_end, seen_keys)
            cursor = win_end + timedelta(days=1)

    def fetch(self, ref: ItemRef) -> RawDoc:
        doc_id = ref.metadata.get("doc_id")
        url = self.VIEW_URL.format(id=doc_id) if doc_id else ref.url
        html = ""
        if doc_id:
            html = self._fetch_via_api(doc_id)
        if not html.strip():
            resp = self._get_with_retry(url)
            html = resp.text
        html = _maybe_decode_base64_html(html)
        if self.use_browser_fallback and _looks_empty(html):
            try:
                html = self._fetch_via_browser(url)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("yargitay_browser_fallback_failed", url=url, error=str(exc))
        return RawDoc(ref=ref, content_html=html)

    def parse(self, raw: RawDoc) -> CanonDoc:
        tree = HTMLParser(raw.content_html or "")

        chamber = raw.ref.metadata.get("chamber", "")
        e_no = raw.ref.metadata.get("e_no", "")
        k_no = raw.ref.metadata.get("k_no", "")
        decision_date_text = raw.ref.metadata.get("decision_date", "")

        parsed_meta = _extract_meta_fields(tree)
        chamber = parsed_meta.get("chamber") or chamber
        e_no = parsed_meta.get("e_no") or e_no
        k_no = parsed_meta.get("k_no") or k_no
        decision_date_text = parsed_meta.get("decision_date") or decision_date_text

        decision_date, decision_date_text = _parse_decision_date(decision_date_text)

        title = parsed_meta.get("title") or "Karar"
        processed_text = _extract_body_text(tree)
        if not processed_text:
            processed_text = _clean_html_text(raw.content_html or "")
        processed_text = normalize_text(unicodedata.normalize("NFKC", processed_text))

        if not processed_text.strip():
            processed_text = "Metin alınamadı"

        normalized_chamber = normalize_chamber(chamber) or chamber or "unknown"
        quality_flag = "ok"
        doc_id_date = decision_date or decision_date_text or "unknown"
        checksum_text = processed_text
        if processed_text == "Metin alınamadı":
            quality_flag = "no_text"
            fallback = "|".join(
                part for part in [normalized_chamber or chamber, e_no or "", k_no or "", str(doc_id_date)] if part
            )
            checksum_text = fallback or "no_text"

        checksum = doc_checksum(checksum_text)
        doc_id_base = build_decision_doc_id("YARGITAY", normalized_chamber, e_no, k_no, doc_id_date)
        if ("unknown" in str(doc_id_base)) or (not e_no) or (not k_no):
            bed_id = raw.ref.metadata.get("doc_id")
            if bed_id:
                doc_id_base = f"yargitay:bedesten:{bed_id}"
        doc_id = doc_id_base
        legal_topic_tags = infer_topic_tags(processed_text)

        item_type = (raw.ref.metadata.get("item_type") or "").upper()
        chamber_txt = (raw.ref.metadata.get("chamber") or "").upper()
        court = "Yargıtay"
        if "ISTINAF" in item_type or "BAM" in chamber_txt:
            court = "Bölge Adliye Mahkemesi"
        elif "GENEL KURUL" in chamber_txt:
            court = "Yargıtay Genel Kurulu"

        return CanonDoc(
            doc_id=doc_id,
            source=self.source,
            doc_type="karar",
            title=title,
            url=raw.ref.url,
            checksum=checksum,
            decision_date=decision_date,
            chamber=normalized_chamber,
            court=court,
            text=processed_text,
            meta={
                "e_no": e_no,
                "k_no": k_no,
                "decision_date_text": decision_date_text,
                "legal_topic_tags": legal_topic_tags,
                "chunk_version": 1,
                "embed_version": 1,
                "quality_flag": quality_flag,
                "bedesten_id": raw.ref.metadata.get("doc_id"),
                "year": (decision_date.isoformat()[:4] if decision_date else (decision_date_text or "")[:4]),
            },
            raw=raw,
        )

    def chunk(self, doc: CanonDoc):
        text = doc.text or ""
        if text == "Metin alınamadı":
            return chunk_decision(doc, "", [])
        sections = split_sections(text)
        return chunk_sections(doc, sections)

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass

    def _make_client(self, proxy: str | None = None) -> httpx.Client:
        return httpx.Client(
            http2=False,
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
            timeout=self.timeout,
            headers=self.base_headers,
            proxies=proxy or None,
        )

    def _build_payload(self, start: date, end: date, page: int) -> dict:
        start_dt = datetime(start.year, start.month, start.day)
        end_dt = datetime(end.year, end.month, end.day, 23, 59, 59)
        types = self.item_type_list if self.item_type_list else ["YARGITAYKARARI"]
        return {
            "applicationName": "UyapMevzuat",
            "paging": True,
            "data": {
                "pageSize": self.page_size,
                "pageNumber": page,
                "kararTarihiStart": start_dt.strftime(ISO_WITH_MS),
                "kararTarihiEnd": end_dt.strftime(ISO_WITH_MS),
                "itemTypeList": types,
                "orderByList": [
                    {"field": "kararTarihi", "order": "ASC"},
                    {"field": "documentId", "order": "ASC"},
                ],
            },
        }

    def _emit_items(self, rows: List[dict], seen_keys: set[str], window_seen: set[str]) -> Iterable[ItemRef]:
        for row in rows:
            item = _item_from_row(row, self.source, self.VIEW_URL)
            if not item:
                continue
            window_seen.add(item.key)
            if item.key in seen_keys:
                continue
            seen_keys.add(item.key)
            yield item

    def _list_window(self, win_start: date, win_end: date, seen_keys: set[str]) -> Iterable[ItemRef]:
        proxy = next(self._proxy_cycle) if self._proxy_cycle else None
        client = self._make_client(proxy)
        window_seen: set[str] = set()
        try:
            payload = self._build_payload(win_start, win_end, page=1)
            resp = self._post_with_retry(payload, client)
            blob = resp.json()
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(
                "yargitay_list_error",
                window_start=win_start.isoformat(),
                window_end=win_end.isoformat(),
                error=str(exc),
            )
            client.close()
            return []

        rows, total = _extract_rows_and_total(blob)
        # Boş geldi ama total varsa 0-index dene
        if total and not rows:
            alt_payload = self._build_payload(win_start, win_end, page=0)
            try:
                alt_resp = self._post_with_retry(alt_payload, client)
                alt_blob = alt_resp.json()
                alt_rows, alt_total = _extract_rows_and_total(alt_blob)
                if alt_rows:
                    rows = alt_rows
                    total = total or alt_total
            except Exception:
                pass

        if total and total > self.MAX_ROWS_PER_WINDOW and (win_end - win_start).days > 1:
            mid = win_start + (win_end - win_start) // 2
            if mid > win_start:
                yield from self._list_window(win_start, mid, seen_keys)
                yield from self._list_window(mid + timedelta(days=1), win_end, seen_keys)
                client.close()
                return

        # Total var ama hiç satır yoksa logla ve gerekirse böl/bitir
        if total and not rows:
            if win_end <= win_start:
                self.logger.warning(
                    "yargitay_empty_rows",
                    window_start=win_start.isoformat(),
                    window_end=win_end.isoformat(),
                    expected=total,
                )
                client.close()
                return
            mid = win_start + (win_end - win_start) // 2
            yield from self._list_window(win_start, mid, seen_keys)
            yield from self._list_window(mid + timedelta(days=1), win_end, seen_keys)
            client.close()
            return

        fetched = 0
        for item in self._emit_items(rows, seen_keys, window_seen):
            fetched += 1
            yield item

        page = 1
        while rows and (total is None or fetched < total):
            page += 1
            payload = self._build_payload(win_start, win_end, page=page)
            try:
                resp = self._post_with_retry(payload, client)
                blob = resp.json()
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(
                    "yargitay_list_page_error",
                    page=page,
                    window_start=win_start.isoformat(),
                    window_end=win_end.isoformat(),
                    error=str(exc),
                )
                break
            rows, total_next = _extract_rows_and_total(blob)
            if total is None and total_next is not None:
                total = total_next
            if not rows:
                break
            for row_item in self._emit_items(rows, seen_keys, window_seen):
                fetched += 1
                yield row_item
            if total is None and len(rows) < self.page_size:
                break

        observed = len(window_seen)
        if total and observed < total:
            self.logger.warning(
                "yargitay_missing_rows",
                window_start=win_start.isoformat(),
                window_end=win_end.isoformat(),
                expected=total,
                fetched=observed,
            )
            if (win_end - win_start).days >= 1:
                mid = win_start + (win_end - win_start) // 2
                yield from self._list_window(win_start, mid, seen_keys)
                yield from self._list_window(mid + timedelta(days=1), win_end, seen_keys)

        client.close()

    def _post_with_retry(self, payload: dict, client: httpx.Client | None = None, attempts: int = 3) -> httpx.Response:
        for attempt in range(attempts):
            try:
                cli = client or self.client
                resp = cli.post(self.SEARCH_URL, json=payload)
                if resp.status_code == 429:
                    ra = resp.headers.get("Retry-After")
                    if ra:
                        try:
                            time.sleep(float(ra))
                        except Exception:
                            pass
                    raise httpx.HTTPStatusError(
                        f"status {resp.status_code}", request=resp.request, response=resp
                    )
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"status {resp.status_code}", request=resp.request, response=resp
                    )
                return resp
            except Exception:
                if attempt == attempts - 1:
                    raise
                delay = (1.5 ** attempt) + random.uniform(0.2, 0.6)
                time.sleep(delay)

    def _get_with_retry(self, url: str, attempts: int = 3) -> httpx.Response:
        for attempt in range(attempts):
            try:
                resp = self.client.get(url)
                if resp.status_code == 429:
                    ra = resp.headers.get("Retry-After")
                    if ra:
                        try:
                            time.sleep(float(ra))
                        except Exception:
                            pass
                    raise httpx.HTTPStatusError(
                        f"status {resp.status_code}", request=resp.request, response=resp
                    )
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"status {resp.status_code}", request=resp.request, response=resp
                    )
                return resp
            except Exception:
                if attempt == attempts - 1:
                    raise
                delay = (1.5 ** attempt) + random.uniform(0.2, 0.6)
                time.sleep(delay)

    def _fetch_via_api(self, doc_id: str) -> str:
        payload = {"data": {"documentId": str(doc_id)}, "applicationName": "UyapMevzuat"}
        try:
            resp = self.client.post(self.DOC_URL, json=payload)
            if not resp.is_success:
                self.logger.warning("api_error", status=resp.status_code, doc_id=doc_id)
                return ""
            try:
                data = resp.json()
                html = _doc_from_payload(data)
            except Exception:
                html = resp.text
            if html and len(html.strip()) > 50:
                return html
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("api_fetch_exception", error=str(exc), doc_id=doc_id)
        return ""

    def _fetch_via_browser(self, url: str) -> str:
        if not self.session:
            raise RuntimeError("browser fallback session is not available")
        page = self.session.new_page()
        page.set_default_timeout(60000)
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(1200)
            container = page.locator(
                ".card-scroll, .content, article, .decision-text, .panel-body, .tab-content, #printArea"
            ).first
            if container.count():
                return container.inner_text()
            printable = page.locator("xpath=//div[contains(@class,'card') and .//text()]").first
            if printable.count():
                return printable.inner_text()
            return page.content()
        finally:
            try:
                page.close()
            except Exception:
                pass

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass
        try:
            if self.session:
                self.session.close()
        except Exception:
            pass


def _looks_empty(html: str, threshold: int = 80) -> bool:
    if not html or len(html) < threshold:
        return True
    try:
        tree = HTMLParser(html)
        text = (
            tree.body.text(separator="\n", strip=True)
            if tree.body
            else tree.text(separator="\n", strip=True)
        )
        return len(text.strip()) < threshold
    except Exception:
        return False


# Backward compatibility: keep the old class name expected by scripts/run_connector.py
class YargitayConnector(Yargitay2Connector):
    pass


def _item_from_row(row: dict, source: str, view_url: str) -> ItemRef | None:
    chamber = _pick(row, ["birimAdi", "daireAdi", "daire", "daireadi", "daireAd", "kurum"])
    e_no = _pick(row, ["esasNo", "esas", "esasno", "esasNumarasi"])
    if not e_no:
        e_no = _compose_case(row.get("esasNoYil"), row.get("esasNoSira"))
    k_no = _pick(row, ["kararNo", "karar", "kararno", "kararNumarasi"])
    if not k_no:
        k_no = _compose_case(row.get("kararNoYil"), row.get("kararNoSira"))
    dt = _pick(row, ["kararTarihiStr", "kararTarihi", "tarih", "decisionDate"])
    doc_id = _pick(row, ["documentId", "id", "docId", "dokumanId", "dokumanID"])

    if not any([chamber, e_no, k_no, dt, doc_id]):
        return None

    normalized_chamber = normalize_chamber(chamber) or chamber
    normalized_e_no = normalize_case_number(e_no)
    normalized_k_no = normalize_case_number(k_no)
    key = f"{source}:{normalized_chamber}:{normalized_e_no}-{normalized_k_no}:{dt or doc_id or 'unknown'}"

    url = view_url.format(id=doc_id) if doc_id else Yargitay2Connector.SEARCH_URL
    metadata = {
        "chamber": normalized_chamber,
        "e_no": normalized_e_no,
        "k_no": normalized_k_no,
        "decision_date": dt,
        "doc_id": doc_id,
    }
    if row.get("birimId"):
        metadata["birim_id"] = row.get("birimId")
    item_type = row.get("itemType")
    if isinstance(item_type, dict):
        metadata["item_type"] = item_type.get("name") or item_type.get("description")

    return ItemRef(key=key, url=url, metadata=metadata)


def _extract_rows_and_total(blob: dict) -> tuple[list[dict], Optional[int]]:
    rows: list[dict] = []
    total = None
    if not isinstance(blob, dict):
        return rows, total
    data = blob.get("data")
    if isinstance(data, dict):
        if isinstance(data.get("emsalKararList"), list):
            rows = [r for r in data.get("emsalKararList", []) if isinstance(r, dict)]
        elif isinstance(data.get("data"), list):
            rows = [r for r in data.get("data", []) if isinstance(r, dict)]
        elif isinstance(data.get("results"), list):
            rows = [r for r in data.get("results", []) if isinstance(r, dict)]
        total = (
            data.get("recordsTotal")
            or data.get("totalElements")
            or data.get("total")
            or data.get("totalCount")
            or data.get("recordCount")
        )
    elif isinstance(data, list):
        rows = [r for r in data if isinstance(r, dict)]
        total = blob.get("recordsTotal") or blob.get("totalElements") or blob.get("total") or blob.get("totalCount")
    if isinstance(total, str) and total.isdigit():
        total = int(total)
    if total is not None and not isinstance(total, int):
        total = None
    return rows, total


def _parse_decision_date(value: str) -> tuple[date | None, str | None]:
    cleaned = (value or "").strip()
    if not cleaned:
        return None, None

    iso_candidate = cleaned.rstrip("Z")
    try:
        return datetime.fromisoformat(iso_candidate).date(), None
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(cleaned, fmt).date(), None
        except ValueError:
            continue

    return None, cleaned


def _extract_meta_fields(tree: HTMLParser) -> dict:
    meta = {"title": None, "chamber": None, "e_no": None, "k_no": None, "decision_date": None}
    try:
        h = tree.css_first("h1, h2, .title")
        if h:
            meta["title"] = h.text(strip=True)

        labels = tree.css("b, strong, label, .label")
        for lb in labels or []:
            text = (lb.text(strip=True) or "").upper()
            val = lb.next.text(strip=True) if isinstance(lb.next, Node) else ""
            if "DAİRE" in text:
                meta["chamber"] = val
            elif "ESAS" in text:
                meta["e_no"] = val
            elif "KARAR" in text and "NO" in text:
                meta["k_no"] = val
            elif "KARAR TARİH" in text or "TARİH" in text:
                meta["decision_date"] = val
    except Exception:
        return meta
    return meta


def _extract_body_text(tree: HTMLParser) -> str:
    try:
        container = tree.css_first(".card-scroll, .content, article, .decision-text, .panel-body, .tab-content, #printArea")
        if container:
            return container.text(separator="\n", strip=True)
        return tree.body.text(separator="\n", strip=True) if tree.body else ""
    except Exception:
        return ""


def _load_proxies_from_env() -> list[str]:
    raw = os.environ.get("YARGITAY_PROXIES", "")
    if not raw.strip():
        return []
    proxies: list[str] = []
    for entry in raw.replace("\n", ",").split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "://" not in entry:
            proxies.append(f"http://{entry}")
        else:
            proxies.append(entry)
    random.shuffle(proxies)
    return proxies


def _clean_html_text(html: str) -> str:
    try:
        parser = HTMLParser(html or "")
        for tag in parser.css("script, style, link, meta"):
            tag.remove()
        root = parser.body or parser
        return root.text(separator="\n", strip=True)
    except Exception:
        return html or ""


def _pick(row: dict, keys: list[str]) -> str:
    for key in keys:
        if key in row and row[key]:
            return str(row[key]).strip()
    return ""


def _compose_case(year_val, seq_val) -> str:
    if year_val is None or seq_val is None:
        return ""
    try:
        return f"{int(year_val)}/{int(seq_val)}"
    except Exception:
        return f"{year_val}/{seq_val}"


def _doc_from_payload(payload) -> str:
    if payload is None:
        return ""

    if isinstance(payload, str):
        return _maybe_decode_base64_html(payload)

    if isinstance(payload, dict):
        data_content = payload.get("data")
        if isinstance(data_content, dict):
            for key in ("data", "icerik", "content", "html", "belgeIcerik"):
                val = data_content.get(key)
                if isinstance(val, str) and val:
                    return _maybe_decode_base64_html(val)
        elif isinstance(data_content, str):
            return _maybe_decode_base64_html(data_content)

        for key in ("icerik", "content", "html", "dokuman"):
            val = payload.get(key)
            if isinstance(val, str):
                return _maybe_decode_base64_html(val)

    return ""


def _looks_empty(html: str, threshold: int = 80) -> bool:
    if not html or len(html) < threshold:
        return True
    try:
        tree = HTMLParser(html)
        text = (
            tree.body.text(separator="\n", strip=True)
            if tree.body
            else tree.text(separator="\n", strip=True)
        )
        return len(text.strip()) < threshold
    except Exception:
        return False


def _maybe_decode_base64_html(html: str) -> str:
    """Base64 ile kodlanmış olabilecek HTML'i çözer."""
    if not html:
        return html

    stripped = html.strip()
    # Çok kısa veya zaten HTML etiketi içeriyorsa dokunma
    if len(stripped) < 20 or ("<html" in stripped.lower() and ">" in stripped):
        return html

    # Base64 karakter seti kontrolü
    if not all(c.isalnum() or c in "+/=\n\r" or c.isspace() for c in stripped):
        return html

    try:
        import base64

        missing_padding = len(stripped) % 4
        if missing_padding:
            stripped += "=" * (4 - missing_padding)
        decoded_bytes = base64.b64decode(stripped, validate=True)
        decoded_txt = decoded_bytes.decode("utf-8", errors="ignore")
        keywords = ["<html", "<body", "<meta", "mahkeme", "karar", "dava", "esas no", "t.c."]
        if any(k in decoded_txt.lower() for k in keywords):
            return decoded_txt
    except Exception:
        return html

    return html
