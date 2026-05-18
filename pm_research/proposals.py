"""Proposal queue for cohort changes.

Continuous scan writes dated parquets to data/scans/. This module reads the
latest scan, compares against the current active cohort, and surfaces NEW
candidates that meet basic criteria — as PROPOSALS for the user to review.

NO automatic addition. User must explicitly decide to include a proposal
in the next runner restart. Active cohort is tracked in data/cohort.json.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import polars as pl


DEFAULT_COHORT_FILE = Path("data/cohort.json")


def load_cohort(path: Path = DEFAULT_COHORT_FILE) -> dict[str, float]:
    if not path.exists():
        return {}
    return json.loads(path.read_text()).get("targets", {})


def save_cohort(targets: dict[str, float], path: Path = DEFAULT_COHORT_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"updated_at": datetime.now(timezone.utc).isoformat(), "targets": targets},
            indent=2,
        )
    )


def find_proposals(
    scan_dir: Path = Path("data/scans"),
    cohort_path: Path = DEFAULT_COHORT_FILE,
    min_1m_pnl: float = 200_000,
    min_1w_pnl: float = 20_000,
    max_per_proposal: int = 20,
) -> dict:
    """Compare latest scan against active cohort; return new candidates."""
    scan_files = sorted(scan_dir.glob("*_candidates.parquet"))
    if not scan_files:
        return {"error": "no scan parquets found — run `scan` first"}
    latest = scan_files[-1]
    df = pl.read_parquet(latest)

    active = set(load_cohort(cohort_path).keys())
    proposals = df.filter(
        (pl.col("pnl_1m") >= min_1m_pnl)
        & (pl.col("pnl_1w") >= min_1w_pnl)
        & (~pl.col("address").is_in(list(active)))
    ).sort("pnl_1m", descending=True).head(max_per_proposal)

    return {
        "scan_file": str(latest),
        "active_cohort": list(active),
        "thresholds": {"min_1m_pnl": min_1m_pnl, "min_1w_pnl": min_1w_pnl},
        "n_proposals": proposals.height,
        "proposals": proposals.select(
            ["address", "pseudonym", "pnl_1d", "pnl_1w", "pnl_1m", "cohort"]
        ).to_dicts(),
    }


def approve(address: str, weight: float, cohort_path: Path = DEFAULT_COHORT_FILE) -> dict:
    """Add address to active cohort. User must restart runners to take effect."""
    cohort = load_cohort(cohort_path)
    cohort[address.lower()] = weight
    save_cohort(cohort, cohort_path)
    return {"approved": address.lower(), "weight": weight, "cohort_size": len(cohort)}


def reject(address: str, reject_path: Path = Path("data/cohort_rejected.json")) -> dict:
    """Mark address as rejected (won't be re-proposed)."""
    reject_path.parent.mkdir(parents=True, exist_ok=True)
    rejected = json.loads(reject_path.read_text()) if reject_path.exists() else []
    addr = address.lower()
    if addr not in rejected:
        rejected.append(addr)
        reject_path.write_text(json.dumps(rejected, indent=2))
    return {"rejected": addr, "total_rejected": len(rejected)}


def remove(address: str, cohort_path: Path = DEFAULT_COHORT_FILE) -> dict:
    """Remove address from active cohort. User must restart runners."""
    cohort = load_cohort(cohort_path)
    if address.lower() in cohort:
        del cohort[address.lower()]
        save_cohort(cohort, cohort_path)
        return {"removed": address.lower(), "cohort_size": len(cohort)}
    return {"error": f"{address} not in cohort"}
