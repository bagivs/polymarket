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
SEEN_CAP_PER_ADDR = 500  # rolling window of seen tx_hashes per address


def _state_load(path: Path) -> dict:
    if not path.exists():
        return {"seen_tx": {}}
    try:
        return json.loads(path.read_text())
    except Exception:
        log.warning("state file corrupt at %s; starting fresh", path)
        return {"seen_tx": {}}


def _state_save(path: Path, seen_tx: dict[str, set[str]]) -> None:
    path.write_text(
        json.dumps(
            {"seen_tx": {a: list(s) for a, s in seen_tx.items()}},
            separators=(",", ":"),
        )
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
    seen: dict[str, set[str]] = {a: set(state.get("seen_tx", {}).get(a, [])) for a in addresses}
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
                    seen[addr].update(t.get("transactionHash") for t in trades)
                    first_poll[addr] = False
                    log.info("[%s] baseline indexed %d trades", addr[:12], len(trades))
                elif new_trades:
                    log.info("[%s] %d NEW trades", addr[:12], len(new_trades))
                    observed_at = int(time.time())
                    # log oldest first so JSONL is roughly chronological
                    for t in sorted(new_trades, key=lambda x: int(x.get("timestamp") or 0)):
                        _append_jsonl(today_path, _trade_record(t, addr, observed_at))
                        seen[addr].add(t.get("transactionHash"))

                # Cap rolling window of seen hashes
                if len(seen[addr]) > SEEN_CAP_PER_ADDR:
                    seen[addr] = set(list(seen[addr])[-SEEN_CAP_PER_ADDR:])

            _state_save(state_path, seen)
            polls += 1

            elapsed = asyncio.get_event_loop().time() - t_start
            sleep_for = max(0.5, poll_interval_sec - elapsed)
            if iterations is None or polls < iterations:
                await asyncio.sleep(sleep_for)

    log.info("tracker stop after %d polls", polls)
