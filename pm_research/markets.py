"""gamma-api wrappers for resolved markets discovery (events + markets)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Iterable

import httpx

from .http import get_json

GAMMA = "https://gamma-api.polymarket.com"
PAGE_LIMIT = 100  # gamma-api hard caps at 100 regardless of higher values

log = logging.getLogger(__name__)


async def list_events(
    client: httpx.AsyncClient,
    *,
    closed: bool = True,
    tag_slug: str | None = "sports",
    order: str = "endDate",
    ascending: bool = False,
    max_pages: int = 50,
) -> list[dict]:
    """Paginated event fetch with optional tag filter (e.g. tag_slug='sports')."""
    out: list[dict] = []
    for page in range(max_pages):
        params: dict = {
            "closed": str(closed).lower(),
            "limit": PAGE_LIMIT,
            "offset": page * PAGE_LIMIT,
            "order": order,
            "ascending": str(ascending).lower(),
        }
        if tag_slug:
            params["tag_slug"] = tag_slug
        rows = await get_json(client, f"{GAMMA}/events", params=params)
        if not rows:
            break
        out.extend(rows)
        if len(rows) < PAGE_LIMIT:
            break
    return out


def extract_markets(events: Iterable[dict]) -> list[dict]:
    """Flatten events into a per-market list, carrying parent-event context."""
    rows: list[dict] = []
    for ev in events:
        for m in ev.get("markets", []) or []:
            try:
                outcomes = json.loads(m.get("outcomes", "[]"))
                outcome_prices = json.loads(m.get("outcomePrices", "[]"))
                clob_token_ids = json.loads(m.get("clobTokenIds", "[]"))
            except json.JSONDecodeError:
                continue
            if not outcomes or not outcome_prices or not clob_token_ids:
                continue
            rows.append(
                {
                    "event_id": ev.get("id"),
                    "event_title": ev.get("title"),
                    "event_ticker": ev.get("ticker"),
                    "event_tags": ",".join(t.get("slug", "") for t in (ev.get("tags") or [])),
                    "market_id": m.get("id"),
                    "condition_id": m.get("conditionId"),
                    "question": m.get("question"),
                    "slug": m.get("slug"),
                    "outcomes": outcomes,
                    "outcome_prices_final": [float(x) for x in outcome_prices],
                    "yes_token_id": str(clob_token_ids[0]) if len(clob_token_ids) >= 1 else None,
                    "no_token_id": str(clob_token_ids[1]) if len(clob_token_ids) >= 2 else None,
                    "volume_usd": float(m.get("volumeNum", 0) or m.get("volume", 0) or 0),
                    "end_date_iso": m.get("endDate"),
                    "start_date_iso": m.get("startDate"),
                    "maker_base_fee": int(m.get("makerBaseFee", 0) or 0),
                    "taker_base_fee": int(m.get("takerBaseFee", 0) or 0),
                    "min_tick_size": float(m.get("orderPriceMinTickSize", 0.01) or 0.01),
                    "min_order_size": float(m.get("orderMinSize", 0) or 0),
                    "neg_risk": bool(m.get("negRisk", False)),
                }
            )
    return rows
