"""Async HTTP layer with per-host rate limiting and retry/backoff.

Rate limits derived from Polymarket's documented Cloudflare buckets, deliberately
held to ~50% of allowed throughput. See docs/sprints/sprint-01-trader-discovery/data-sources.md.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit

import httpx
from aiolimiter import AsyncLimiter
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

HOST_LIMITS: dict[str, tuple[float, float]] = {
    "data-api.polymarket.com": (10, 1),
    "lb-api.polymarket.com": (3, 1),
    "gamma-api.polymarket.com": (20, 1),
    "clob.polymarket.com": (75, 1),
}
_DEFAULT_LIMIT: tuple[float, float] = (5.0, 1.0)
_limiters: dict[str, AsyncLimiter] = {}


def _limiter(host: str) -> AsyncLimiter:
    if host not in _limiters:
        rate, per = HOST_LIMITS.get(host, _DEFAULT_LIMIT)
        _limiters[host] = AsyncLimiter(rate, per)
    return _limiters[host]


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        sc = exc.response.status_code
        return sc == 429 or sc >= 500
    return False


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_exception(_retryable),
    reraise=True,
)
async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float = 20.0,
) -> Any:
    host = urlsplit(url).netloc
    async with _limiter(host):
        log.debug("GET %s params=%s", url, params)
        r = await client.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()


@asynccontextmanager
async def session(timeout: float = 20.0):
    async with httpx.AsyncClient(timeout=timeout) as c:
        yield c
