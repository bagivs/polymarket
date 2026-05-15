"""Live execution layer — wraps py-clob-client.

Reads credentials from .env (PRIVATE_KEY, POLYMARKET_API_KEY/SECRET/PASSPHRASE,
POLYMARKET_RELAY_API_ADDRESS, FUNDER_ADDRESS). Default signature_type is
POLY_GNOSIS_SAFE (2) which is what the Polymarket UI uses; if preflight
fails we fall back to POLY_PROXY (1).

Hard rule: every order goes through risk.check() upstream — this module
just submits, it does NOT enforce limits. Guard separation of concerns.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, AssetType, BalanceAllowanceParams, OrderArgs
from py_clob_client.constants import POLYGON

log = logging.getLogger(__name__)

CLOB_HOST = "https://clob.polymarket.com"

# Polymarket signature types (from py-clob-client docs / OrderBuilder source)
SIG_EOA = 0
SIG_POLY_PROXY = 1
SIG_POLY_GNOSIS_SAFE = 2


def _load_env(env_path: Path) -> dict:
    if not env_path.exists():
        return {}
    out = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


@dataclass
class ExecutorConfig:
    private_key: str
    api_key: str
    api_secret: str
    api_passphrase: str
    funder: str
    signature_type: int = SIG_POLY_GNOSIS_SAFE


def config_from_env(env_path: Path = Path(".env")) -> ExecutorConfig:
    e = _load_env(env_path)
    missing = [k for k in (
        "PRIVATE_KEY", "POLYMARKET_API_KEY", "POLYMARKET_API_SECRET",
        "POLYMARKET_API_PASSPHRASE",
    ) if not e.get(k)]
    if missing:
        raise RuntimeError(f"missing env keys: {missing}")
    funder = e.get("POLYMARKET_RELAY_API_ADDRESS") or e.get("FUNDER_ADDRESS")
    if not funder:
        raise RuntimeError("need POLYMARKET_RELAY_API_ADDRESS or FUNDER_ADDRESS")
    return ExecutorConfig(
        private_key=e["PRIVATE_KEY"],
        api_key=e["POLYMARKET_API_KEY"],
        api_secret=e["POLYMARKET_API_SECRET"],
        api_passphrase=e["POLYMARKET_API_PASSPHRASE"],
        funder=funder,
    )


class Executor:
    def __init__(self, cfg: ExecutorConfig) -> None:
        self.cfg = cfg
        self.client = ClobClient(
            host=CLOB_HOST,
            chain_id=POLYGON,
            key=cfg.private_key,
            creds=ApiCreds(
                api_key=cfg.api_key,
                api_secret=cfg.api_secret,
                api_passphrase=cfg.api_passphrase,
            ),
            signature_type=cfg.signature_type,
            funder=cfg.funder,
        )

    def preflight(self) -> dict:
        """Return diagnostic dict; raises only on hard failures."""
        out: dict = {
            "host": CLOB_HOST,
            "chain_id": POLYGON,
            "signature_type": self.cfg.signature_type,
            "funder": self.cfg.funder,
            "address_from_key": None,
            "ok_endpoint": None,
            "l1_auth": None,
            "l2_auth": None,
            "usdc_balance": None,
            "usdc_allowance": None,
            "errors": [],
        }
        try:
            out["address_from_key"] = self.client.get_address()
        except Exception as exc:
            out["errors"].append(f"get_address: {exc}")
        try:
            out["ok_endpoint"] = self.client.get_ok()
        except Exception as exc:
            out["errors"].append(f"get_ok: {exc}")
        try:
            self.client.assert_level_1_auth()
            out["l1_auth"] = "ok"
        except Exception as exc:
            out["l1_auth"] = f"FAIL: {exc}"
        try:
            self.client.assert_level_2_auth()
            out["l2_auth"] = "ok"
        except Exception as exc:
            out["l2_auth"] = f"FAIL: {exc}"
        try:
            ba = self.client.get_balance_allowance(
                BalanceAllowanceParams(
                    asset_type=AssetType.COLLATERAL,
                    signature_type=self.cfg.signature_type,
                )
            )
            out["usdc_balance"] = ba.get("balance") if isinstance(ba, dict) else str(ba)
            out["usdc_allowance"] = ba.get("allowance") if isinstance(ba, dict) else None
        except Exception as exc:
            out["errors"].append(f"balance_allowance: {exc}")
        return out

    def post_buy(self, *, token_id: str, max_price: float, size_tokens: float) -> dict:
        """Place a GTC limit BUY order. Returns the raw API response."""
        args = OrderArgs(
            token_id=str(token_id),
            price=float(max_price),
            size=float(size_tokens),
            side="BUY",
        )
        log.info(
            "post_buy: token=%s... size=%.4f price<=%.4f",
            str(token_id)[:24], size_tokens, max_price,
        )
        return self.client.create_and_post_order(args)

    def cancel(self, order_id: str) -> dict:
        return self.client.cancel(order_id)

    def set_usdc_allowance(self) -> dict:
        """Approve the CTF exchange to spend our USDC. One-time setup."""
        return self.client.update_balance_allowance(
            BalanceAllowanceParams(
                asset_type=AssetType.COLLATERAL,
                signature_type=self.cfg.signature_type,
            )
        )
