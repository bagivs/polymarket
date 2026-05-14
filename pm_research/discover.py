"""Build a candidate trader pool by joining multiple Polymarket leaderboards.

Strategy:
  - Pull top-N profit for week/month/year/all and top-N volume for month.
  - Pivot to one row per wallet with profit_<period> and volume_<period> columns.
  - Label each wallet with a coarse cohort: sustained_winner, market_maker_candidate,
    event_or_directional, or uncategorized.

The resulting Parquet is the seed list for the per-trader fingerprinting step.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from pathlib import Path

import polars as pl

from . import http, leaderboard

log = logging.getLogger(__name__)

PROFIT_PERIODS: tuple[leaderboard.Period, ...] = ("day", "week", "month", "year", "all")
VOLUME_PERIODS: tuple[leaderboard.Period, ...] = ("week", "month")
# lb-api caps results at 50 regardless of higher limit values; see data-sources.md.
DEFAULT_LIMIT = 50

# Cohort thresholds (USD). Coarse first pass; tune after seeing distributions.
SUSTAINED_MIN_PROFIT = 5_000.0
SUSTAINED_YEAR_VS_WEEK_RATIO = 3.0  # year profit must be >= ratio * week profit
MARKET_MAKER_MIN_VOLUME = 1_000_000.0
MARKET_MAKER_MAX_MARGIN = 0.005
DIRECTIONAL_MIN_YEAR_PROFIT = 100_000.0


async def fetch_all_leaderboards(
    limit: int = DEFAULT_LIMIT,
) -> dict[tuple[str, str], list[dict]]:
    async with http.session() as client:
        coros: list[tuple[tuple[str, str], asyncio.Task]] = []
        for period in PROFIT_PERIODS:
            coros.append(
                (
                    ("profit", period),
                    asyncio.create_task(leaderboard.top(client, "profit", period, limit=limit)),
                )
            )
        for period in VOLUME_PERIODS:
            coros.append(
                (
                    ("volume", period),
                    asyncio.create_task(leaderboard.top(client, "volume", period, limit=limit)),
                )
            )
        out: dict[tuple[str, str], list[dict]] = {}
        for key, task in coros:
            try:
                out[key] = await task
            except Exception as exc:
                log.error("leaderboard fetch failed %s: %s", key, exc)
                out[key] = []
        return out


def _to_long(boards: dict[tuple[str, str], list[dict]]) -> pl.DataFrame:
    rows: list[dict] = []
    for (metric, period), entries in boards.items():
        for rank, e in enumerate(entries, start=1):
            rows.append(
                {
                    "address": (e.get("proxyWallet") or "").lower(),
                    "name": e.get("name"),
                    "pseudonym": e.get("pseudonym"),
                    "metric": metric,
                    "period": period,
                    "rank": rank,
                    "amount": float(e.get("amount") or 0.0),
                }
            )
    if not rows:
        return pl.DataFrame(
            schema={
                "address": pl.Utf8,
                "name": pl.Utf8,
                "pseudonym": pl.Utf8,
                "metric": pl.Utf8,
                "period": pl.Utf8,
                "rank": pl.Int64,
                "amount": pl.Float64,
            }
        )
    return pl.DataFrame(rows)


def _candidates(long: pl.DataFrame) -> pl.DataFrame:
    if long.is_empty():
        return long

    profit_pivot = (
        long.filter(pl.col("metric") == "profit")
        .pivot(values="amount", index="address", on="period", aggregate_function="first")
    )
    profit_pivot = profit_pivot.rename(
        {c: f"profit_{c}" for c in profit_pivot.columns if c != "address"}
    )

    volume_pivot = (
        long.filter(pl.col("metric") == "volume")
        .pivot(values="amount", index="address", on="period", aggregate_function="first")
    )
    volume_pivot = volume_pivot.rename(
        {c: f"volume_{c}" for c in volume_pivot.columns if c != "address"}
    )

    names = long.group_by("address").agg(
        pl.col("name").drop_nulls().first().alias("name"),
        pl.col("pseudonym").drop_nulls().first().alias("pseudonym"),
    )

    df = names.join(profit_pivot, on="address", how="left").join(
        volume_pivot, on="address", how="left"
    )

    money_cols = [c for c in df.columns if c.startswith(("profit_", "volume_"))]
    df = df.with_columns([pl.col(c).fill_null(0.0) for c in money_cols])

    profit_cols = [c for c in df.columns if c.startswith("profit_")]
    df = df.with_columns(
        pl.concat_list(profit_cols).list.min().alias("min_profit_window"),
    )

    has_year = "profit_year" in df.columns
    has_week = "profit_week" in df.columns
    has_month = "profit_month" in df.columns and "volume_month" in df.columns
    has_volume = "volume_month" in df.columns

    # "Sustained winner" requires profit in every window AND year profit not
    # dominated by a single recent week (year >= ratio*week). Otherwise the
    # account is just a recent one-shot winner showing up in every list.
    sustained_clauses = [pl.col("min_profit_window") > SUSTAINED_MIN_PROFIT]
    if has_year and has_week:
        sustained_clauses.append(
            pl.col("profit_year") >= SUSTAINED_YEAR_VS_WEEK_RATIO * pl.col("profit_week")
        )
    sustained = sustained_clauses[0]
    for c in sustained_clauses[1:]:
        sustained = sustained & c

    cohort_expr = pl.when(sustained).then(pl.lit("sustained_winner"))

    # Recent one-shot: positive in all windows but year ≈ week (concentrated).
    if has_year and has_week:
        cohort_expr = cohort_expr.when(
            (pl.col("min_profit_window") > SUSTAINED_MIN_PROFIT)
            & (pl.col("profit_year") < SUSTAINED_YEAR_VS_WEEK_RATIO * pl.col("profit_week"))
        ).then(pl.lit("recent_oneshot_winner"))

    if has_month:
        cohort_expr = cohort_expr.when(
            (pl.col("volume_month") > MARKET_MAKER_MIN_VOLUME)
            & (
                pl.col("profit_month").abs()
                < pl.col("volume_month") * MARKET_MAKER_MAX_MARGIN
            )
        ).then(pl.lit("market_maker_candidate"))

    if has_year:
        cohort_expr = cohort_expr.when(
            pl.col("profit_year") > DIRECTIONAL_MIN_YEAR_PROFIT
        ).then(pl.lit("event_or_directional"))

    df = df.with_columns(cohort_expr.otherwise(pl.lit("uncategorized")).alias("cohort"))

    sort_col = "profit_month" if "profit_month" in df.columns else profit_cols[0]
    return df.sort(sort_col, descending=True)


async def run(out_dir: Path, limit: int = DEFAULT_LIMIT) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    boards = await fetch_all_leaderboards(limit)
    long = _to_long(boards)
    cand = _candidates(long)

    long_path = out_dir / f"{today}_leaderboard_long.parquet"
    cand_path = out_dir / f"{today}_candidates.parquet"
    long.write_parquet(long_path)
    cand.write_parquet(cand_path)

    cohort_counts = (
        cand.group_by("cohort").len().sort("len", descending=True).to_dicts()
        if not cand.is_empty()
        else []
    )

    return {
        "date": today,
        "leaderboards_fetched": len(boards),
        "rows_long": long.height,
        "candidates": cand.height,
        "cohorts": cohort_counts,
        "long_path": str(long_path),
        "candidates_path": str(cand_path),
    }
