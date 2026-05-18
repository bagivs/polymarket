"""Continuous trader discovery + ranking.

Pipeline:
1. lb-api leaderboard (5 periods x 2 metrics) → seed pool
2. global recent /trades scan → discover currently-active wallets
3. user-pnl-api enrich → real 1d/1w/1m PnL deltas (lb-api period is broken)
4. dormant filter → drop wallets with no recent activity
5. cohort labelling (sustained_winner / recent_surge / etc.)
6. Save dated parquet to data/scans/ for trend analysis

Output: `data/scans/<date>_candidates.parquet` with columns:
  address, pseudonym, lifetime_profit, 1d_pnl, 1w_pnl, 1m_pnl,
  active_recent (bool), cohort_v2, recent_activity_score
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx
import polars as pl

from . import data_api, discover, enrich as enrich_mod, http, leaderboard, user_pnl

log = logging.getLogger(__name__)


async def _global_recent_active(client: httpx.AsyncClient, n_pages: int = 7) -> Counter:
    """Scan global recent /trades, count appearances per address."""
    appearances: Counter = Counter()
    for page in range(n_pages):
        try:
            trades = await data_api.trades(
                client, taker_only=False, limit=500, offset=page * 500
            )
            for t in trades:
                addr = (t.get("proxyWallet") or "").lower()
                if addr:
                    appearances[addr] += 1
        except Exception as exc:
            log.warning("global scan page %d failed: %s", page, exc)
            break
    return appearances


async def run_scan(
    out_dir: Path = Path("data/scans"),
    lb_limit: int = 50,
    global_scan_pages: int = 7,
    top_active_addresses: int = 100,
) -> dict:
    """End-to-end one-shot scan. Returns summary dict; writes dated parquet."""
    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    log.info("scan start: lb_limit=%d global_pages=%d", lb_limit, global_scan_pages)

    # 1. Lb-api leaderboards
    leaderboards = await discover.fetch_all_leaderboards(limit=lb_limit)
    long_df = discover._to_long(leaderboards)
    cand_lb = discover._candidates(long_df)
    log.info("lb-api candidates: %d", cand_lb.height)

    # 2. Global active scan
    async with http.session(timeout=30) as client:
        global_app = await _global_recent_active(client, n_pages=global_scan_pages)
    top_active = [a for a, _ in global_app.most_common(top_active_addresses)]
    log.info("global-scan distinct addresses (top %d): %d", top_active_addresses, len(top_active))

    # 3. Merge address pool
    lb_set = set(cand_lb["address"].to_list()) if not cand_lb.is_empty() else set()
    pool = lb_set | set(top_active)
    log.info("merged pool: %d unique addresses", len(pool))

    # 4. Enrich each with user-pnl-api (1d, 1w, 1m)
    pnl_map = await enrich_mod.fetch_pnl_for_addresses(list(pool))

    # 5. Build final dataframe
    rows = []
    pseu_map = (
        {r["address"]: r.get("pseudonym") for r in cand_lb.to_dicts()}
        if not cand_lb.is_empty()
        else {}
    )
    name_map = (
        {r["address"]: r.get("name") for r in cand_lb.to_dicts()}
        if not cand_lb.is_empty()
        else {}
    )
    for addr in pool:
        p = pnl_map.get(addr, {})
        rows.append(
            {
                "address": addr,
                "pseudonym": pseu_map.get(addr),
                "name": name_map.get(addr),
                "pnl_1d": float(p.get("1d") or 0),
                "pnl_1w": float(p.get("1w") or 0),
                "pnl_1m": float(p.get("1m") or 0),
                "in_lb_top": addr in lb_set,
                "global_recent_trades": global_app.get(addr, 0),
            }
        )
    df = pl.DataFrame(rows)

    # 6. Cohort labelling
    df = df.with_columns(
        pl.struct(df.columns)
        .map_elements(_cohort_v3, return_dtype=pl.Utf8)
        .alias("cohort")
    )
    df = df.sort("pnl_1m", descending=True)

    # 7. Save
    out_path = out_dir / f"{today}_candidates.parquet"
    df.write_parquet(out_path)

    summary = {
        "scan_at": today,
        "lb_candidates": cand_lb.height if not cand_lb.is_empty() else 0,
        "global_active_addresses": len(top_active),
        "merged_pool": len(pool),
        "cohort_counts": (
            df.group_by("cohort").len().sort("len", descending=True).to_dicts()
            if not df.is_empty()
            else []
        ),
        "out_path": str(out_path),
        "top_10_by_1m_pnl": (
            df.select(["pseudonym", "address", "pnl_1d", "pnl_1w", "pnl_1m", "cohort"])
            .head(10)
            .to_dicts()
        ),
    }
    log.info("scan complete: %d candidates → %s", df.height, out_path)
    return summary


def _cohort_v3(row: dict) -> str:
    """Same logic as enrich._label_cohort_v2 but no dependence on lb-api lifetime."""
    p1d = float(row.get("pnl_1d") or 0)
    p1m = float(row.get("pnl_1m") or 0)
    if abs(p1d) < 100 and abs(p1m) < 100:
        return "dormant"
    if p1m >= 500_000:
        return "recent_surge_winner"
    if p1m >= 100_000:
        return "currently_winning"
    if p1m >= 5_000:
        return "small_winner"
    if p1m <= -100_000:
        return "actively_losing"
    return "low_activity"
