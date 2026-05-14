"""Command-line entry: `uv run python -m pm_research <subcommand>`."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import date
from pathlib import Path

import polars as pl

from . import discover, metrics, profile

DEFAULT_LB_DIR = Path("data/leaderboard")
DEFAULT_TRADERS_DIR = Path("data/traders")


def _latest_candidates(lb_dir: Path) -> Path:
    files = sorted(lb_dir.glob("*_candidates.parquet"))
    if not files:
        raise SystemExit(f"no candidates parquet under {lb_dir}; run `discover` first")
    return files[-1]


def _pick_addresses(
    candidates_path: Path,
    cohort: str | None,
    explicit: list[str] | None,
    top: int,
) -> tuple[list[str], pl.DataFrame]:
    df = pl.read_parquet(candidates_path)
    if explicit:
        sel = df.filter(pl.col("address").is_in([a.lower() for a in explicit]))
        return [a.lower() for a in explicit], sel
    if not cohort:
        raise SystemExit("--cohort or --addresses required")
    sub = df.filter(pl.col("cohort") == cohort)
    sort_col = "volume_month" if "market_maker" in cohort else "profit_year"
    if sort_col not in sub.columns:
        sort_col = sub.columns[-1]
    sub = sub.sort(sort_col, descending=True).head(top)
    return sub["address"].to_list(), sub


async def _run_profile(addresses: list[str], out_dir: Path, max_pages: int) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    bundles = await profile.collect_cohort(addresses, max_pages=max_pages)
    fps: list[dict] = []
    for b in bundles:
        addr = b["address"]
        d = out_dir / addr
        d.mkdir(parents=True, exist_ok=True)
        if b["trades"]:
            pl.DataFrame(b["trades"]).write_parquet(d / "trades.parquet")
        if b["closed_positions"]:
            pl.DataFrame(b["closed_positions"]).write_parquet(d / "closed_positions.parquet")
        if b["open_positions"]:
            pl.DataFrame(b["open_positions"]).write_parquet(d / "open_positions.parquet")
        fp = metrics.fingerprint(b)
        (d / "fingerprint.json").write_text(json.dumps(fp, indent=2))
        fps.append(fp)
    return fps


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="pm_research")
    p.add_argument("--log-level", default="INFO")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover", help="Pull leaderboards, label cohorts, save Parquet")
    d.add_argument("--limit", type=int, default=50,
                   help="top-N per leaderboard (lb-api hard-caps at 50)")
    d.add_argument("--out", type=Path, default=DEFAULT_LB_DIR)

    pp = sub.add_parser("profile", help="Deep-dive a cohort (or explicit addresses): fetch + fingerprint")
    pp.add_argument("--cohort", type=str,
                    help="Cohort label from candidates parquet (e.g. market_maker_candidate)")
    pp.add_argument("--addresses", nargs="*",
                    help="Explicit wallet addresses (overrides --cohort)")
    pp.add_argument("--top", type=int, default=5)
    pp.add_argument("--max-pages", type=int, default=10)
    pp.add_argument("--candidates", type=Path,
                    help="Candidates parquet (default: latest under data/leaderboard)")
    pp.add_argument("--lb-dir", type=Path, default=DEFAULT_LB_DIR)
    pp.add_argument("--out", type=Path, default=DEFAULT_TRADERS_DIR)

    args = p.parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.cmd == "discover":
        summary = asyncio.run(discover.run(args.out, limit=args.limit))
        print(json.dumps(summary, indent=2, default=str))
        return 0

    if args.cmd == "profile":
        cands_path = args.candidates or _latest_candidates(args.lb_dir)
        addresses, picked = _pick_addresses(cands_path, args.cohort, args.addresses, args.top)
        if not addresses:
            print(json.dumps({"error": "no addresses matched", "cohort": args.cohort}, indent=2))
            return 2
        print(f"# profiling {len(addresses)} addresses from {cands_path.name}", file=sys.stderr)
        fps = asyncio.run(_run_profile(addresses, args.out, args.max_pages))
        # Save aggregated fingerprints + cohort summary
        today = date.today().isoformat()
        tag = (args.cohort or "explicit").replace("/", "_")
        agg_path = args.out / f"_fingerprints_{today}_{tag}.parquet"
        agg = pl.DataFrame(fps) if fps else pl.DataFrame()
        if not agg.is_empty():
            agg.write_parquet(agg_path)
        summary = {
            "candidates_used": str(cands_path),
            "cohort": args.cohort,
            "addresses": addresses,
            "fingerprints_path": str(agg_path),
            "cohort_summary": metrics.cohort_summary(fps),
        }
        print(json.dumps(summary, indent=2, default=str))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
