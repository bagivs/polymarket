"""Smoke tests: imports + offline metric computation + mocked HTTP wrappers."""

from __future__ import annotations

import httpx
import pytest
import respx

from pm_research import data_api, discover, leaderboard, metrics, profile


def test_imports_resolve():
    for mod in (data_api, discover, leaderboard, metrics, profile):
        assert mod is not None


def test_fingerprint_empty_trader():
    fp = metrics.fingerprint(
        {"address": "0xabc", "trades": [], "closed_positions": [], "open_positions": [], "current_value": 0.0}
    )
    assert fp["address"] == "0xabc"
    assert fp["n_trades"] == 0


def test_fingerprint_with_trades():
    trades = [
        {"timestamp": 1000, "side": "BUY", "size": 10, "price": 0.5,
         "conditionId": "0xc1", "eventSlug": "ev1", "outcomeIndex": 0},
        {"timestamp": 1000, "side": "BUY", "size": 5, "price": 0.5,
         "conditionId": "0xc1", "eventSlug": "ev1", "outcomeIndex": 1},  # paired same-second
        {"timestamp": 1010, "side": "SELL", "size": 8, "price": 0.6,
         "conditionId": "0xc1", "eventSlug": "ev1", "outcomeIndex": 0},
    ]
    closed = [{"realizedPnl": 12.5}, {"realizedPnl": -3.0}]
    fp = metrics.fingerprint(
        {"address": "0xabc", "trades": trades, "closed_positions": closed,
         "open_positions": [], "current_value": 100.0}
    )
    assert fp["n_trades"] == 3
    assert fp["unique_markets"] == 1
    assert fp["unique_events"] == 1
    assert fp["paired_outcome_event_seconds"] == 1
    assert pytest.approx(fp["buy_ratio"], rel=1e-3) == 2 / 3
    assert fp["realized_pnl_total"] == 9.5
    assert fp["realized_win_rate"] == 0.5


def test_cohort_summary_handles_mixed():
    fps = [
        {"address": "a", "n_trades": 100, "trades_per_day": 10.0, "buy_ratio": 1.0,
         "current_value_usd": 50.0},
        {"address": "b", "n_trades": 200, "trades_per_day": 20.0, "buy_ratio": 0.5,
         "current_value_usd": 100.0},
    ]
    s = metrics.cohort_summary(fps)
    assert s["n_traders"] == 2
    assert s["n_trades"]["min"] == 100
    assert s["n_trades"]["max"] == 200


@respx.mock
@pytest.mark.asyncio
async def test_leaderboard_top_calls_lb_api():
    respx.get("https://lb-api.polymarket.com/profit").mock(
        return_value=httpx.Response(200, json=[{"proxyWallet": "0xabc", "amount": 1.0,
                                                 "name": "x", "pseudonym": "x"}])
    )
    async with httpx.AsyncClient() as client:
        rows = await leaderboard.top(client, "profit", "month", limit=10)
    assert rows[0]["proxyWallet"] == "0xabc"


@respx.mock
@pytest.mark.asyncio
async def test_data_api_value():
    respx.get("https://data-api.polymarket.com/value").mock(
        return_value=httpx.Response(200, json=[{"user": "0xabc", "value": 42.5}])
    )
    async with httpx.AsyncClient() as client:
        v = await data_api.value(client, "0xabc")
    assert v == 42.5
