#!/usr/bin/env bash
# Continuous trader discovery — installed via crontab.
# Run hourly: scans lb-api + global active, enriches with user-pnl-api,
# writes data/scans/<YYYYMMDD_HHMM>_candidates.parquet for trend analysis.
#
# Install:
#   crontab -e
#   # add: 0 * * * * /home/bagi/PlayGround/BOTS/Crypto/polymarket/scripts/cron-scan.sh
set -euo pipefail

REPO=/home/bagi/PlayGround/BOTS/Crypto/polymarket
cd "$REPO"

mkdir -p data/scans
LOG=data/scans/cron.log

{
  echo "=== $(date -u +'%Y-%m-%dT%H:%M:%SZ') scan start ==="
  /home/bagi/.local/bin/uv run python -m pm_research --log-level WARNING scan 2>&1 | tail -10
  echo "=== $(date -u +'%Y-%m-%dT%H:%M:%SZ') scan end ==="
  echo
} >> "$LOG" 2>&1

# Keep last 30 days of scan parquets, archive older
find data/scans -name '2026*_candidates.parquet' -mtime +30 -exec mv {} data/scans/archive/ \; 2>/dev/null || true
