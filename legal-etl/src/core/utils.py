from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Iterable, Iterator, Sequence, TypeVar

import structlog

T = TypeVar("T")


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def approx_tokens(text: str) -> int:
    return max(1, len(text.split()))


def hash_for_content(text: str, algo: str = "sha1") -> str:
    h = hashlib.new(algo)
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def chunked(seq: Sequence[T] | Iterable[T], size: int) -> Iterator[list[T]]:
    bucket: list[T] = []
    for item in seq:
        bucket.append(item)
        if len(bucket) >= size:
            yield bucket
            bucket = []
    if bucket:
        yield bucket


def configure_logging() -> None:
    structlog.configure(processors=[structlog.processors.JSONRenderer()])


def env(key: str, default: str | None = None) -> str:
    val = os.environ.get(key, default)
    if val is None:
        raise RuntimeError(f"Missing environment variable {key}")
    return val
