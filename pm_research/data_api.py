"""Read-only wrappers for data-api.polymarket.com.

Sprint 01 uses these for per-trader deep dives once a candidate pool exists.
"""

from __future__ import annotations

from typing import Literal, Sequence

import httpx

from .http import get_json

DATA_API = "https://data-api.polymarket.com"

ActivityType = Literal["TRADE", "SPLIT", "MERGE", "REDEEM", "REWARD", "CONVERSION"]


async def trades(
    client: httpx.AsyncClient,
    *,
    user: str | None = None,
    market: str | None = None,
    side: Literal["BUY", "SELL"] | None = None,
    taker_only: bool = True,
    limit: int = 500,
    offset: int = 0,
) -> list[dict]:
    p: dict = {"limit": limit, "offset": offset, "takerOnly": str(taker_only).lower()}
    if user:
        p["user"] = user
    if market:
        p["market"] = market
    if side:
        p["side"] = side
    return await get_json(client, f"{DATA_API}/trades", params=p)


async def positions(
    client: httpx.AsyncClient,
    user: str,
    *,
    limit: int = 500,
    offset: int = 0,
    size_threshold: float = 1.0,
    sort_by: str = "CURRENT",
    sort_dir: Literal["ASC", "DESC"] = "DESC",
) -> list[dict]:
    return await get_json(
        client,
        f"{DATA_API}/positions",
        params={
            "user": user,
            "limit": limit,
            "offset": offset,
            "sizeThreshold": size_threshold,
            "sortBy": sort_by,
            "sortDirection": sort_dir,
        },
    )


async def closed_positions(
    client: httpx.AsyncClient, user: str, *, limit: int = 500, offset: int = 0
) -> list[dict]:
    return await get_json(
        client,
        f"{DATA_API}/closed-positions",
        params={"user": user, "limit": limit, "offset": offset},
    )


async def activity(
    client: httpx.AsyncClient,
    user: str,
    *,
    types: Sequence[ActivityType] | None = None,
    start: int | None = None,
    end: int | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[dict]:
    p: dict = {"user": user, "limit": limit, "offset": offset}
    if types:
        p["type"] = ",".join(types)
    if start is not None:
        p["start"] = start
    if end is not None:
        p["end"] = end
    return await get_json(client, f"{DATA_API}/activity", params=p)


async def value(client: httpx.AsyncClient, user: str) -> float:
    rows = await get_json(client, f"{DATA_API}/value", params={"user": user})
    return float(rows[0]["value"]) if rows else 0.0
