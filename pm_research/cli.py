"""Command-line entry: `uv run python -m pm_research <subcommand>`."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from . import discover

DEFAULT_DATA = Path("data/leaderboard")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="pm_research")
    p.add_argument("--log-level", default="INFO")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover", help="Pull leaderboards, label cohorts, save Parquet")
    d.add_argument(
        "--limit",
        type=int,
        default=50,
        help="top-N per leaderboard (lb-api hard-caps at 50; higher values are silently truncated)",
    )
    d.add_argument("--out", type=Path, default=DEFAULT_DATA)

    args = p.parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.cmd == "discover":
        summary = asyncio.run(discover.run(args.out, limit=args.limit))
        print(json.dumps(summary, indent=2, default=str))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
