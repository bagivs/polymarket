"""Backtest the 'BUY favorite at entry, hold to resolution' strategy.

For each closed market we know the final outcome and can pull a historical
price timeseries for the YES token. We pick an entry timestamp (a configurable
offset before market close), find the YES price at that point, decide which
side is the FAVORITE, and simulate buying it.

Payoff per dollar invested:
  payoff = 1 / entry_price if favorite_won else 0
  net   = payoff - 1                                  # raw return per $1 stake
  net_after_fees_slippage = (1 - fee) * payoff * (1 - slippage_in) - 1

This is a lower bound: we model entry slippage but assume zero exit cost
(redemption is gas-only on resolution; modelled as a tiny constant).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Iterable

import httpx
import polars as pl

from . import http, prices

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Config:
    entry_hours_before_close: int = 1   # how many hours before resolution to enter
    entry_price_min: float = 0.55       # favorite-price floor
    entry_price_max: float = 0.85       # favorite-price ceiling
    fee_bps: float = 0.0                # round-trip fee in basis points (Polymarket default 0)
    slippage_bps: float = 100.0         # entry slippage in bps (~1% default)
    redemption_gas_usd: float = 0.05    # rough Polygon gas at $0.05 per redeem
    stake_per_market_usd: float = 100.0 # uniform stake across markets
    min_market_volume_usd: float = 10_000.0


@dataclass
class TradeResult:
    market_id: str
    condition_id: str
    question: str
    event_title: str | None
    end_date_iso: str
    yes_resolved: float
    yes_entry_price: float | None
    favorite_side: str | None     # "YES" / "NO" / None if no price
    favorite_entry_price: float | None
    favorite_won: bool | None
    excluded_reason: str | None
    pnl_usd: float
    roi: float


def _resolve_payoff(yes_resolved: float, favorite_side: str) -> bool:
    if favorite_side == "YES":
        return yes_resolved > 0.5
    return yes_resolved < 0.5


def simulate_one(
    market: dict,
    history: list[dict],
    cfg: Config,
) -> TradeResult:
    end_dt = datetime.fromisoformat(market["end_date_iso"].replace("Z", "+00:00"))
    end_ts = int(end_dt.timestamp())
    entry_ts = end_ts - cfg.entry_hours_before_close * 3600

    yes_resolved = float(market["outcome_prices_final"][0])

    base = TradeResult(
        market_id=str(market["market_id"]),
        condition_id=str(market["condition_id"]),
        question=market["question"],
        event_title=market.get("event_title"),
        end_date_iso=market["end_date_iso"],
        yes_resolved=yes_resolved,
        yes_entry_price=None,
        favorite_side=None,
        favorite_entry_price=None,
        favorite_won=None,
        excluded_reason=None,
        pnl_usd=0.0,
        roi=0.0,
    )

    if not history:
        base.excluded_reason = "no_price_history"
        return base
    yes_price = prices.price_at_or_before(history, entry_ts)
    if yes_price is None:
        base.excluded_reason = "no_price_at_entry"
        return base
    base.yes_entry_price = yes_price

    favorite_side = "YES" if yes_price >= 0.5 else "NO"
    favorite_price = yes_price if favorite_side == "YES" else (1.0 - yes_price)
    base.favorite_side = favorite_side
    base.favorite_entry_price = favorite_price

    if not (cfg.entry_price_min <= favorite_price <= cfg.entry_price_max):
        base.excluded_reason = "favorite_price_out_of_band"
        return base
    if 0.45 <= yes_resolved <= 0.55:
        base.excluded_reason = "ambiguous_resolution"
        return base

    favorite_won = _resolve_payoff(yes_resolved, favorite_side)
    base.favorite_won = favorite_won

    slip = cfg.slippage_bps / 10_000.0
    fee = cfg.fee_bps / 10_000.0
    effective_entry = favorite_price * (1.0 + slip)

    payoff_per_dollar = (1.0 / effective_entry) if favorite_won else 0.0
    payoff_per_dollar *= (1.0 - fee)

    pnl_per_dollar = payoff_per_dollar - 1.0
    pnl_usd = pnl_per_dollar * cfg.stake_per_market_usd - cfg.redemption_gas_usd
    roi = pnl_usd / cfg.stake_per_market_usd

    base.pnl_usd = round(pnl_usd, 4)
    base.roi = round(roi, 6)
    return base


async def fetch_history_batch(
    client: httpx.AsyncClient,
    markets_iter: Iterable[dict],
    *,
    fidelity_min: int = 60,
) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for m in markets_iter:
        tid = m.get("yes_token_id")
        if not tid:
            continue
        try:
            out[tid] = await prices.prices_history(
                client, tid, interval="max", fidelity_min=fidelity_min
            )
        except Exception as exc:
            log.warning("prices history failed %s: %s", tid, exc)
            out[tid] = []
    return out


async def fetch_all_histories(
    markets_df: pl.DataFrame,
    *,
    fidelity_min: int = 60,
    min_volume: float = 10_000.0,
    progress_every: int = 200,
) -> dict[str, list[dict]]:
    """Pull prices_history once per market; cache by yes_token_id."""
    df = markets_df.filter(pl.col("volume_usd") >= min_volume)
    log.info("fetch_all_histories: %d markets to fetch", df.height)
    out: dict[str, list[dict]] = {}
    async with http.session(timeout=30) as client:
        rows = df.to_dicts()
        for i, m in enumerate(rows, start=1):
            tid = m.get("yes_token_id")
            if not tid or tid in out:
                continue
            try:
                out[tid] = await prices.prices_history(
                    client, tid, interval="max", fidelity_min=fidelity_min
                )
            except Exception as exc:
                log.warning("price fetch failed for %s: %s", tid, exc)
                out[tid] = []
            if i % progress_every == 0:
                log.info("  ... %d/%d", i, len(rows))
    return out


def simulate_grid(
    markets_df: pl.DataFrame,
    histories: dict[str, list[dict]],
    cfg: Config,
) -> pl.DataFrame:
    """Run one config against pre-fetched histories. Cheap, repeatable."""
    df = markets_df.filter(pl.col("volume_usd") >= cfg.min_market_volume_usd)
    results = [
        simulate_one(m, histories.get(m.get("yes_token_id") or "", []), cfg)
        for m in df.to_dicts()
        if m.get("yes_token_id")
    ]
    return pl.DataFrame([asdict(r) for r in results])


async def run_backtest(
    markets_df: pl.DataFrame,
    cfg: Config,
    *,
    fidelity_min: int = 60,
    progress_every: int = 100,
) -> pl.DataFrame:
    histories = await fetch_all_histories(
        markets_df,
        fidelity_min=fidelity_min,
        min_volume=cfg.min_market_volume_usd,
        progress_every=progress_every,
    )
    return simulate_grid(markets_df, histories, cfg)


def summarize(trades: pl.DataFrame, cfg: Config) -> dict:
    """Return-stats over the included subset."""
    included = trades.filter(pl.col("excluded_reason").is_null())
    n_total = trades.height
    n_included = included.height
    if n_included == 0:
        return {"config": asdict(cfg), "n_total": n_total, "n_included": 0}

    pnl = included["pnl_usd"]
    roi = included["roi"]
    won = included.filter(pl.col("favorite_won"))
    win_rate = won.height / n_included
    total_pnl = float(pnl.sum())
    total_stake = n_included * cfg.stake_per_market_usd
    avg_roi = float(roi.mean())
    return {
        "config": asdict(cfg),
        "n_total_markets": n_total,
        "n_included": n_included,
        "n_excluded": n_total - n_included,
        "exclusion_breakdown": (
            trades.filter(pl.col("excluded_reason").is_not_null())
            .group_by("excluded_reason").len().sort("len", descending=True).to_dicts()
        ),
        "win_rate": round(win_rate, 4),
        "total_stake_usd": round(total_stake, 2),
        "total_pnl_usd": round(total_pnl, 2),
        "avg_roi_per_trade": round(avg_roi, 6),
        "total_return_pct": round(total_pnl / total_stake * 100, 3) if total_stake else 0,
    }
