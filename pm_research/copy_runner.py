"""Wire tracker → copy_strategy → risk → executor.

Default mode is PAPER (no real orders). Live mode requires --live flag in CLI
plus explicit py-clob-client setup. Paper mode logs every decision so we can
compare ex-post pnl against actual market resolution later.

V2.2 in-poll fill aggregation: target traders (surfandturf, swisstony,
LaBradfordSmith etc.) burst-execute by splitting one position into many
micro-fills, each a separate API trade. Without aggregation, our copy
strategy emits one decision per fill — most below the min_size threshold,
so 80%+ get skipped. We instead group fills sharing (target, market,
outcome, side) within the same poll and emit ONE decision for the merged
size at VWAP price. Individual fills are still logged to observed_trades
for analysis.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from . import data_api, http
from .copy_strategy import CopyConfig, CopyDecision, decide
from .risk import RiskLimits, RiskState, book_open, check
from .executor import Executor

log = logging.getLogger(__name__)

DEFAULT_POLL_SEC = 5
DEFAULT_TRADES_PER_POLL = 50
SEEN_CAP_PER_ADDR = 100_000  # was 500 — way too small for high-frequency targets;
# at 500 cap with set() (no insertion order), high-freq trades fall out and get
# re-detected as "new" → 1000x duplicate logging within hours. 100k is safe
# for ~24h of even the busiest target (LaBradfordSm peaked ~80k in past run).


def _state_load(path: Path) -> dict:
    if not path.exists():
        return {"seen_tx": {}}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {"seen_tx": {}}


def _state_save(path: Path, seen_tx: dict[str, dict[str, int]]) -> None:
    """seen_tx now: addr -> {tx_hash: ts} (insertion-ordered dict)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"seen_tx": seen_tx}, separators=(",", ":"))
    )


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")


def _trade_record(trade: dict, target: str, observed_at: int) -> dict:
    size = float(trade.get("size") or 0)
    price = float(trade.get("price") or 0)
    return {
        "observed_at": observed_at,
        "target": target,
        "tx": trade.get("transactionHash"),
        "ts": trade.get("timestamp"),
        "lag_sec": observed_at - int(trade.get("timestamp") or 0),
        "title": trade.get("title"),
        "slug": trade.get("slug"),
        "conditionId": trade.get("conditionId"),
        "asset": trade.get("asset"),
        "outcome": trade.get("outcome"),
        "outcomeIndex": trade.get("outcomeIndex"),
        "side": trade.get("side"),
        "size": size,
        "price": price,
        "usd": round(size * price, 4),
        "pseudonym": trade.get("pseudonym"),
        "name": trade.get("name"),
    }


def aggregate_fills(records: list[dict]) -> list[dict]:
    """Group fills by (target, conditionId, outcome, side) and emit a single
    synthetic record per group with summed tokens and VWAP price.

    Singleton groups pass through unchanged. Aggregates carry _aggregate_of
    and _aggregate_tx_hashes for traceability.
    """
    groups: dict[tuple, list[dict]] = {}
    order: list[tuple] = []
    for r in records:
        key = (r.get("target"), r.get("conditionId"), r.get("outcome"), r.get("side"))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)

    out: list[dict] = []
    for key in order:
        fills = groups[key]
        if len(fills) == 1:
            out.append(fills[0])
            continue
        total_tokens = sum(float(f.get("size") or 0) for f in fills)
        total_usd = sum(float(f.get("size") or 0) * float(f.get("price") or 0) for f in fills)
        if total_tokens <= 0:
            out.append(fills[-1])
            continue
        vwap = total_usd / total_tokens
        latest = max(fills, key=lambda f: int(f.get("ts") or f.get("timestamp") or 0))
        agg = dict(latest)
        agg["size"] = round(total_tokens, 6)
        agg["price"] = round(vwap, 6)
        agg["usd"] = round(total_usd, 4)
        agg["_aggregate_of"] = len(fills)
        agg["_aggregate_tx_hashes"] = [f.get("tx") or f.get("transactionHash") for f in fills]
        out.append(agg)
    return out


async def _execute_paper(decision: CopyDecision, log_path: Path) -> dict:
    """Pretend to place an order; just log what we'd do."""
    rec = {
        "kind": "paper_order",
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        **asdict(decision),
    }
    _append_jsonl(log_path, rec)
    return rec


async def _execute_live(
    decision: CopyDecision, executor: Executor, log_path: Path
) -> dict:
    """Submit a real GTC limit BUY via py-clob-client. Logs both attempt and result."""
    record_base = {
        "kind": "live_order",
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        **asdict(decision),
    }
    try:
        # py-clob-client is sync; run in thread pool to avoid blocking the loop.
        resp = await asyncio.to_thread(
            executor.post_buy,
            token_id=decision.asset_id,
            max_price=decision.our_max_price,
            size_tokens=decision.our_target_size_tokens,
        )
        record_base["result"] = "submitted"
        record_base["api_response"] = resp
    except Exception as exc:
        record_base["result"] = "error"
        record_base["error"] = str(exc)
        log.error("live order failed: %s", exc)
    _append_jsonl(log_path, record_base)
    return record_base


