"""Wire tracker → copy_strategy → risk → executor.

Default mode is PAPER (no real orders). Live mode requires --live flag in CLI
plus explicit py-clob-client setup. Paper mode logs every decision so we can
compare ex-post pnl against actual market resolution later.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from . import data_api, http
from .copy_strategy import CopyConfig, CopyDecision, decide
from .risk import RiskLimits, RiskState, book_open, check

log = logging.getLogger(__name__)

DEFAULT_POLL_SEC = 5
DEFAULT_TRADES_PER_POLL = 50
SEEN_CAP_PER_ADDR = 500


def _state_load(path: Path) -> dict:
    if not path.exists():
        return {"seen_tx": {}}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {"seen_tx": {}}


def _state_save(path: Path, seen_tx: dict[str, set[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"seen_tx": {a: list(s) for a, s in seen_tx.items()}}, separators=(",", ":"))
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


async def _execute_paper(decision: CopyDecision, log_path: Path) -> dict:
    """Pretend to place an order; just log what we'd do."""
    rec = {
        "kind": "paper_order",
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        **asdict(decision),
    }
    _append_jsonl(log_path, rec)
    return rec


async def run(
    addresses: Iterable[str],
    cfg: CopyConfig,
    limits: RiskLimits,
    *,
    poll_interval_sec: int = DEFAULT_POLL_SEC,
    log_dir: Path = Path("data/copy"),
    iterations: int | None = None,
    live: bool = False,
) -> None:
    if live:
        raise NotImplementedError(
            "live mode requires py-clob-client integration (V2.1). Currently paper-only."
        )

    addresses = [a.lower() for a in addresses]
    log_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    trade_log = log_dir / f"observed_trades_{today}.jsonl"
    decision_log = log_dir / f"decisions_{today}.jsonl"
    paper_log = log_dir / f"paper_orders_{today}.jsonl"
    state_path = log_dir / "tracker_state.json"
    risk_path = log_dir / "risk_state.json"

    seen_state = _state_load(state_path)
    seen: dict[str, set[str]] = {a: set(seen_state.get("seen_tx", {}).get(a, [])) for a in addresses}
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
                    seen[addr].update(t.get("transactionHash") for t in trades)
                    first_poll[addr] = False
                    log.info("[%s] baseline indexed %d trades", addr[:12], len(trades))
                    continue

                if not new_trades:
                    continue

                log.info("[%s] %d NEW trades", addr[:12], len(new_trades))
                observed_at = int(t_start)
                for t in sorted(new_trades, key=lambda x: int(x.get("timestamp") or 0)):
                    record = _trade_record(t, addr, observed_at)
                    _append_jsonl(trade_log, record)
                    seen[addr].add(t.get("transactionHash"))

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

                    allowed, reason = check(decision, risk_state, limits)
                    if not allowed:
                        log.warning("  [risk-block] %s", reason)
                        _append_jsonl(
                            paper_log,
                            {"kind": "risk_block", "reason": reason, **asdict(decision)},
                        )
                        continue

                    book_open(risk_state, decision.target_addr, decision.our_target_usd)
                    rec = await _execute_paper(decision, paper_log)
                    log.info(
                        "  [paper-order] %s/%s size=%.2f tokens @ <=$%.4f, ours=$%.2f",
                        decision.market_title[:30], decision.outcome,
                        decision.our_target_size_tokens, decision.our_max_price,
                        decision.our_target_usd,
                    )

                if len(seen[addr]) > SEEN_CAP_PER_ADDR:
                    seen[addr] = set(list(seen[addr])[-SEEN_CAP_PER_ADDR:])

            _state_save(state_path, seen)
            risk_state.save(risk_path)
            polls += 1

            elapsed = asyncio.get_event_loop().time() - t_start
            sleep_for = max(0.5, poll_interval_sec - elapsed)
            if iterations is None or polls < iterations:
                await asyncio.sleep(sleep_for)

    log.info("copy_runner stop after %d polls", polls)
