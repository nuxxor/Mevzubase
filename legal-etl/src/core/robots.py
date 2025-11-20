from __future__ import annotations

import functools
import time
from dataclasses import dataclass
from typing import Dict
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

USER_AGENT = "legal-etl"


@dataclass
class RobotsResult:
    allowed: bool
    crawl_delay: float | None


class RobotsCache:
    def __init__(self, ttl_seconds: int = 3600) -> None:
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, tuple[float, RobotFileParser]] = {}

    def get(self, domain: str) -> RobotFileParser | None:
        entry = self._cache.get(domain)
        if not entry:
            return None
        ts, parser = entry
        if time.time() - ts > self.ttl_seconds:
            self._cache.pop(domain, None)
            return None
        return parser

    def set(self, domain: str, parser: RobotFileParser) -> None:
        self._cache[domain] = (time.time(), parser)


cache = RobotsCache()


def fetch_robots(url: str) -> RobotFileParser:
    parsed = urlparse(url)
    domain = parsed.scheme + "://" + parsed.netloc
    cached = cache.get(domain)
    if cached:
        return cached

    rp = RobotFileParser()
    rp.set_url(f"{domain}/robots.txt")
    try:
        rp.read()
    except Exception:  # pragma: no cover
        rp.modified()
    cache.set(domain, rp)
    return rp


def is_allowed(url: str, user_agent: str = USER_AGENT) -> RobotsResult:
    rp = fetch_robots(url)
    allowed = rp.can_fetch(user_agent, url)
    delay = rp.crawl_delay(user_agent)
    return RobotsResult(allowed=allowed, crawl_delay=delay)


def polite_sleep(delay: float | None) -> None:
    if delay:
        time.sleep(delay)
