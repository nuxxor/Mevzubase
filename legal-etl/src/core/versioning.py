from __future__ import annotations

import hashlib
from typing import Iterable

from .schema import CanonDoc, Chunk


def doc_checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_hash(content: str) -> str:
    return hashlib.sha1(content.encode("utf-8")).hexdigest()


def compute_chunk_hashes(chunks: Iterable[Chunk]) -> list[Chunk]:
    out: list[Chunk] = []
    for chunk in chunks:
        if not chunk.content_hash:
            chunk.content_hash = chunk_hash(chunk.content)
        out.append(chunk)
    return out


def needs_new_version(existing_checksum: str | None, new_checksum: str) -> bool:
    if existing_checksum is None:
        return True
    return existing_checksum != new_checksum


def bump_version(doc: CanonDoc) -> CanonDoc:
    doc.version += 1
    doc.is_current = True
    return doc
