"""RiskGuard: pre-flight checks + global state limits.

Stateful guard that gates every CopyDecision before execution. Tracks:
- cumulative USD deployed (open + spent)
- realized loss for the day
- per-target outstanding position size
- copy-rate per minute (avoid spam if upstream goes haywire)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from .copy_strategy import CopyDecision


@dataclass(frozen=True)
class RiskLimits:
    max_gross_open_usd: float = 200.0
    """Sum of all 'in flight' position notional we tolerate."""

    max_per_target_open_usd: float = 100.0
    """Per-target sub-cap."""

    max_daily_realized_loss_usd: float = 50.0
    """If realized loss for the day exceeds this, halt all copies."""

    max_copies_per_minute: int = 10
    """Rate limit on order submissions."""

    max_copies_per_hour: int = 100
    """Hourly rate limit."""


@dataclass
class RiskState:
    open_positions_usd: dict[str, float] = field(default_factory=dict)
    """address -> sum of open USD"""

    realized_pnl_today: float = 0.0
    today_iso: str = ""

    copy_timestamps: list[float] = field(default_factory=list)
    """unix timestamps of recent copy orders (rolling)"""

    halt_reason: str = ""

    @classmethod
    def load(cls, path: Path) -> "RiskState":
        if not path.exists():
            return cls()
        try:
            d = json.loads(path.read_text())
            return cls(
                open_positions_usd=dict(d.get("open_positions_usd", {})),
                realized_pnl_today=float(d.get("realized_pnl_today", 0.0)),
                today_iso=d.get("today_iso", ""),
                copy_timestamps=list(d.get("copy_timestamps", [])),
                halt_reason=d.get("halt_reason", ""),
            )
        except Exception:
            return cls()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "open_positions_usd": self.open_positions_usd,
                    "realized_pnl_today": self.realized_pnl_today,
                    "today_iso": self.today_iso,
                    "copy_timestamps": self.copy_timestamps[-200:],
                    "halt_reason": self.halt_reason,
                },
                separators=(",", ":"),
            )
        )


def _gross_open_usd(state: RiskState) -> float:
    return sum(state.open_positions_usd.values())


def _trim_old_copies(state: RiskState, now: float) -> None:
    state.copy_timestamps = [t for t in state.copy_timestamps if now - t < 3600]


def check(decision: CopyDecision, state: RiskState, limits: RiskLimits) -> tuple[bool, str]:
    """Return (allowed, reason). Mutates state.copy_timestamps if allowed."""
    now = time.time()
    today = time.strftime("%Y-%m-%d", time.gmtime(now))

    # Reset realized PnL on day rollover
    if state.today_iso != today:
        state.today_iso = today
        state.realized_pnl_today = 0.0
        state.halt_reason = ""

    if state.halt_reason:
        return False, f"halted: {state.halt_reason}"

    if state.realized_pnl_today < -limits.max_daily_realized_loss_usd:
        state.halt_reason = (
            f"daily loss {state.realized_pnl_today:.2f} < -{limits.max_daily_realized_loss_usd}"
        )
        return False, state.halt_reason

    _trim_old_copies(state, now)
    last_minute = sum(1 for t in state.copy_timestamps if now - t < 60)
    last_hour = len(state.copy_timestamps)
    if last_minute >= limits.max_copies_per_minute:
        return False, f"rate limit: {last_minute} copies in last 60s"
    if last_hour >= limits.max_copies_per_hour:
        return False, f"rate limit: {last_hour} copies in last 3600s"

    gross_after = _gross_open_usd(state) + decision.our_target_usd
    if gross_after > limits.max_gross_open_usd:
        return False, (
            f"gross open ${_gross_open_usd(state):.2f} + ${decision.our_target_usd:.2f} "
            f"> cap ${limits.max_gross_open_usd:.2f}"
        )

    per_target = state.open_positions_usd.get(decision.target_addr, 0.0)
    if per_target + decision.our_target_usd > limits.max_per_target_open_usd:
        return False, (
            f"per-target ${per_target:.2f} + ${decision.our_target_usd:.2f} "
            f"> cap ${limits.max_per_target_open_usd:.2f}"
        )

    state.copy_timestamps.append(now)
    return True, "ok"


def book_open(state: RiskState, target_addr: str, usd: float) -> None:
    state.open_positions_usd[target_addr] = state.open_positions_usd.get(target_addr, 0.0) + usd


def book_close(state: RiskState, target_addr: str, usd_returned: float, original_usd: float) -> None:
    state.open_positions_usd[target_addr] = max(
        0.0, state.open_positions_usd.get(target_addr, 0.0) - original_usd
    )
    state.realized_pnl_today += usd_returned - original_usd
