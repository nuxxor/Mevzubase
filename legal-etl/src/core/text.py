from __future__ import annotations

import io
import re
from typing import Iterable

import fitz  # type: ignore
from pdfminer.high_level import extract_text as pdfminer_extract
from selectolax.parser import HTMLParser

ARTICLE_RE = re.compile(r"MADDE\s+\d+(?:/[0-9A-Z]+)?", re.IGNORECASE)
E_NO_RE = re.compile(r"E\.\s*\d{4}/\d+")
K_NO_RE = re.compile(r"K\.\s*\d{4}/\d+")
T_NO_RE = re.compile(r"T\.\s*\d{2}\.\d{2}\.\d{4}")


def clean_text(html: str) -> str:
    tree = HTMLParser(html)
    for node in tree.css("script,style,noscript"):
        node.decompose()
    text = tree.text(separator="\n")
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def extract_pdf_text(data: bytes) -> str:
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        pages = [page.get_text("text") for page in doc]
        return "\n".join(pages)
    except Exception:
        return pdfminer_extract(io.BytesIO(data))


def split_paragraphs(text: str) -> list[str]:
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    return paras


def find_matches(pattern: re.Pattern[str], text: str) -> list[str]:
    return pattern.findall(text)


def detect_meta(text: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    e = E_NO_RE.search(text)
    k = K_NO_RE.search(text)
    t = T_NO_RE.search(text)
    if e:
        meta["e_no"] = e.group().replace(" ", "")
    if k:
        meta["k_no"] = k.group().replace(" ", "")
    if t:
        meta["decision_date"] = t.group().replace("T.", "").strip()
    return meta


def normalize_whitespace(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def first_lines(text: str, count: int = 1) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines[:count])
