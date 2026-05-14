"""Reconcile lb-api per-period profit numbers against locally-computable
cash flow from trades + redemption activity.

The point isn't perfect realized-PnL accounting (that needs FIFO position matching).
It's a sanity check: do lb-api's headline numbers move in the same direction and
order of magnitude as the trader's actual USDC inflows/outflows over the same
window? If yes, leaderboard signals are trustworthy enough to drive Sprint 02
choice; if not, our archetype claims need a rebuild.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

import httpx
import polars as pl

from . import data_api, http, leaderboard, profile

log = logging.getLogger(__name__)

PERIOD_SECONDS = {
    "day": 86_400,
    "week": 7 * 86_400,
    "month": 30 * 86_400,
    "year": 365 * 86_400,
}
PERIODS_WITH_BOUNDS: tuple[leaderboard.Period, ...] = ("day", "week", "month", "year")
ALL_PERIODS: tuple[leaderboard.Period, ...] = PERIODS_WITH_BOUNDS + ("all",)


async def _fetch_trades(client: httpx.AsyncClient, address: str, max_pages: int) -> list[dict]:
    async def page(offset: int) -> list[dict]:
        return await data_api.trades(
            client, user=address, taker_only=False, limit=500, offset=offset
        )

    return await profile._paginate(page, max_pages=max_pages, label=f"{address[:10]} trades")


async def _fetch_redemptions(
    client: httpx.AsyncClient, address: str, max_pages: int
) -> list[dict]:
    async def page(offset: int) -> list[dict]:
        return await data_api.activity(
            client, address, types=["REDEEM"], limit=500, offset=offset
        )

    return await profile._paginate(page, max_pages=max_pages, label=f"{address[:10]} redeems")


async def _fetch_lb_metrics(
    client: httpx.AsyncClient, address: str
) -> dict[tuple[str, str], float | None]:
    out: dict[tuple[str, str], float | None] = {}
    for metric in ("profit", "volume"):
        for period in ALL_PERIODS:
            row = await leaderboard.address_metric(client, metric, period, address)
            out[(metric, period)] = float(row["amount"]) if row else None
    return out


def _cashflow_in_window(
    trades: list[dict],
    redemptions: list[dict],
    *,
    period_seconds: int,
    now_ts: int,
) -> dict[str, float]:
    start = now_ts - period_seconds
    buys = sells = redeems = 0.0
    n_buy = n_sell = n_redeem = 0
    for t in trades:
        ts = int(t["timestamp"])
        if not (start <= ts <= now_ts):
            continue
        usd = float(t["size"]) * float(t["price"])
        if t.get("side") == "BUY":
            buys += usd
            n_buy += 1
        elif t.get("side") == "SELL":
            sells += usd
            n_sell += 1
    for a in redemptions:
        ts = int(a["timestamp"])
        if not (start <= ts <= now_ts):
            continue
        redeems += float(a.get("usdcSize") or 0)
        n_redeem += 1
    return {
        "buys_usd": buys,
        "sells_usd": sells,
        "redeems_usd": redeems,
        "net_cashflow_usd": sells + redeems - buys,
        "trade_volume_usd": buys + sells,  # comparable to lb-api "volume"
        "n_buy": n_buy,
        "n_sell": n_sell,
        "n_redeem": n_redeem,
    }


def _load_cached_trades(address: str, traders_dir: Path) -> list[dict] | None:
    p = traders_dir / address / "trades.parquet"
    if not p.exists():
        return None
    df = pl.read_parquet(p)
    return df.to_dicts()


async def validate_address(
    client: httpx.AsyncClient,
    address: str,
    *,
    cached_trades: list[dict] | None = None,
    max_pages: int = 7,
) -> list[dict]:
    addr = address.lower()
    trades = cached_trades if cached_trades is not None else await _fetch_trades(
        client, addr, max_pages
    )
    redemptions = await _fetch_redemptions(client, addr, max_pages)
    lb = await _fetch_lb_metrics(client, addr)

    now_ts = int(time.time())
    out: list[dict] = []
    for period in ALL_PERIODS:
        row: dict = {
            "address": addr,
            "period": period,
            "lb_profit_usd": lb.get(("profit", period)),
            "lb_volume_usd": lb.get(("volume", period)),
        }
        if period in PERIOD_SECONDS:
            cf = _cashflow_in_window(
                trades, redemptions,
                period_seconds=PERIOD_SECONDS[period], now_ts=now_ts,
            )
            row.update(cf)
            # Diagnostic: ratio of computed cashflow to lb_profit. Closer to 1.0 means
            # lb-api reports something close to "net USDC moved this period".
            lp = row["lb_profit_usd"]
            if lp and abs(lp) > 1.0:
                row["pnl_ratio_computed_to_lb"] = round(cf["net_cashflow_usd"] / lp, 3)
            lv = row["lb_volume_usd"]
            if lv and lv > 1.0:
                row["volume_ratio_computed_to_lb"] = round(cf["trade_volume_usd"] / lv, 4)
        out.append(row)
    log.info(
        "validated %s: %d trades (cached=%s), %d redemptions",
        addr, len(trades), cached_trades is not None, len(redemptions),
    )
    return out


async def validate_addresses(
    addresses: list[str],
    *,
    traders_dir: Path | None = None,
    max_pages: int = 7,
) -> list[dict]:
    rows: list[dict] = []
    async with http.session() as client:
        for addr in addresses:
            cached = _load_cached_trades(addr, traders_dir) if traders_dir else None
            try:
                rows.extend(
                    await validate_address(
                        client, addr, cached_trades=cached, max_pages=max_pages
                    )
                )
            except Exception as exc:
                log.error("validation failed for %s: %s", addr, exc)
    return rows
