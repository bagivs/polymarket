"""On-chain resolution lookup via Polygon RPC.

Polymarket markets settle on the Gnosis ConditionalTokens contract on Polygon
(0x4D97DCd97eC945f40cF65F87097ACe5EA0476045). When gamma-api drops a market
from its REST endpoint (common for short-duration sport markets after
settlement), the resolution is still readable on-chain via:

    payoutDenominator(bytes32 conditionId) -> uint
        0 = unresolved, >0 = resolved (typically 1)
    getOutcomeSlotCount(bytes32 conditionId) -> uint
        2 for binary YES/NO markets
    payoutNumerators(bytes32 conditionId, uint index) -> uint
        per-outcome payout (denom = payoutDenominator)
        binary win = [1,0] (YES won) or [0,1] (NO won)

For our purposes, payout_per_token[i] = numerators[i] / denominator.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Iterable

import httpx
from Crypto.Hash import keccak

log = logging.getLogger(__name__)

CTF_POLYGON = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"


def _selector(signature: str) -> str:
    k = keccak.new(digest_bits=256)
    k.update(signature.encode())
    return "0x" + k.hexdigest()[:8]


SEL_DENOMINATOR = _selector("payoutDenominator(bytes32)")  # 0xdd34de67
SEL_NUMERATORS = _selector("payoutNumerators(bytes32,uint256)")  # 0x0504c814
SEL_SLOT_COUNT = _selector("getOutcomeSlotCount(bytes32)")  # 0xd42dc0c2


def _eth_call_payload(data: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"to": CTF_POLYGON, "data": data}, "latest"],
        "id": 1,
    }


def _hex_to_int(hex_str: str) -> int:
    if not hex_str or hex_str == "0x":
        return 0
    return int(hex_str, 16)


async def _eth_call(client: httpx.AsyncClient, rpc_url: str, data: str) -> int | None:
    try:
        r = (await client.post(rpc_url, json=_eth_call_payload(data), timeout=15)).json()
    except Exception as exc:
        log.warning("eth_call failed: %s", exc)
        return None
    if "error" in r:
        return None
    return _hex_to_int(r.get("result", "0x"))


async def fetch_resolution(
    client: httpx.AsyncClient, rpc_url: str, condition_id: str
) -> dict | None:
    """Return {denominator, numerators, slot_count, payouts_per_token} or None on error.

    payouts_per_token is the normalized fraction-per-token (0..1) per outcome index.
    """
    cid_padded = condition_id.lower().replace("0x", "").zfill(64)

    denom = await _eth_call(client, rpc_url, SEL_DENOMINATOR + cid_padded)
    if denom is None:
        return None
    if denom == 0:
        return {"resolved": False, "denominator": 0}

    slots = await _eth_call(client, rpc_url, SEL_SLOT_COUNT + cid_padded)
    if not slots:
        return {"resolved": False, "denominator": denom, "error": "no slot count"}

    numerators: list[int] = []
    for i in range(slots):
        data = SEL_NUMERATORS + cid_padded + hex(i)[2:].zfill(64)
        n = await _eth_call(client, rpc_url, data)
        numerators.append(n or 0)

    payouts = [n / denom for n in numerators]
    return {
        "resolved": True,
        "denominator": denom,
        "slot_count": slots,
        "numerators": numerators,
        "payouts_per_token": payouts,
    }


async def fetch_resolutions(
    rpc_url: str, condition_ids: Iterable[str], concurrency: int = 20
) -> dict[str, dict | None]:
    """Batch-fetch resolutions for many conditionIds."""
    out: dict[str, dict | None] = {}
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(timeout=20) as client:

        async def one(cid: str) -> None:
            async with sem:
                out[cid] = await fetch_resolution(client, rpc_url, cid)

        await asyncio.gather(*(one(c) for c in condition_ids))
    return out


def winning_outcome_index(resolution: dict) -> int | None:
    """For binary markets, return the index whose payout is 1 (or highest)."""
    if not resolution or not resolution.get("resolved"):
        return None
    nums = resolution.get("numerators") or []
    if not nums:
        return None
    return nums.index(max(nums))
