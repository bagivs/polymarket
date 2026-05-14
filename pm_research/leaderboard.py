"""Wrappers for the (undocumented but public) Polymarket leaderboard service.

Endpoint shape: GET https://lb-api.polymarket.com/{profit|volume}
    ?period=day|week|month|year|all
    &limit=N            # top-N
    &address=0x...      # OR a single address lookup
"""

from __future__ import annotations

from typing import Literal

import httpx

from .http import get_json

LB_API = "https://lb-api.polymarket.com"

Period = Literal["day", "week", "month", "year", "all"]
Metric = Literal["profit", "volume"]


async def top(
    client: httpx.AsyncClient,
    metric: Metric,
    period: Period,
    *,
    limit: int = 200,
) -> list[dict]:
    return await get_json(
        client,
        f"{LB_API}/{metric}",
        params={"period": period, "limit": limit},
    )


async def address_metric(
    client: httpx.AsyncClient,
    metric: Metric,
    period: Period,
    address: str,
) -> dict | None:
    rows = await get_json(
        client,
        f"{LB_API}/{metric}",
        params={"period": period, "address": address},
    )
    return rows[0] if rows else None
