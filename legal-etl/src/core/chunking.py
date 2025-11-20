from __future__ import annotations

from typing import Iterable

from .schema import CanonDoc, Chunk
from .text import split_paragraphs
from .utils import approx_tokens, hash_for_content

TARGET_REGULATION_TOKENS = 700
TARGET_DECISION_TOKENS = 500


def make_chunk(content: str, doc: CanonDoc, article_no: str | None, paragraph_no: str | None) -> Chunk:
    content = content.strip()
    return Chunk(
        chunk_id="",
        doc_id=doc.doc_id,
        version=doc.version,
        content=content,
        content_hash=hash_for_content(content),
        token_count=approx_tokens(content),
        article_no=article_no,
        paragraph_no=paragraph_no,
        payload={
            "doc_id": doc.doc_id,
            "version": doc.version,
            "source": doc.source,
            "doc_type": doc.doc_type,
            "url": str(doc.url),
            "rg_no": doc.rg_no,
            "rg_date": doc.rg_date.isoformat() if doc.rg_date else None,
            "court": doc.court,
            "chamber": doc.chamber,
            "decision_date": doc.decision_date.isoformat() if doc.decision_date else None,
            "is_current": doc.is_current,
            **doc.meta,
        },
    )


def chunk_regulation(doc: CanonDoc, articles: dict[str, str]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for article_no, body in articles.items():
        if approx_tokens(body) <= TARGET_REGULATION_TOKENS:
            chunks.append(make_chunk(body, doc, article_no, None))
            continue
        paras = split_paragraphs(body)
        for idx, para in enumerate(paras):
            chunks.append(make_chunk(para, doc, article_no, f"{idx+1}"))
    return chunks


def chunk_decision(doc: CanonDoc, summary: str, reasoning: Iterable[str]) -> list[Chunk]:
    chunks: list[Chunk] = []
    if summary.strip():
        chunks.append(make_chunk(summary.strip(), doc, None, "summary"))
    for idx, para in enumerate(reasoning):
        para = para.strip()
        if not para:
            continue
        chunks.append(make_chunk(para, doc, None, f"§{idx+1}"))
    return chunks


def chunk_bullet_items(doc: CanonDoc, items: Iterable[str]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for idx, item in enumerate(items):
        if not item.strip():
            continue
        chunks.append(make_chunk(item.strip(), doc, None, f"item-{idx+1}"))
    return chunks
