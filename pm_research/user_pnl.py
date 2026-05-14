"""user-pnl-api.polymarket.com — true period-windowed PnL timeseries.

This is a separate service from lb-api. While lb-api's `period` parameter is
ignored (always returns lifetime), this endpoint actually filters by interval
and returns a chronological PnL curve.

Discovered 2026-05-14 by inspecting bonereaper's profile network calls.
Frontend's "1d/1w/1m/all" tabs read from here.

GET https://user-pnl-api.polymarket.com/user-pnl
    ?user_address=0x...      # snake_case, mandatory
    &interval=1d|1w|1m|all|max
    &fidelity=1d|1h          # bucket size; 1m + 1d ≈ 30 rows; 1m + 1h ≈ 720 rows

Returns: [{"t": <unix>, "p": <cumulative_pnl_usd>}, ...]
"""

from __future__ import annotations

from typing import Literal

import httpx

from .http import get_json

USER_PNL_API = "https://user-pnl-api.polymarket.com"

Interval = Literal["1d", "1w", "1m", "all", "max"]
Fidelity = Literal["1d", "1h"]


async def pnl_series(
    client: httpx.AsyncClient,
    address: str,
    *,
    interval: Interval = "1m",
    fidelity: Fidelity = "1d",
) -> list[dict]:
    return await get_json(
        client,
        f"{USER_PNL_API}/user-pnl",
        params={
            "user_address": address.lower(),
            "interval": interval,
            "fidelity": fidelity,
        },
    )


async def period_delta(
    client: httpx.AsyncClient,
    address: str,
    *,
    interval: Interval = "1m",
    fidelity: Fidelity = "1d",
) -> float:
    """Net PnL change over the requested interval window."""
    series = await pnl_series(client, address, interval=interval, fidelity=fidelity)
    if not series:
        return 0.0
    return float(series[-1]["p"]) - float(series[0]["p"])


async def multi_interval_deltas(
    client: httpx.AsyncClient,
    address: str,
    intervals: tuple[Interval, ...] = ("1d", "1w", "1m"),
) -> dict[str, float]:
    """Convenience: deltas for several intervals, one call each."""
    out: dict[str, float] = {}
    for iv in intervals:
        out[iv] = await period_delta(client, address, interval=iv)
    return out
