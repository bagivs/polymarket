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

from . import (
    copy_runner,
    copy_strategy,
    discover,
    enrich as enrich_mod,
    metrics,
    profile,
    risk as risk_mod,
    scan as scan_mod,
    tracker as tracker_mod,
    validate as validate_mod,
)
from . import executor as executor_mod

DEFAULT_LB_DIR = Path("data/leaderboard")
DEFAULT_TRADERS_DIR = Path("data/traders")
DEFAULT_VALIDATE_DIR = Path("data/validation")


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

    sc = sub.add_parser(
        "scan",
        help="Full continuous discovery: lb-api + global active scan + user-pnl enrich + cohort",
    )
    sc.add_argument("--out-dir", type=Path, default=Path("data/scans"))
    sc.add_argument("--lb-limit", type=int, default=50)
    sc.add_argument("--global-pages", type=int, default=7)
    sc.add_argument("--top-active", type=int, default=100)

    ee = sub.add_parser(
        "enrich",
        help="Enrich latest candidates with true period PnL (user-pnl-api) and re-cohort",
    )
    ee.add_argument("--candidates", type=Path,
                    help="Candidates parquet (default: latest under data/leaderboard)")
    ee.add_argument("--lb-dir", type=Path, default=DEFAULT_LB_DIR)
    ee.add_argument("--out", type=Path,
                    help="Output parquet path (default: <date>_candidates_v2.parquet next to input)")

    tt = sub.add_parser(
        "track",
        help="Read-only copy-trade tracker — poll target addresses and log new trades",
    )
    tt.add_argument("--addresses", nargs="+", required=False)
    tt.add_argument("--poll", type=int, default=5, help="poll interval seconds")
    tt.add_argument("--log-dir", default="data/tracker")
    tt.add_argument("--iterations", type=int, default=None,
                    help="N polls then stop (default: run forever)")

    pf = sub.add_parser(
        "preflight",
        help="Test live-execution setup (auth, balance, allowance) WITHOUT placing orders.",
    )
    pf.add_argument("--sig-type", type=int, default=2,
                    help="signature_type: 0=EOA, 1=POLY_PROXY, 2=POLY_GNOSIS_SAFE (default 2)")

    aa = sub.add_parser(
        "set-allowance",
        help="One-time: approve the CTF exchange to spend our USDC.",
    )
    aa.add_argument("--sig-type", type=int, default=2)

    cp = sub.add_parser(
        "copy",
        help="Run the copy-trade strategy (paper mode unless --live).",
    )
    cp.add_argument(
        "--targets", nargs="+", required=True,
        help="addr:weight pairs, e.g. 0xabc:0.01 0xdef:0.005 — weight is fraction of their size",
    )
    cp.add_argument("--poll", type=int, default=5)
    cp.add_argument("--log-dir", default="data/copy")
    cp.add_argument("--iterations", type=int, default=None)
    cp.add_argument("--max-trade-usd", type=float, default=50.0)
    cp.add_argument("--min-trade-usd", type=float, default=1.0,
                    help="skip copies smaller than this (Polymarket markets enforce orderMinSize $5+)")
    cp.add_argument("--max-slippage", type=float, default=0.05)
    cp.add_argument("--skip-underdog-below", type=float, default=None,
                    help="skip copies where their_price < this (e.g. 0.45)")
    cp.add_argument("--aggregate-window-sec", type=int, default=30,
                    help="V2.3 cross-poll aggregator: force emit after N seconds")
    cp.add_argument("--aggregate-quiet-sec", type=int, default=5,
                    help="V2.3 cross-poll aggregator: emit if no new fill for N seconds")
    cp.add_argument("--max-gross-open", type=float, default=200.0)
    cp.add_argument("--max-per-target-open", type=float, default=100.0)
    cp.add_argument("--max-daily-loss", type=float, default=50.0)
    cp.add_argument("--max-copies-min", type=int, default=10)
    cp.add_argument("--max-copies-hour", type=int, default=100)
    cp.add_argument("--live", action="store_true",
                    help="Submit real orders (requires py-clob-client + .env credentials).")

    vv = sub.add_parser(
        "validate",
        help="Reconcile lb-api per-period P&L against trade + redemption cashflow.",
    )
    vv.add_argument("--addresses", nargs="*")
    vv.add_argument("--cohort", type=str)
    vv.add_argument("--top", type=int, default=10)
    vv.add_argument("--candidates", type=Path)
    vv.add_argument("--lb-dir", type=Path, default=DEFAULT_LB_DIR)
    vv.add_argument("--traders-dir", type=Path, default=DEFAULT_TRADERS_DIR,
                    help="Reuse trades.parquet from this dir if present")
    vv.add_argument("--out", type=Path, default=DEFAULT_VALIDATE_DIR)
    vv.add_argument("--max-pages", type=int, default=7)

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

    if args.cmd == "scan":
        summary = asyncio.run(scan_mod.run_scan(
            out_dir=args.out_dir,
            lb_limit=args.lb_limit,
            global_scan_pages=args.global_pages,
            top_active_addresses=args.top_active,
        ))
        print(json.dumps(summary, indent=2, default=str))
        return 0

    if args.cmd == "enrich":
        cands = args.candidates or _latest_candidates(args.lb_dir)
        summary = asyncio.run(enrich_mod.enrich(cands, out_path=args.out))
        print(json.dumps(summary, indent=2, default=str))
        return 0

    if args.cmd == "track":
        addrs = args.addresses or []
        if not addrs:
            print(json.dumps({"error": "no addresses given"}, indent=2))
            return 2
        asyncio.run(tracker_mod.track(
            addrs,
            poll_interval_sec=args.poll,
            log_dir=Path(args.log_dir),
            iterations=args.iterations,
        ))
        return 0

    if args.cmd == "preflight":
        cfg = executor_mod.config_from_env()
        cfg = executor_mod.ExecutorConfig(**{**cfg.__dict__, "signature_type": args.sig_type})
        ex = executor_mod.Executor(cfg)
        result = ex.preflight()
        print(json.dumps(result, indent=2, default=str))
        return 0 if not result["errors"] and result["l1_auth"] == "ok" and result["l2_auth"] == "ok" else 1

    if args.cmd == "set-allowance":
        cfg = executor_mod.config_from_env()
        cfg = executor_mod.ExecutorConfig(**{**cfg.__dict__, "signature_type": args.sig_type})
        ex = executor_mod.Executor(cfg)
        try:
            result = ex.set_usdc_allowance()
            print(json.dumps({"status": "submitted", "result": str(result)}, indent=2))
            return 0
        except Exception as exc:
            print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
            return 1

    if args.cmd == "copy":
        targets: dict[str, float] = {}
        addrs: list[str] = []
        for pair in args.targets:
            if ":" not in pair:
                print(f"bad target spec '{pair}', expected addr:weight", file=sys.stderr)
                return 2
            a, w = pair.split(":", 1)
            a = a.lower()
            targets[a] = float(w)
            addrs.append(a)
        cfg = copy_strategy.CopyConfig(
            targets=targets,
            max_size_per_trade_usd=args.max_trade_usd,
            min_size_per_trade_usd=args.min_trade_usd,
            max_slippage_pct=args.max_slippage,
            skip_underdog_below=args.skip_underdog_below,
        )
        limits = risk_mod.RiskLimits(
            max_gross_open_usd=args.max_gross_open,
            max_per_target_open_usd=args.max_per_target_open,
            max_daily_realized_loss_usd=args.max_daily_loss,
            max_copies_per_minute=args.max_copies_min,
            max_copies_per_hour=args.max_copies_hour,
        )
        executor = None
        if args.live:
            ex_cfg = executor_mod.config_from_env()
            executor = executor_mod.Executor(ex_cfg)
            pre = executor.preflight()
            if pre["l1_auth"] != "ok" or pre["l2_auth"] != "ok":
                print(json.dumps({"error": "preflight failed", "preflight": pre}, indent=2))
                return 2
            print(f"# LIVE mode confirmed; balance={pre['usdc_balance']}", file=sys.stderr)
        asyncio.run(copy_runner.run(
            addrs, cfg, limits,
            poll_interval_sec=args.poll,
            log_dir=Path(args.log_dir),
            iterations=args.iterations,
            live=args.live,
            executor=executor,
            aggregate_max_sec=args.aggregate_window_sec,
            aggregate_quiet_sec=args.aggregate_quiet_sec,
        ))
        return 0

    if args.cmd == "validate":
        if args.addresses:
            addresses = [a.lower() for a in args.addresses]
        else:
            cands_path = args.candidates or _latest_candidates(args.lb_dir)
            addresses, _ = _pick_addresses(cands_path, args.cohort, None, args.top)
        if not addresses:
            print(json.dumps({"error": "no addresses"}, indent=2))
            return 2
        print(f"# validating {len(addresses)} addresses", file=sys.stderr)
        rows = asyncio.run(
            validate_mod.validate_addresses(
                addresses,
                traders_dir=args.traders_dir,
                max_pages=args.max_pages,
            )
        )
        args.out.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        out_path = args.out / f"{today}_validation.parquet"
        if rows:
            pl.DataFrame(rows).write_parquet(out_path)
        summary = {
            "addresses": addresses,
            "rows": len(rows),
            "out": str(out_path),
        }
        print(json.dumps(summary, indent=2, default=str))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
