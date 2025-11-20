from __future__ import annotations

import os

import redis
import rq
import structlog

from src.connectors.spk import SPKConnector
from src.connectors.yargitay import YargitayConnector
from src.core.schema import CanonDoc, ItemRef, RawDoc

logger = structlog.get_logger()


def get_queue(name: str) -> rq.Queue:
    conn = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    return rq.Queue(name, connection=conn)


def process_raw(source: str, raw_data: dict) -> dict:
    connector = {"YARGITAY": YargitayConnector(), "SPK": SPKConnector()}[source]
    raw = RawDoc.model_validate(raw_data)
    doc = connector.parse(raw)
    chunks = connector.chunk(doc)
    get_queue("diff").enqueue(process_normalized, doc.model_dump(), [c.model_dump() for c in chunks])
    logger.info("parse.done", doc_id=doc.doc_id, chunks=len(chunks))
    return doc.model_dump()


def process_normalized(doc_data: dict, chunks_data: list[dict]) -> dict:
    doc = CanonDoc.model_validate(doc_data)
    return {"doc": doc.model_dump(), "chunks": chunks_data}