async def run(
    addresses: Iterable[str],
    cfg: CopyConfig,
    limits: RiskLimits,
    *,
    poll_interval_sec: int = DEFAULT_POLL_SEC,
    log_dir: Path = Path("data/copy"),
    iterations: int | None = None,
    live: bool = False,
    executor: Executor | None = None,
) -> None:
    if live and executor is None:
        raise RuntimeError("live=True requires an Executor instance")

    addresses = [a.lower() for a in addresses]
    log_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    trade_log = log_dir / f"observed_trades_{today}.jsonl"
    decision_log = log_dir / f"decisions_{today}.jsonl"
    paper_log = log_dir / f"paper_orders_{today}.jsonl"
    state_path = log_dir / "tracker_state.json"
    risk_path = log_dir / "risk_state.json"

    seen_state = _state_load(state_path)
    # Per-address ordered dict: tx_hash -> timestamp. Insertion order preserved
    # so we can trim oldest when SEEN_CAP_PER_ADDR is exceeded.
    raw_seen = seen_state.get("seen_tx", {})
    seen: dict[str, dict[str, int]] = {}
    for a in addresses:
        v = raw_seen.get(a, {})
        if isinstance(v, list):  # legacy: list of tx hashes (no ts)
            seen[a] = {tx: 0 for tx in v}
        else:
            seen[a] = dict(v)
    first_poll: dict[str, bool] = {a: (len(seen[a]) == 0) for a in addresses}
    risk_state = RiskState.load(risk_path)

    log.info(
        "copy_runner start: %d addrs, paper=%s, poll=%ds, log_dir=%s",
        len(addresses), not live, poll_interval_sec, log_dir,
    )

    polls = 0
    async with http.session(timeout=20) as client:
        while iterations is None or polls < iterations:
            t_start = asyncio.get_event_loop().time()
            for addr in addresses:
                try:
                    trades = await data_api.trades(
                        client, user=addr, taker_only=False, limit=DEFAULT_TRADES_PER_POLL
                    )
                except Exception as exc:
                    log.warning("poll fail %s: %s", addr[:12], exc)
                    continue

                new_trades = [t for t in trades if t.get("transactionHash") not in seen[addr]]
                if first_poll[addr]:
                    for t in trades:
                        tx = t.get("transactionHash")
                        if tx:
                            seen[addr][tx] = int(t.get("timestamp", 0))
                    first_poll[addr] = False
                    log.info("[%s] baseline indexed %d trades", addr[:12], len(trades))
                    continue

                if not new_trades:
                    continue

                log.info("[%s] %d NEW trades", addr[:12], len(new_trades))
                observed_at = int(time.time())

                # 1) Log every individual fill (for analysis) and update dedup set.
                fill_records: list[dict] = []
                for t in sorted(new_trades, key=lambda x: int(x.get("timestamp") or 0)):
                    record = _trade_record(t, addr, observed_at)
                    _append_jsonl(trade_log, record)
                    tx = t.get("transactionHash")
                    if tx:
                        seen[addr][tx] = int(t.get("timestamp", 0))
                    fill_records.append(record)

                # 2) Aggregate fills sharing (target, market, outcome, side) into
                #    a single synthetic trade for the decision layer.
                aggregated = aggregate_fills(fill_records)
                if len(aggregated) < len(fill_records):
                    log.info(
                        "  aggregated %d fills → %d decisions", len(fill_records), len(aggregated)
                    )

                for record in aggregated:
                    decision = decide(record, cfg)
                    _append_jsonl(decision_log, asdict(decision))

                    if decision.decision != "copy":
                        log.info(
                            "  [skip %s/%s] %s — %s",
                            decision.market_title[:30],
                            decision.outcome,
                            decision.reason,
                            "",
                        )
                        continue

                    allowed, risk_reason = check(decision, risk_state, limits)
                    if not allowed:
                        log.warning("  [risk-block] %s", risk_reason)
                        _append_jsonl(
                            paper_log,
                            {**asdict(decision), "kind": "risk_block", "risk_reason": risk_reason},
                        )
                        continue

                    book_open(risk_state, decision.target_addr, decision.our_target_usd)
                    if live and executor is not None:
                        rec = await _execute_live(decision, executor, paper_log)
                        log.info(
                            "  [LIVE-order:%s] %s/%s size=%.2f @ <=$%.4f, ours=$%.2f",
                            rec.get("result"), decision.market_title[:30], decision.outcome,
                            decision.our_target_size_tokens, decision.our_max_price,
                            decision.our_target_usd,
                        )
                    else:
                        rec = await _execute_paper(decision, paper_log)
                        log.info(
                            "  [paper-order] %s/%s size=%.2f tokens @ <=$%.4f, ours=$%.2f",
                            decision.market_title[:30], decision.outcome,
                            decision.our_target_size_tokens, decision.our_max_price,
                            decision.our_target_usd,
                        )

                # Insertion-ordered trim: drop oldest entries when cap exceeded
                if len(seen[addr]) > SEEN_CAP_PER_ADDR:
                    excess = len(seen[addr]) - SEEN_CAP_PER_ADDR
                    for k in list(seen[addr].keys())[:excess]:
                        del seen[addr][k]

            _state_save(state_path, seen)
            risk_state.save(risk_path)
            polls += 1

            elapsed = asyncio.get_event_loop().time() - t_start
            sleep_for = max(0.5, poll_interval_sec - elapsed)
            if iterations is None or polls < iterations:
                await asyncio.sleep(sleep_for)

    log.info("copy_runner stop after %d polls", polls)
