"""Enrich a candidates parquet with true period-windowed PnL from user-pnl-api,
then re-cohort with currently-winning vs dormant signal.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from pathlib import Path

import polars as pl

from . import http, user_pnl

log = logging.getLogger(__name__)

# Cohort thresholds (USD).
WIN_AT_SCALE_1M = 100_000.0
SMALL_WIN_1M = 5_000.0
LARGE_LOSS_1M = -100_000.0
DORMANT_1D_TOL = 100.0
HIGH_LIFETIME_VOL = 100_000_000.0
HIGH_LIFETIME_PROFIT = 1_000_000.0


async def fetch_pnl_for_addresses(
    addresses: list[str],
    intervals: tuple[user_pnl.Interval, ...] = ("1d", "1w", "1m"),
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    async with http.session() as client:
        for addr in addresses:
            try:
                out[addr] = await user_pnl.multi_interval_deltas(
                    client, addr, intervals=intervals
                )
            except Exception as exc:
                log.error("user-pnl failed for %s: %s", addr, exc)
                out[addr] = {iv: float("nan") for iv in intervals}
    return out


def _label_cohort_v2(row: dict) -> str:
    p1d = row.get("pnl_1d") or 0.0
    p1m = row.get("pnl_1m") or 0.0
    life_p = row.get("profit_all") or 0.0
    life_v = row.get("volume_month") or 0.0  # lb-api volume is also lifetime in practice

    if abs(p1d) < DORMANT_1D_TOL and abs(p1m) < DORMANT_1D_TOL:
        return "dormant"
    if p1m >= WIN_AT_SCALE_1M:
        if life_p >= HIGH_LIFETIME_PROFIT and (p1m / life_p) < 0.5:
            return "consistent_winner"
        if p1m >= 500_000:
            return "recent_surge_winner"
        return "currently_winning"
    if life_v >= HIGH_LIFETIME_VOL and abs(p1m) < SMALL_WIN_1M:
        return "high_vol_break_even"
    if p1m < LARGE_LOSS_1M:
        return "actively_losing"
    if p1m >= SMALL_WIN_1M:
        return "small_winner"
    return "low_activity"


async def enrich(
    candidates_path: Path,
    out_path: Path | None = None,
) -> dict:
    df = pl.read_parquet(candidates_path)
    addrs = df["address"].to_list()
    pnl_map = await fetch_pnl_for_addresses(addrs)

    pnl_rows = [
        {
            "address": addr,
            "pnl_1d": float(pnl_map.get(addr, {}).get("1d") or 0.0),
            "pnl_1w": float(pnl_map.get(addr, {}).get("1w") or 0.0),
            "pnl_1m": float(pnl_map.get(addr, {}).get("1m") or 0.0),
        }
        for addr in addrs
    ]
    pnl_df = pl.DataFrame(pnl_rows)

    enriched = df.join(pnl_df, on="address", how="left")
    enriched = enriched.with_columns(
        pl.struct(enriched.columns)
        .map_elements(_label_cohort_v2, return_dtype=pl.Utf8)
        .alias("cohort_v2")
    )
    enriched = enriched.sort("pnl_1m", descending=True, nulls_last=True)

    today = date.today().isoformat()
    if out_path is None:
        out_path = candidates_path.parent / f"{today}_candidates_v2.parquet"
    enriched.write_parquet(out_path)

    summary = {
        "input": str(candidates_path),
        "output": str(out_path),
        "n_candidates": enriched.height,
        "cohort_v2_counts": (
            enriched.group_by("cohort_v2").len().sort("len", descending=True).to_dicts()
        ),
        "top_10_by_1m_pnl": (
            enriched.select(["pseudonym", "address", "pnl_1d", "pnl_1w", "pnl_1m", "cohort_v2"])
            .head(10)
            .to_dicts()
        ),
    }
    return summary
