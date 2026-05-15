"""Copy-trade decision logic.

Given a target trader's new trade, decide whether and how we'd mirror it
with our (much smaller) bankroll. Pure logic — no I/O, no order placement.
The Executor module wires this into either paper-mode (log only) or live
(py-clob-client) execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class CopyConfig:
    """Per-target weights and cohort-wide hard limits."""

    targets: dict[str, float] = field(default_factory=dict)
    """address (lower) -> scale_fraction (e.g. 0.01 = 1% of their size)"""

    max_size_per_trade_usd: float = 50.0
    """Hard cap on a single copy order, in USDC."""

    max_slippage_pct: float = 0.05
    """Max premium over their entry price we'll pay (e.g. 0.05 = 5%)."""

    min_size_per_trade_usd: float = 1.0
    """Skip copies smaller than this (gas would dominate)."""

    skip_if_their_price_above: float = 0.95
    """Don't copy if their entry price > this (no upside left)."""

    skip_if_lag_above_sec: int = 300
    """Don't copy if we detected the trade more than N seconds late."""

    skip_sells: bool = True
    """V1: only mirror BUYs (winners almost never sell directly)."""

    skip_underdog_below: float | None = None
    """If set, skip when their_price < this (e.g. 0.45 to skip underdog bucket).
    Backtest 2026-05-15: cohort underdog ROI only +5% vs +33% favorite/+54% neutral."""


@dataclass
class CopyDecision:
    target_addr: str
    target_pseudonym: str | None
    market_condition_id: str
    asset_id: str
    market_title: str
    outcome: str
    side: str
    their_price: float
    their_size: float
    their_usd: float
    lag_sec: int
    our_target_size_tokens: float
    our_max_price: float
    our_target_usd: float
    decision: Literal["copy", "skip"]
    reason: str


def decide(trade_record: dict, cfg: CopyConfig) -> CopyDecision:
    """Pure decision: would we copy this trade, and with what parameters?"""
    addr = (trade_record.get("target") or "").lower()
    side = trade_record.get("side", "")
    their_price = float(trade_record.get("price") or 0)
    their_size = float(trade_record.get("size") or 0)
    their_usd = float(trade_record.get("usd") or their_price * their_size)
    lag = int(trade_record.get("lag_sec") or 0)

    base = CopyDecision(
        target_addr=addr,
        target_pseudonym=trade_record.get("pseudonym") or trade_record.get("name"),
        market_condition_id=trade_record.get("conditionId", ""),
        asset_id=trade_record.get("asset", ""),
        market_title=trade_record.get("title", ""),
        outcome=trade_record.get("outcome", ""),
        side=side,
        their_price=their_price,
        their_size=their_size,
        their_usd=their_usd,
        lag_sec=lag,
        our_target_size_tokens=0.0,
        our_max_price=0.0,
        our_target_usd=0.0,
        decision="skip",
        reason="",
    )

    if addr not in cfg.targets:
        base.reason = f"unknown target {addr[:10]}"
        return base
    weight = cfg.targets[addr]
    if weight <= 0:
        base.reason = "target weight <= 0"
        return base
    if cfg.skip_sells and side != "BUY":
        base.reason = f"skip side={side}"
        return base
    if their_price <= 0 or their_size <= 0:
        base.reason = "invalid price/size"
        return base
    if their_price > cfg.skip_if_their_price_above:
        base.reason = f"their_price {their_price:.3f} > {cfg.skip_if_their_price_above}"
        return base
    if cfg.skip_underdog_below is not None and their_price < cfg.skip_underdog_below:
        base.reason = (
            f"underdog: their_price {their_price:.3f} < {cfg.skip_underdog_below}"
        )
        return base
    if lag > cfg.skip_if_lag_above_sec:
        base.reason = f"lag {lag}s > {cfg.skip_if_lag_above_sec}s"
        return base

    our_max_price = their_price * (1 + cfg.max_slippage_pct)
    if our_max_price >= 0.99:
        # too expensive after slippage
        base.our_max_price = our_max_price
        base.reason = f"max_price {our_max_price:.3f} >= 0.99"
        return base

    target_tokens = their_size * weight
    target_usd = target_tokens * our_max_price

    if target_usd > cfg.max_size_per_trade_usd:
        target_tokens = cfg.max_size_per_trade_usd / our_max_price
        target_usd = cfg.max_size_per_trade_usd

    if target_usd < cfg.min_size_per_trade_usd:
        base.reason = f"target_usd ${target_usd:.2f} < min ${cfg.min_size_per_trade_usd:.2f}"
        base.our_target_usd = target_usd
        return base

    base.our_target_size_tokens = target_tokens
    base.our_max_price = our_max_price
    base.our_target_usd = target_usd
    base.decision = "copy"
    base.reason = "ok"
    return base
