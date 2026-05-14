"""Wrapper for clob.polymarket.com/prices-history.

Returns a price timeseries for a token id. Used to reconstruct what the
market believed at any point in time.
"""

from __future__ import annotations

from typing import Literal

import httpx

from .http import get_json

CLOB = "https://clob.polymarket.com"
Interval = Literal["1m", "1w", "max"]


async def prices_history(
    client: httpx.AsyncClient,
    token_id: str,
    *,
    interval: Interval = "max",
    fidelity_min: int = 60,
) -> list[dict]:
    """[{t: <unix>, p: <price>}] for the requested interval/granularity."""
    resp = await get_json(
        client,
        f"{CLOB}/prices-history",
        params={"market": token_id, "interval": interval, "fidelity": fidelity_min},
    )
    if isinstance(resp, dict) and "history" in resp:
        return resp["history"]
    return resp if isinstance(resp, list) else []


def price_at_or_before(history: list[dict], ts: int) -> float | None:
    """Last price observation at or before ts; None if no observation in range."""
    last: float | None = None
    for row in history:
        if int(row["t"]) <= ts:
            last = float(row["p"])
        else:
            break
    return last


def price_at_or_after(history: list[dict], ts: int) -> float | None:
    """First price observation at or after ts; None if no observation in range."""
    for row in history:
        if int(row["t"]) >= ts:
            return float(row["p"])
    return None
