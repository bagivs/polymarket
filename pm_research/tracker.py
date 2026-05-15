"""Read-only copy-trade tracker.

Polls a list of target addresses on data-api/trades every N seconds and
logs every new trade observation as JSONL. Restart-tolerant: persists
the last-seen transaction hashes per address in a small JSON state file
so a restart picks up where we left off.

V1 is intentionally minimal — no CLOB price enrichment, no order
placement, no risk guard. Just trustworthy detection + persistence.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from . import data_api, http

log = logging.getLogger(__name__)

DEFAULT_POLL_SEC = 5
DEFAULT_TRADES_PER_POLL = 50
SEEN_CAP_PER_ADDR = 100_000  # see copy_runner.py for rationale


def _state_load(path: Path) -> dict:
    if not path.exists():
        return {"seen_tx": {}}
    try:
        return json.loads(path.read_text())
    except Exception:
        log.warning("state file corrupt at %s; starting fresh", path)
        return {"seen_tx": {}}


def _state_save(path: Path, seen_tx: dict[str, dict[str, int]]) -> None:
    path.write_text(
        json.dumps({"seen_tx": seen_tx}, separators=(",", ":"))
    )


def _append_jsonl(path: Path, record: dict) -> None:
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


async def track(
    addresses: Iterable[str],
    *,
    poll_interval_sec: int = DEFAULT_POLL_SEC,
    log_dir: Path = Path("data/tracker"),
    state_path: Path | None = None,
    trades_per_poll: int = DEFAULT_TRADES_PER_POLL,
    iterations: int | None = None,
) -> None:
    """Run the polling loop. iterations=None -> forever; otherwise N polls then exit."""
    addresses = [a.lower() for a in addresses]
    log_dir.mkdir(parents=True, exist_ok=True)
    today_path = log_dir / f"trades_{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"
    state_path = state_path or (log_dir / "state.json")

    state = _state_load(state_path)
    raw = state.get("seen_tx", {})
    seen: dict[str, dict[str, int]] = {}
    for a in addresses:
        v = raw.get(a, {})
        seen[a] = {tx: 0 for tx in v} if isinstance(v, list) else dict(v)
    first_poll: dict[str, bool] = {a: (len(seen[a]) == 0) for a in addresses}

    log.info(
        "tracker start: %d addrs, poll_interval=%ds, log=%s, state=%s",
        len(addresses), poll_interval_sec, today_path, state_path,
    )

    polls = 0
    async with http.session(timeout=20) as client:
        while iterations is None or polls < iterations:
            t_start = asyncio.get_event_loop().time()
            for addr in addresses:
                try:
                    trades = await data_api.trades(
                        client, user=addr, taker_only=False, limit=trades_per_poll
                    )
                except Exception as exc:
                    log.warning("poll fail %s: %s", addr[:12], exc)
                    continue

                new_trades = [t for t in trades if t.get("transactionHash") not in seen[addr]]
                if first_poll[addr]:
                    # Baseline: index everything as seen, do not log
                    for t in trades:
                        tx = t.get("transactionHash")
                        if tx:
                            seen[addr][tx] = int(t.get("timestamp", 0))
                    first_poll[addr] = False
                    log.info("[%s] baseline indexed %d trades", addr[:12], len(trades))
                elif new_trades:
                    log.info("[%s] %d NEW trades", addr[:12], len(new_trades))
                    observed_at = int(time.time())
                    for t in sorted(new_trades, key=lambda x: int(x.get("timestamp") or 0)):
                        _append_jsonl(today_path, _trade_record(t, addr, observed_at))
                        tx = t.get("transactionHash")
                        if tx:
                            seen[addr][tx] = int(t.get("timestamp", 0))

                # Trim oldest if cap exceeded (insertion-ordered dict)
                if len(seen[addr]) > SEEN_CAP_PER_ADDR:
                    excess = len(seen[addr]) - SEEN_CAP_PER_ADDR
                    for k in list(seen[addr].keys())[:excess]:
                        del seen[addr][k]

            _state_save(state_path, seen)
            polls += 1

            elapsed = asyncio.get_event_loop().time() - t_start
            sleep_for = max(0.5, poll_interval_sec - elapsed)
            if iterations is None or polls < iterations:
                await asyncio.sleep(sleep_for)

    log.info("tracker stop after %d polls", polls)
