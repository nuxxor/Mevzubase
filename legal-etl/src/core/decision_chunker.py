from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from src.core.chunking import make_chunk
from src.core.cleaners import strip_noise_lines
from src.core.legal import build_aliases
from src.core.schema import CanonDoc, Chunk
from src.core.utils import approx_tokens

SECTION_ALIASES: dict[str, str] = {
    "ÖZET": "ÖZET",
    "KÜNYE": "KÜNYE",
    "GEREĞİ DÜŞÜNÜLDÜ": "GEREĞİ DÜŞÜNÜLDÜ",
    "GEREKÇE": "GEREKÇE",
    "SONUÇ": "HÜKÜM/SONUÇ",
    "HÜKÜM": "HÜKÜM/SONUÇ",
    "HÜKÜM/SONUÇ": "HÜKÜM/SONUÇ",
    "DELİLLERİN DEĞERLENDİRİLMESİ": "GEREKÇE",
    "TALEP": "TALEP",
    "SAVUNMA": "SAVUNMA",
}

SECTION_PATTERN = re.compile(
    r"^(?P<header>(ÖZETİ?|KÜNYE|GEREĞİ DÜŞÜNÜLDÜ|GEREKÇE|SONUÇ|HÜKÜM|DELİLLERİN DEĞERLENDİRİLMESİ|TALEP|SAVUNMA))[:\-–]?$",
    re.IGNORECASE,
)

SOFT_TOKEN_TARGET = 600
HARD_TOKEN_LIMIT = 850
OVERLAP_TOKENS = 50


@dataclass
class Section:
    title: str
    paragraphs: list[str]


def build_anchor(doc: CanonDoc) -> str:
    court = doc.court or doc.source
    chamber = doc.chamber or doc.meta.get("chamber") or "BİLİNMİYOR"
    e_no = doc.meta.get("e_no") or ""
    k_no = doc.meta.get("k_no") or ""
    b_no = doc.meta.get("b_no") or ""
    date_txt = (
        doc.decision_date.isoformat()
        if doc.decision_date
        else doc.meta.get("decision_date_text")
        or "unknown"
    )
    parts = [f"KAYNAK:{court}", f"DAİRE:{chamber}", f"E:{e_no}", f"K:{k_no}", f"B:{b_no}", f"T:{date_txt}"]
    return "[" + "|".join(part for part in parts if part.split(":", 1)[1]) + "]"


def normalize_text(text: str | None) -> str:
    return strip_noise_lines(text, extra_patterns=[r"windowHeight", r"pixel"])


def split_sections(text: str) -> list[Section]:
    sections: list[Section] = []
    current = Section(title="METİN", paragraphs=[])
    for para in _iter_paragraphs(text):
        match = SECTION_PATTERN.match(para.upper())
        if match:
            if current.paragraphs:
                sections.append(current)
            normalized = SECTION_ALIASES.get(match.group("header").upper(), match.group("header").upper())
            current = Section(title=normalized, paragraphs=[])
            continue
        current.paragraphs.append(para)
    if current.paragraphs:
        sections.append(current)
    if not sections:
        sections.append(Section(title="METİN", paragraphs=[text]))
    return sections


def chunk_sections(doc: CanonDoc, sections: Sequence[Section]) -> list[Chunk]:
    anchor = build_anchor(doc)
    doc.meta.setdefault("anchor", anchor)
    doc.meta.setdefault("aliases", build_aliases(doc.meta.get("e_no"), doc.meta.get("k_no"), doc.chamber))
    chunks: list[Chunk] = []
    for section in sections:
        buffer: list[str] = []
        token_total = 0
        chunk_index = 1
        for para in section.paragraphs:
            tokens = approx_tokens(para)
            if token_total and token_total + tokens > HARD_TOKEN_LIMIT:
                chunks.append(_emit_chunk(doc, anchor, section.title, buffer, chunk_index))
                chunk_index += 1
                buffer = _tail_lines(buffer, OVERLAP_TOKENS)
                token_total = sum(approx_tokens(l) for l in buffer)
            buffer.append(para)
            token_total += tokens
            if token_total >= SOFT_TOKEN_TARGET:
                chunks.append(_emit_chunk(doc, anchor, section.title, buffer, chunk_index))
                chunk_index += 1
                buffer = _tail_lines(buffer, OVERLAP_TOKENS)
                token_total = sum(approx_tokens(l) for l in buffer)
        if buffer:
            chunks.append(_emit_chunk(doc, anchor, section.title, buffer, chunk_index))
    return chunks


def _emit_chunk(doc: CanonDoc, anchor: str, section_title: str, lines: list[str], idx: int) -> Chunk:
    body = "\n".join(lines).strip()
    if not body:
        return make_chunk(anchor, doc, None, section_title)
    chunk_text = "\n".join([anchor, f"[{section_title}]", body]).strip()
    return make_chunk(chunk_text, doc, None, f"{section_title}:{idx}")


def _tail_lines(lines: list[str], budget_tokens: int) -> list[str]:
    """Son kısımdan budget_tokens kadarını bırakır (overlap için)."""
    if not lines or budget_tokens <= 0:
        return []
    tail: list[str] = []
    used = 0
    for line in reversed(lines):
        t = approx_tokens(line)
        if used + t > budget_tokens and tail:
            break
        tail.append(line)
        used += t
        if used >= budget_tokens:
            break
    return list(reversed(tail))


def _iter_paragraphs(text: str) -> Iterable[str]:
    paragraph = []
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            if paragraph:
                yield " ".join(paragraph).strip()
                paragraph = []
            continue
        paragraph.append(cleaned)
    if paragraph:
        yield " ".join(paragraph).strip()
