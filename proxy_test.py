#!/usr/bin/env python3
"""
Quick proxy tester for HTTP/HTTPS endpoints.

Usage:
  python proxy_test.py
"""

from __future__ import annotations

import itertools
import random
from typing import Iterable

import httpx

# Provided proxies in host:port:user:pass format
RAW_PROXIES = [
    "isp2.livaproxy.com:30085:taygundogan:poineer107",
    "isp2.livaproxy.com:31116:taygundogan:poineer107",
    "isp2.livaproxy.com:31235:taygundogan:poineer107",
    "isp2.livaproxy.com:31144:taygundogan:poineer107",
    "isp2.livaproxy.com:30111:taygundogan:poineer107",
]

TEST_URL = "https://httpbin.org/ip"
TIMEOUT = 10.0


def to_proxy_url(raw: str) -> str:
    host, port, user, pwd = raw.split(":")
    return f"http://{user}:{pwd}@{host}:{port}"


def cycle_proxies(raw_list: Iterable[str]) -> Iterable[str]:
    for raw in raw_list:
        yield to_proxy_url(raw)


def test_proxy(proxy_url: str) -> None:
    print(f"\n=== Testing {proxy_url} ===")
    try:
        with httpx.Client(
            proxies=proxy_url,
            timeout=TIMEOUT,
            http2=False,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Connection": "keep-alive",
            },
        ) as client:
            resp = client.get(TEST_URL)
            resp.raise_for_status()
            print(resp.text.strip())
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}")


def main() -> None:
    proxies = list(cycle_proxies(RAW_PROXIES))
    random.shuffle(proxies)
    for proxy_url in proxies:
        test_proxy(proxy_url)


if __name__ == "__main__":
    main()
