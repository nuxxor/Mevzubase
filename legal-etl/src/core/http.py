from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx
from tenacity import RetryError, retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

DEFAULT_UA = (
    "legal-etl/0.1 (+https://example.local; contact: data@legal-etl.local) "
    "python-httpx"
)


class RateLimiter:
    """Token bucket limiter for polite crawling."""

    def __init__(self, rate: float = 1.0, capacity: int = 2):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.updated_at = time.monotonic()

    def acquire(self) -> None:
        now = time.monotonic()
        elapsed = now - self.updated_at
        self.updated_at = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        if self.tokens < 1:
            sleep_for = (1 - self.tokens) / self.rate
            time.sleep(sleep_for)
            self.tokens = 0
        self.tokens -= 1


class HttpError(Exception):
    pass


@dataclass
class HttpResponse:
    status_code: int
    text: str | None
    content: bytes | None
    headers: dict[str, str]

    def to_httpx_response(self) -> httpx.Response:
        return httpx.Response(
            status_code=self.status_code,
            content=self.content or b"",
            headers=self.headers,
            request=httpx.Request("GET", "https://example.local"),
        )


class HttpClient:
    def __init__(
        self,
        user_agent: str = DEFAULT_UA,
        rate_limiter: RateLimiter | None = None,
        timeout: float = 15.0,
        session_factory: Callable[..., httpx.Client] = httpx.Client,
    ) -> None:
        self.rate_limiter = rate_limiter or RateLimiter()
        self.session = session_factory(timeout=timeout, headers={"User-Agent": user_agent})

    def _retryable(self, exc: Exception) -> bool:
        if isinstance(exc, HttpError):
            return True
        return False

    def _should_retry_status(self, status: int) -> bool:
        return status in {429, 500, 502, 503, 504}

    def _request(self, method: str, url: str, **kwargs: Any) -> HttpResponse:
        self.rate_limiter.acquire()
        try:
            resp = self.session.request(method, url, **kwargs)
        except Exception as exc:  # pragma: no cover - network errors
            raise HttpError(str(exc)) from exc

        if self._should_retry_status(resp.status_code):
            raise HttpError(f"retryable status {resp.status_code}")
        return HttpResponse(
            status_code=resp.status_code,
            text=resp.text,
            content=resp.content,
            headers=dict(resp.headers),
        )

    def close(self) -> None:
        self.session.close()

    @retry(
        retry=retry_if_exception_type(HttpError),
        wait=wait_exponential_jitter(initial=1, max=8),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def get(
        self,
        url: str,
        etag: str | None = None,
        last_modified: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        hdrs = headers.copy() if headers else {}
        if etag:
            hdrs["If-None-Match"] = etag
        if last_modified:
            hdrs["If-Modified-Since"] = last_modified
        return self._request("GET", url, headers=hdrs)


def fetch_text(
    client: HttpClient, url: str, etag: str | None = None, last_modified: str | None = None
) -> tuple[str | None, dict[str, str]]:
    resp = client.get(url, etag=etag, last_modified=last_modified)
    if resp.status_code == 304:
        return None, resp.headers
    return resp.text, resp.headers
