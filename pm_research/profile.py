"""Per-trader bulk fetch: trades, open + closed positions, current value.

Trades and closed-positions are paginated; positions and value are single calls.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

import httpx

from . import data_api, http

log = logging.getLogger(__name__)

PAGE_LIMIT = 500
# data-api /trades hard-caps at offset 3000 (probed 2026-05-14); 7 pages = ~3500 most
# recent trades, which is enough sample for archetype fingerprinting on any trader.
DEFAULT_MAX_PAGES = 7


async def _paginate(
    fetch_page: Callable[[int], Awaitable[list[dict]]],
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
    label: str = "",
) -> list[dict]:
    out: list[dict] = []
    for page in range(max_pages):
        offset = page * PAGE_LIMIT
        try:
            rows = await fetch_page(offset)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 400 and offset > 0:
                # Hidden server-side max-offset; treat as end-of-data.
                log.info("%s: stop at offset=%d (server 400, returning %d rows)",
                         label or "paginate", offset, len(out))
                break
            raise
        if not rows:
            break
        out.extend(rows)
        if len(rows) < PAGE_LIMIT:
            break
    return out


async def collect_trader(
    client: httpx.AsyncClient,
    address: str,
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> dict[str, Any]:
    addr = address.lower()

    async def _trades(offset: int) -> list[dict]:
        return await data_api.trades(
            client, user=addr, taker_only=False, limit=PAGE_LIMIT, offset=offset
        )

    async def _closed(offset: int) -> list[dict]:
        return await data_api.closed_positions(
            client, addr, limit=PAGE_LIMIT, offset=offset
        )

    trades, closed, open_positions, value = await asyncio.gather(
        _paginate(_trades, max_pages=max_pages, label=f"{addr[:10]} trades"),
        _paginate(_closed, max_pages=max_pages, label=f"{addr[:10]} closed"),
        data_api.positions(client, addr, limit=PAGE_LIMIT),
        data_api.value(client, addr),
    )

    log.info(
        "%s: trades=%d closed=%d open=%d value=$%s",
        addr,
        len(trades),
        len(closed),
        len(open_positions),
        f"{value:,.0f}",
    )
    return {
        "address": addr,
        "trades": trades,
        "closed_positions": closed,
        "open_positions": open_positions,
        "current_value": value,
    }


async def collect_cohort(
    addresses: list[str], *, max_pages: int = DEFAULT_MAX_PAGES
) -> list[dict[str, Any]]:
    """Run collect_trader sequentially across addresses (per-host limiter handles bursts)."""
    results: list[dict[str, Any]] = []
    async with http.session() as client:
        for addr in addresses:
            try:
                results.append(await collect_trader(client, addr, max_pages=max_pages))
            except Exception as exc:
                log.error("collect failed for %s: %s", addr, exc)
    return results
