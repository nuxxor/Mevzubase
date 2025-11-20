from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Iterable

from pydantic import AnyHttpUrl, BaseModel, Field


def _strip(value: str | None) -> str | None:
    return value.strip() if value else value


class ItemRef(BaseModel):
    """Lightweight reference emitted by list_items."""

    key: str
    url: AnyHttpUrl
    etag: str | None = None
    last_modified: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RawDoc(BaseModel):
    """Fetched raw payloads from the source."""

    ref: ItemRef
    content_html: str | None = None
    content_pdf: bytes | None = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CanonDoc(BaseModel):
    """Canonical normalized document."""

    doc_id: str
    source: str
    doc_type: str
    title: str
    url: AnyHttpUrl
    checksum: str
    version: int = 1
    is_current: bool = True
    decision_date: date | None = None
    rg_no: str | None = None
    rg_date: date | None = None
    chamber: str | None = None
    court: str | None = None
    text: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    raw: RawDoc | None = None


class Chunk(BaseModel):
    """Chunk representation that feeds Qdrant/OpenSearch."""

    chunk_id: str
    doc_id: str
    version: int
    content: str
    content_hash: str
    token_count: int
    article_no: str | None = None
    paragraph_no: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


def build_decision_doc_id(
    source: str, chamber: str, e_no: str, k_no: str, decision_date: date | str | None
) -> str:
    date_part: str
    if isinstance(decision_date, date):
        date_part = decision_date.isoformat()
    else:
        raw_date = str(decision_date) if decision_date is not None else ""
        date_part = raw_date.strip() or "unknown"

    return ":".join(
        [
            source.lower(),
            _strip(chamber) or "unknown",
            f"{_strip(e_no) or 'e0'}-{_strip(k_no) or 'k0'}",
            date_part,
        ]
    )


def build_regulation_doc_id(source: str, rg_no: str, item_no: str) -> str:
    return ":".join([source.lower(), rg_no, item_no])


def ensure_chunk_ids(doc_id: str, version: int, chunks: Iterable[Chunk]) -> list[Chunk]:
    out: list[Chunk] = []
    for idx, chunk in enumerate(chunks):
        chunk.chunk_id = chunk.chunk_id or f"{doc_id}:v{version}:c{idx}"
        out.append(chunk)
    return out
