"""Strategy fingerprint metrics from a trader's bundled data.

Produces a flat dict of measurable signals; downstream cohort analysis tells us
which signals separate market-makers from directional/event-driven traders.
"""

from __future__ import annotations

from statistics import mean, median
from typing import Any


def _percentile(sorted_vals: list, q: float):
    if not sorted_vals:
        return 0
    idx = max(0, min(len(sorted_vals) - 1, int(q * len(sorted_vals))))
    return sorted_vals[idx]


def fingerprint(trader: dict[str, Any]) -> dict[str, Any]:
    address = trader["address"]
    trades = trader["trades"]
    closed = trader["closed_positions"]
    open_positions = trader["open_positions"]

    fp: dict[str, Any] = {
        "address": address,
        "current_value_usd": round(float(trader["current_value"]), 2),
        "n_open_positions": len(open_positions),
        "n_closed_positions": len(closed),
        "n_trades": len(trades),
    }

    if trades:
        n = len(trades)
        ts = sorted(int(t["timestamp"]) for t in trades)
        span_s = ts[-1] - ts[0]
        span_d = max(1.0, span_s / 86400.0)

        sides = [t.get("side", "") for t in trades]
        n_buy = sum(1 for s in sides if s == "BUY")

        sizes_usd = sorted(float(t["size"]) * float(t["price"]) for t in trades)
        diffs = sorted(ts[i + 1] - ts[i] for i in range(n - 1))

        cond_ids = {t.get("conditionId", "") for t in trades}
        event_slugs = {t.get("eventSlug", "") or t.get("slug", "") for t in trades}

        # Co-occurring trades on the same second across opposite outcomes
        # (proxy for paired YES/NO arb or atomic hedge entries).
        by_event_ts: dict[tuple[str, int], set[int]] = {}
        for t in trades:
            key = (t.get("eventSlug", "") or t.get("slug", ""), int(t["timestamp"]))
            by_event_ts.setdefault(key, set()).add(t.get("outcomeIndex", -1))
        paired_seconds = sum(1 for outs in by_event_ts.values() if len(outs) > 1)

        fp.update(
            {
                "active_span_days": round(span_d, 1),
                "trades_per_day": round(n / span_d, 2),
                "buy_ratio": round(n_buy / n, 3),
                "unique_markets": len(cond_ids),
                "unique_events": len(event_slugs),
                "market_concentration": round(n / max(1, len(cond_ids)), 2),  # trades per market
                "trade_size_usd_median": round(median(sizes_usd), 2),
                "trade_size_usd_mean": round(mean(sizes_usd), 2),
                "trade_size_usd_p95": round(_percentile(sizes_usd, 0.95), 2),
                "traded_volume_usd": round(sum(sizes_usd), 2),
                "inter_arrival_median_s": _percentile(diffs, 0.5) if diffs else 0,
                "inter_arrival_p10_s": _percentile(diffs, 0.1) if diffs else 0,
                "inter_arrival_p90_s": _percentile(diffs, 0.9) if diffs else 0,
                "same_second_trade_pct": round(
                    100 * sum(1 for d in diffs if d == 0) / max(1, len(diffs)), 1
                ),
                "paired_outcome_event_seconds": paired_seconds,
                "paired_pct_of_events": round(100 * paired_seconds / max(1, len(by_event_ts)), 1),
            }
        )

    if closed:
        realized = [float(p.get("realizedPnl", 0) or 0) for p in closed]
        wins = sum(1 for r in realized if r > 0)
        losses = sum(1 for r in realized if r < 0)
        fp.update(
            {
                "realized_pnl_total": round(sum(realized), 2),
                "realized_pnl_wins": wins,
                "realized_pnl_losses": losses,
                "realized_win_rate": round(wins / len(closed), 3),
                "avg_realized_pnl_per_position": round(sum(realized) / len(closed), 2),
            }
        )

    return fp


_NUMERIC_KEYS = (
    "n_trades",
    "trades_per_day",
    "buy_ratio",
    "unique_markets",
    "unique_events",
    "market_concentration",
    "trade_size_usd_median",
    "traded_volume_usd",
    "inter_arrival_median_s",
    "inter_arrival_p10_s",
    "same_second_trade_pct",
    "paired_pct_of_events",
    "realized_pnl_total",
    "realized_win_rate",
    "current_value_usd",
)


def cohort_summary(fingerprints: list[dict]) -> dict[str, Any]:
    out: dict[str, Any] = {"n_traders": len(fingerprints)}
    for key in _NUMERIC_KEYS:
        vals = [fp[key] for fp in fingerprints if key in fp]
        if not vals:
            continue
        sv = sorted(vals)
        out[key] = {
            "median": round(median(sv), 2),
            "min": round(min(sv), 2),
            "max": round(max(sv), 2),
        }
    return out
