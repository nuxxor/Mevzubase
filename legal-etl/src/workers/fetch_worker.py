from __future__ import annotations

import os
from datetime import date

import redis
import rq
import structlog

from src.connectors.spk import SPKConnector
from src.connectors.yargitay import YargitayConnector
from src.core.schema import ItemRef
from src.core.utils import configure_logging

logger = structlog.get_logger()


def get_queue(name: str) -> rq.Queue:
    conn = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    return rq.Queue(name, connection=conn)


def enqueue_new_items(since: date | None = None) -> None:
    since = since or date.today()
    connectors = [YargitayConnector(), SPKConnector()]
    parse_queue = get_queue("parse")
    for conn in connectors:
        for ref in conn.list_items(since):
            parse_queue.enqueue(process_fetch, conn.source, ref.model_dump())
            logger.info("fetch.enqueued", source=conn.source, ref=ref.key)


def process_fetch(source: str, ref_data: dict) -> dict:
    configure_logging()
    conn_map = {"YARGITAY": YargitayConnector(), "SPK": SPKConnector()}
    connector = conn_map[source]
    ref = ItemRef.model_validate(ref_data)
    raw = connector.fetch(ref)
    return raw.model_dump()
