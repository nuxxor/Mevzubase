from __future__ import annotations

# Not: EMSAL UYAP Detaylı Arama, Yargıtay ile benzer iki JSON uç noktası kullanıyor:
#   - aramadetaylist  => liste (daire, esas/karar no, tarih, doküman id)
#   - getDokuman      => doküman gövdesi (HTML string) id ile
# Liste/detay JSON yakalanır; yoksa DOM geri yolu devreye girer. Bu, scraping hızını birkaç kat artırır.

import os
import random
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, List, Optional

import structlog
from selectolax.parser import HTMLParser, Node

from src.core.chunking import chunk_decision
from src.core.decision_chunker import chunk_sections, normalize_text, split_sections
from src.core.legal import infer_topic_tags, normalize_case_number, normalize_chamber
from src.core.schema import CanonDoc, ItemRef, RawDoc, build_decision_doc_id
from src.core.versioning import doc_checksum

from .base import BaseConnector
from .playwright_session import PlaywrightSession


DATE_FMT_UI = "%d.%m.%Y"


class EmsalConnector(BaseConnector):
    source = "EMSAL"
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
                key=f"{self.source}:Daire:E2024/500-K2025/900:2025-03-12",
                url="https://emsal.uyap.gov.tr/sample",
                metadata={"fixture": "emsal_sample.html"},
            )
            return
        for item in self._list_items_live(since, until):
            yield item

    def fetch(self, ref: ItemRef) -> RawDoc:
        if not self.use_live:
            path = self.fixture_dir / ref.metadata.get("fixture", "emsal_sample.html")
            html = path.read_text(encoding="utf-8")
            return RawDoc(ref=ref, content_html=html)
        html = self._fetch_detail_live(ref)
        return RawDoc(ref=ref, content_html=html)

    def parse(self, raw: RawDoc) -> CanonDoc:
        tree = HTMLParser(raw.content_html or "")
        chamber = _text_or(tree.css_first(".court")) or raw.ref.metadata.get("chamber", "")
        e_no = (_text_or(tree.css_first(".e")) or raw.ref.metadata.get("e_no", "")).replace(
            "E.", ""
        ).strip()
        k_no = (_text_or(tree.css_first(".k")) or raw.ref.metadata.get("k_no", "")).replace(
            "K.", ""
        ).strip()
        date_txt = (
            _text_or(tree.css_first(".t")) or raw.ref.metadata.get("decision_date", "")
        ).replace("T.", "").strip()
        decision_date, decision_date_text = _parse_decision_date(date_txt)
        title = _text_or(tree.css_first(".title")) or "Karar"

        # Metin çıkarma: önce başlık/özet/gerekçe alanlarını tara, yoksa tüm p'leri birleştir.
        summary = _text_or(tree.css_first(".summary")) or ""
        reasoning_nodes = tree.css(".reasoning p")
        reasoning = [p.text(separator="\n", strip=True) for p in reasoning_nodes]
        if not reasoning:
            reasoning = [
                p.text(separator="\n", strip=True) for p in tree.css("p") if len(p.text(strip=True)) > 30
            ]
        processed_text = "\n".join(line.strip() for line in [summary, *reasoning] if line.strip())
        
        if not processed_text and raw.content_html:
            processed_text = _clean_html_text(raw.content_html)

        processed_text = normalize_text(processed_text)

        is_junk = False
        junk_indicators = ["recordsTotal", "draw:", "lengthMenu", "pixel-ratio", "windowHeight", "DataTable"]
        if any(ind in processed_text for ind in junk_indicators):
            is_junk = True
        
        if is_junk or not processed_text.strip():
            processed_text = "Metin alınamadı"

        normalized_chamber = normalize_chamber(chamber) or chamber or "unknown"
        quality_flag = "ok"
        checksum_text = processed_text
        if processed_text in ("", "Metin alınamadı"):
            quality_flag = "no_text"
            fallback = "|".join(
                part
                for part in [normalized_chamber or chamber, e_no or "", k_no or "", str(doc_id_date)]
                if part
            )
            checksum_text = fallback or "no_text"

        checksum = doc_checksum(checksum_text)
        doc_id_date = decision_date or decision_date_text or "unknown"
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
            court="EMSAL UYAP",
            text=processed_text,
            meta={
                "e_no": e_no,
                "k_no": k_no,
                "decision_date_text": decision_date_text,
                "legal_topic_tags": legal_topic_tags,
                "chunk_version": 2,
                "embed_version": 2,
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

    def _list_items_live(self, since: date, until: date | None = None) -> List[ItemRef]:
        items: List[ItemRef] = []
        json_rows: list[dict] = []
        seen_keys: set[str] = set()
        page = self.session.new_page()

        def _capture(resp):
            try:
                ct = (resp.headers.get("content-type") or "").lower()
                if "application/json" in ct and self.LIST_ENDPOINT_HINT in resp.url:
                    data = resp.json()
                    json_rows.extend(_extract_json_rows(data))
            except Exception:
                return

        page.on("response", _capture)
        try:
            page.goto("https://emsal.uyap.gov.tr/", wait_until="domcontentloaded")
            self._human_delay()
            page.get_by_text("Detaylı Arama", exact=False).click()
            end_target = until or date.today()
            self._fill_date_range(
                page,
                since.strftime(DATE_FMT_UI),
                end_target.strftime(DATE_FMT_UI),
            )
            self._human_delay()
            page.get_by_role("button", name=re.compile("Ara", re.I)).click()
            page.wait_for_timeout(1200)

            if json_rows:
                for row in json_rows:
                    item = _item_from_row(row, page.url, self.source)
                    if item and item.key not in seen_keys:
                        items.append(item)
                        seen_keys.add(item.key)

            try:
                page.wait_for_selector("table tbody tr", timeout=5000)
            except Exception:
                _debug_dump(page, "emsal_no_rows")
                return items
            
            table = page.locator("table tbody tr")
            while True:
                row_count = table.count()
                if row_count == 0:
                    break
                for i in range(row_count):
                    cells = table.nth(i).locator("td")
                    chamber = cells.nth(0).inner_text().strip()
                    e_no = cells.nth(1).inner_text().strip()
                    k_no = cells.nth(2).inner_text().strip()
                    dt = cells.nth(3).inner_text().strip()
                    status = cells.nth(4).inner_text().strip()
                    decision_date = _normalize_date(dt)
                    normalized_chamber = normalize_chamber(chamber) or chamber
                    normalized_e = normalize_case_number(e_no)
                    normalized_k = normalize_case_number(k_no)
                    key = f"{self.source}:{normalized_chamber}:{normalized_e}-{normalized_k}:{decision_date}"
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    items.append(
                        ItemRef(
                            key=key,
                            url=page.url,
                            metadata={
                                "chamber": normalized_chamber,
                                "e_no": normalized_e,
                                "k_no": normalized_k,
                                "decision_date": dt,
                                "decision_status": status,
                            },
                        )
                    )
                next_candidates = page.get_by_role("button", name=re.compile("Sonraki", re.I))
                if next_candidates.count() == 0:
                    break
                next_btn = next_candidates.first
                try:
                    if not next_btn.is_visible(timeout=2000) or not next_btn.is_enabled(timeout=2000):
                        break
                    if "disabled" in (next_btn.get_attribute("class") or ""):
                        break
                except Exception:
                    break
                next_btn.click()
                page.wait_for_timeout(700)
        finally:
            page.close()
        return items


    def _fetch_detail_live(self, ref: ItemRef) -> str:
        html_content = self._fetch_via_template(ref.metadata.get("doc_id"))
        if html_content:
            return html_content

        doc_payload: list = []
        page = self.session.new_page()

        def _capture(resp):
            try:
                if self.DOC_ENDPOINT_HINT in resp.url:
                    self.session.remember_doc_request(resp, ref.metadata.get("doc_id"))
                    ct = (resp.headers.get("content-type") or "").lower()
                    if "application/json" in ct:
                        doc_payload.append(resp.json())
                    else:
                        doc_payload.append(resp.text())
            except Exception:
                return

        page.on("response", _capture)
        try:
            page.goto("https://emsal.uyap.gov.tr/", wait_until="domcontentloaded")
            self._human_delay()
            page.get_by_text("Detaylı Arama", exact=False).click()
            self._human_delay()

            d_date = ref.metadata.get("decision_date") or date.today().strftime(DATE_FMT_UI)
            self._fill_date_range(page, d_date, d_date)
            self._fill_file_numbers(page, ref.metadata.get("e_no"), "Esas")
            self._fill_file_numbers(page, ref.metadata.get("k_no"), "Karar")

            adv_panel = page.locator("xpath=//div[contains(@class,'card') and .//text()[contains(., 'BİRİMLER')]]").first
            if adv_panel.count() > 0:
                search_btn = adv_panel.get_by_role("button", name=re.compile(r"^Ara$", re.I)).first
            else:
                search_btn = page.get_by_role("button", name=re.compile(r"^Ara$", re.I)).last

            with page.expect_response(lambda r: r.ok, timeout=4000):
                search_btn.click()

            page.wait_for_function(
                """
                () => document.querySelector('table tbody tr')
                   || (document.body && document.body.innerText.includes('0 adet karar bulundu'))
                """,
                timeout=5000,
            )

            rows = page.locator("table tbody tr")
            if rows.count() == 0:
                return ""

            row = rows.first
            try:
                row.scroll_into_view_if_needed()
                with page.expect_response(lambda r: self.DOC_ENDPOINT_HINT in r.url and r.ok, timeout=5000) as resp_info:
                    row.click()
                resp = resp_info.value
                ct = (resp.headers.get("content-type") or "").lower()
                if "application/json" in ct:
                    html_content = _doc_from_payload(resp.json())
                else:
                    html_content = _clean_html_text(resp.text())
            except Exception:
                html_content = ""

            if not html_content.strip():
                header = page.locator("xpath=//h4[contains(., 'Metn')]").first
                try:
                    if header.is_visible():
                        header.click(timeout=1000)
                except Exception:
                    pass

                panel = page.locator(".card-scroll").first
                if not panel.count() and header.count():
                    panel = header.locator("xpath=following-sibling::*[1]").first

                try:
                    panel.wait_for(state="visible", timeout=3000)
                    html_content = _clean_html_text(panel.inner_html())
                except Exception:
                    pass

        except Exception as exc:
            self.logger.warning("emsal_detail_error", error=str(exc), key=ref.key)
            html_content = ""
        finally:
            page.close()

        return html_content
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

    def _fill_file_numbers(self, page, number_str, type_prefix):
        """Esas/Karar numaralarını (Yıl/Sıra) inputlara doldurur."""
        if not number_str:
            return
        year_match = re.search(r"(\d{4})", number_str)
        seq_match = re.search(r"/(\d+)", number_str)
        
        if year_match:
            ph = re.compile(f"{type_prefix} y", re.I)
            self._force_input(page, ph, year_match.group(1))
            
        if seq_match:
            seq_val = seq_match.group(1)
            ph = re.compile(f"{type_prefix} sıra no", re.I) # Placeholder regex
            # EMSAL'de "İlk" ve "Son" sıra no inputları var, her ikisine de aynı değeri yazalım
            inputs = page.get_by_placeholder(re.compile("ilk|son", re.I))
            # Bu kısım biraz hassas, sayfadaki input sırasına göre:
            # Genellikle Esas İlk/Son, sonra Karar İlk/Son gelir.
            # type_prefix ile ayrıştırmak zor olabilir, bu yüzden tüm ilgili inputları bulup dolduruyoruz
            # Ancak daha güvenli yol:
            
            if type_prefix == "Esas":
                # Esas yıl ve no inputlarını bulmaya çalış
                # En basit yöntem: placeholder'ında 'Esas' geçenleri bulmak ama placeholder 'İlk sıra no' sadece.
                # Bu yüzden locator indeksleri kullanmak daha güvenli (fetch metodunda yaptığınız gibi)
                first_inputs = page.get_by_placeholder(re.compile("İlk sıra no", re.I))
                last_inputs = page.get_by_placeholder(re.compile("Son sıra no", re.I))
                # Esas genellikle 0. indeks
                if first_inputs.count() > 0:
                    self._force_input_loc(first_inputs.nth(0), seq_val)
                if last_inputs.count() > 0:
                    self._force_input_loc(last_inputs.nth(0), seq_val)
            
            elif type_prefix == "Karar":
                # Karar genellikle 1. indeks
                first_inputs = page.get_by_placeholder(re.compile("İlk sıra no", re.I))
                last_inputs = page.get_by_placeholder(re.compile("Son sıra no", re.I))
                if first_inputs.count() > 1:
                    self._force_input_loc(first_inputs.nth(1), seq_val)
                if last_inputs.count() > 1:
                    self._force_input_loc(last_inputs.nth(1), seq_val)

    def _force_input(self, page, placeholder, value):
        loc = page.get_by_placeholder(placeholder)
        if loc.count():
            self._force_input_loc(loc.first, value)

    def _force_input_loc(self, locator, value):
        try:
            locator.evaluate(
                f"""(el) => {{
                    el.removeAttribute('readonly');
                    el.value = '{value}';
                    el.dispatchEvent(new Event('input', {{bubbles:true}}));
                    el.dispatchEvent(new Event('change', {{bubbles:true}}));
                }}"""
            )
        except Exception:
            pass

    def _log_case_mismatch(self, metadata: dict | None, field: str, parsed_value: str | None) -> None:
        if not metadata:
            return
        expected = metadata.get(field)
        if not expected or not parsed_value:
            return
        if normalize_case_number(expected) != normalize_case_number(parsed_value):
            self.logger.warning(
                "emsal_meta_mismatch",
                field=field,
                expected=expected,
                parsed=parsed_value,
            )

    def _human_delay(self, min_ms: int = 300, max_ms: int = 1200) -> None:
        time.sleep(random.uniform(min_ms, max_ms) / 1000)

    def close(self) -> None:
        if hasattr(self, "session"):
            self.session.close()
    @staticmethod
    def _fill_date_range(page, start: str, end: str) -> None:
        start_ph = "Başlama tarihini giriniz."
        end_ph = "Bitiş tarihini giriniz."

        def force_fill(ph: str, value: str) -> bool:
            loc = page.get_by_placeholder(ph)
            if not loc.count():
                return False
            try:
                loc.first.evaluate(
                    f"""
                    (el) => {{
                      el.removeAttribute('readonly');
                      el.value = '{value}';
                      el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                      el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                    """
                )
                return True
            except Exception:
                return False

        ok_start = force_fill(start_ph, start)
        ok_end = force_fill(end_ph, end)


def _text_or(node: Optional[Node]) -> str:
    return node.text(strip=True) if node else ""


def _clean_html_text(html: str) -> str:
    try:
        parser = HTMLParser(html or "")
        for tag in parser.css("script, style, link, meta"):
            tag.remove()
        # Sadece içerik container'ını hedefle
        container = parser.css_first(".card-scroll") or parser.body or parser
        return container.text(separator="\n", strip=True)
    except Exception:
        return html or ""


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


def _normalize_date(dt: str) -> str:
    parts = dt.split(".")
    if len(parts) != 3:
        return dt
    return f"{parts[2]}-{parts[1]}-{parts[0]}"



def _debug_dump(page, prefix: str) -> None:
    try:
        html = page.content()
        Path(f"/tmp/{prefix}.html").write_text(html, encoding="utf-8")
    except Exception:
        pass
    try:
        page.screenshot(path=f"/tmp/{prefix}.png", full_page=True)
    except Exception:
        pass


def _extract_json_rows(data) -> list[dict]:
    rows: list[dict] = []
    try:
        if isinstance(data, list):
            rows = [el for el in data if isinstance(el, dict)]
        elif isinstance(data, dict):
            for key in ("data", "results", "rows"):
                if isinstance(data.get(key), list):
                    rows.extend([el for el in data[key] if isinstance(el, dict)])
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
    chamber = _pick(row, ["daire", "daireAdi", "daireadi", "daireAd", "daire_ad", "BIRIM_ADI"])
    e_no = _pick(row, ["esas", "esasNo", "esasno", "esasNoStr", "esas_numarasi", "esasNumarasi", "ESAS_NO"])
    k_no = _pick(row, ["karar", "kararNo", "kararno", "kararNoStr", "karar_numarasi", "kararNumarasi", "KARAR_NO"])
    dt = _pick(row, ["kararTarihi", "tarih", "kararTarih", "kararTarihiStr", "kararTarihStr", "DECISION_DATE", "KARAR_TARIHI"])
    doc_id = _pick(row, ["id", "dokumanId", "dokumanID", "docId", "documentId", "kararId", "DOKUMAN_ID"])
    status = _pick(row, ["durum", "status", "kararDurumu"])

    if not any([chamber, e_no, k_no, dt]):
        return None

    normalized_chamber = normalize_chamber(chamber) or chamber
    normalized_e = normalize_case_number(e_no)
    normalized_k = normalize_case_number(k_no)
    key = f"{source}:{normalized_chamber}:{normalized_e}-{normalized_k}:{dt}"
    meta = {
        "chamber": normalized_chamber,
        "e_no": normalized_e,
        "k_no": normalized_k,
        "decision_date": dt,
        "decision_status": status,
    }
    if doc_id:
        meta["doc_id"] = doc_id
    return ItemRef(key=key, url=url, metadata=meta)


def _doc_from_payload(payload) -> str:
    if payload is None:
        return ""
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
