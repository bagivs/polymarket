"""Wire tracker → copy_strategy → risk → executor.

Default mode is PAPER (no real orders). Live mode requires --live flag in CLI
plus explicit py-clob-client setup. Paper mode logs every decision so we can
compare ex-post pnl against actual market resolution later.

V2.2 in-poll aggregation merged fills sharing (target, market, outcome, side)
WITHIN a single poll cycle. V2.3 generalises this to CROSS-POLL: fills are
buffered per group; an aggregate emits when either (a) the first fill is
`aggregate_max_sec` old (force timeout) or (b) no new fill has arrived for
`aggregate_quiet_sec` (burst quieted). This catches the common case where
a single trader's position-build spans 30-120 seconds across many polls.
Backtest tolerates 30-60s additional decision lag (still +ROI per
findings-v2-backtest.md).
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

    return [_merge_fills(groups[key]) for key in order]


def _merge_fills(fills: list[dict]) -> dict:
    if len(fills) == 1:
        return fills[0]
    total_tokens = sum(float(f.get("size") or 0) for f in fills)
    total_usd = sum(float(f.get("size") or 0) * float(f.get("price") or 0) for f in fills)
    if total_tokens <= 0:
        return fills[-1]
    vwap = total_usd / total_tokens
    latest = max(fills, key=lambda f: int(f.get("ts") or f.get("timestamp") or 0))
    agg = dict(latest)
    agg["size"] = round(total_tokens, 6)
    agg["price"] = round(vwap, 6)
    agg["usd"] = round(total_usd, 4)
    agg["_aggregate_of"] = len(fills)
    agg["_aggregate_tx_hashes"] = [f.get("tx") or f.get("transactionHash") for f in fills]
    return agg


class CrossPollAggregator:
    """Buffer fills per (target, conditionId, outcome, side); emit aggregated
    records when the position's first fill ages past `max_window_sec` (force
    timeout) OR when no new fill has arrived for `quiet_window_sec` (burst
    quieted).
    """

    def __init__(self, max_window_sec: int = 30, quiet_window_sec: int = 5) -> None:
        self.max_window_sec = max_window_sec
        self.quiet_window_sec = quiet_window_sec
        self.pending: dict[tuple, dict] = {}

    def add(self, record: dict) -> None:
        key = (
            record.get("target"),
            record.get("conditionId"),
            record.get("outcome"),
            record.get("side"),
        )
        ts = int(record.get("ts") or record.get("timestamp") or 0)
        slot = self.pending.get(key)
        if slot is None:
            self.pending[key] = {"fills": [record], "first_ts": ts, "last_ts": ts}
        else:
            slot["fills"].append(record)
            slot["last_ts"] = max(slot["last_ts"], ts)

    def emit_ready(self, now_ts: int) -> list[dict]:
        """Return aggregated records whose buffer expired; remove them from pending."""
        out: list[dict] = []
        for key in list(self.pending.keys()):
            slot = self.pending[key]
            first_age = now_ts - slot["first_ts"]
            last_age = now_ts - slot["last_ts"]
            if (
                first_age >= self.max_window_sec
                or last_age >= self.quiet_window_sec
            ):
                out.append(_merge_fills(slot["fills"]))
                del self.pending[key]
        return out

    def flush_all(self) -> list[dict]:
        """Emit everything pending (for shutdown)."""
        out = [_merge_fills(slot["fills"]) for slot in self.pending.values()]
        self.pending.clear()
        return out

    def size(self) -> int:
        return len(self.pending)


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
    aggregate_max_sec: int = 30,
    aggregate_quiet_sec: int = 5,
) -> None:
    if live and executor is None:
        raise RuntimeError("live=True requires an Executor instance")

    addresses = [a.lower() for a in addresses]
    aggregator = CrossPollAggregator(
        max_window_sec=aggregate_max_sec, quiet_window_sec=aggregate_quiet_sec
    )
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

                # 2) Push every fill into the cross-poll aggregator; emit
                #    happens later (after polling all addresses) when timing
                #    thresholds are met.
                for record in fill_records:
                    aggregator.add(record)

            # End of this poll cycle — emit any aggregates whose window expired.
            now_ts = int(time.time())
            ready = aggregator.emit_ready(now_ts)
            if ready:
                log.info("  cross-poll emit: %d aggregates (pending=%d)", len(ready), aggregator.size())
            for record in ready:
                decision = decide(record, cfg)
                _append_jsonl(decision_log, asdict(decision))

                if decision.decision != "copy":
                    log.info(
                        "  [skip %s/%s] %s — ",
                        decision.market_title[:30],
                        decision.outcome,
                        decision.reason,
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

            # The trailing dedup-trim logic must run AFTER aggregator emit so it
            # doesn't interfere with the in-poll bookkeeping.
            for addr in addresses:
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
