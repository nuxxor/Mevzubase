from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from selectolax.parser import HTMLParser

from src.core.chunking import chunk_bullet_items
from src.core.schema import CanonDoc, ItemRef, RawDoc, build_regulation_doc_id
from src.core.versioning import doc_checksum

from .base import BaseConnector


class SPKConnector(BaseConnector):
    source = "SPK"

    def __init__(self, fixture_dir: str | Path | None = None) -> None:
        self.fixture_dir = Path(fixture_dir or Path(__file__).resolve().parents[2] / "tests/fixtures/sample_html")

    def list_items(self, since: date) -> Iterable[ItemRef]:
        ref = ItemRef(
            key=f"{self.source}:2025/58",
            url="https://spk.gov.tr/bultenler/2025/58",
            metadata={"fixture": "spk_sample.html"},
        )
        yield ref

    def fetch(self, ref: ItemRef) -> RawDoc:
        path = self.fixture_dir / ref.metadata.get("fixture", "spk_sample.html")
        html = path.read_text(encoding="utf-8")
        return RawDoc(ref=ref, content_html=html)

    def parse(self, raw: RawDoc) -> CanonDoc:
        tree = HTMLParser(raw.content_html or "")
        title = tree.css_first("h1").text(strip=True)
        checksum = doc_checksum(title + clean_entries(tree))
        doc_id = build_regulation_doc_id(self.source, "2025/58", "bulten")
        return CanonDoc(
            doc_id=doc_id,
            source=self.source,
            doc_type="bulten",
            title=title,
            url=raw.ref.url,
            checksum=checksum,
            meta={"bulten_no": "2025/58"},
            raw=raw,
        )

    def chunk(self, doc: CanonDoc):
        tree = HTMLParser(doc.raw.content_html if doc.raw else "")
        items = []
        for entry in tree.css(".entry"):
            text = entry.css_first(".text").text(strip=True)
            item_id = entry.css_first(".id").text(strip=True)
            date_txt = entry.css_first(".date").text(strip=True)
            items.append(f"{item_id} - {date_txt}: {text}")
        return chunk_bullet_items(doc, items)


def clean_entries(tree: HTMLParser) -> str:
    entries = []
    for entry in tree.css(".entry"):
        text = entry.text(separator=" ", strip=True)
        entries.append(text)
    return "\n".join(entries)
