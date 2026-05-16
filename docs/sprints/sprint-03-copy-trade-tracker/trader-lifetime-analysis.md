# Trader Lifetime Analysis (2026-05-17)

**Triggered by:** 0x492442EaB ("king") dormant 2+ days; we wondered if
this is normal pattern + whether king is genuinely skilled (backtest
attributed +81% of cohort PnL to them).

**Methodology:** user-pnl-api `interval=all fidelity=1d` for each of 4
active targets; analyzed lifetime cumulative PnL curve, recent 30d
delta, dormant streaks (>=3 consecutive days no pnl change) in last
6 months.

## Findings

| Trader | Wallet age | Days active | Start P | End P (today) | LIFETIME | Recent 30d | Dormant 3d+ streaks |
|---|---|---|---|---|---|---|---|
| **0x492442EaB (king)** | 2025-12-23 | 145 | -$3K | **-$1.56M** | **-$1.56M** | +$1.97M | **1** (Apr 17-19 + current) |
| **surfandturf** | 2026-04-03 | 44 | -$9K | +$3.93M | **+$3.94M** | +$3.75M | 0 |
| **LaBradfordSm** | 2026-04-24 | 23 | +$644K | +$3.19M | **+$2.55M** | +$2.55M | 0 |
| **swisstony** | 2025-08-10 | **280** | -$297 | +$8.12M | **+$8.12M** | +$2.25M | 0 |

## Key insights

**(a) King is the ONLY NET LOSER lifetime.** $-1.56M. Despite a recent
$2M rally (Apr 19 peak loss $-3.5M → today $-1.56M), still in red.
High-variance gambler profile.

**(b) swisstony is the GOAT.** 9+ months active, +$8.12M lifetime, never
dormant >=3 days in 6 months. Most reliable winner.

**(c) surfandturf & LaBradfordSm short but explosive.** Both started
recent (44 / 23 days) and are 100% positive trajectory.

**(d) Original weighting was BACKWARDS.** We had king at 0.01 (highest)
and swisstony at 0.005 (lowest). The actual reliability ranking was
opposite.

## Backtest with re-weighted cohort (king removed)

```
NEW WEIGHTS:
  surfandturf  0.01   (was 0.005, 2x up)
  LaBradfordSm 0.01   (unchanged)
  swisstony    0.015  (was 0.005, 3x up — GOAT)
  king         0      (was 0.01 — removed)
```

Backtest result on historical resolved trades (V2.3 aggregation, slip 5%):

| trader | records | copies | resolved | invested | PnL | ROI | Win% |
|---|---|---|---|---|---|---|---|
| surfandturf | 403 | 124 | 13 | $183 | +$43 | **+23.3%** | 100% |
| LaBradfordSm | 1362 | 604 | 156 | $1,510 | +$183 | **+12.1%** | 58.3% |
| **swisstony** | 1947 | 684 | 39 | $300 | +$122 | **+40.6%** | **89.7%** |
| **COHORT TOTAL** | | | 208 | **$1,994** | **+$347** | **+17.4%** | **66.8%** |

**Comparison vs old (king included):**
- Old cohort: +33.2% ROI, 57.2% win rate
- New cohort: **+17.4% ROI, 66.8% win rate**

Trade-off: half the ROI but **higher win rate + lower variance** (no
king's wild swings). Per-trader, swisstony's +40.6% on 39 resolved
trades is the most signal-rich data point.

## Action taken
1. Both paper runners restarted with new weights (king removed)
2. Forward V3 live execution will use king-removed cohort
3. Continue 24h paper monitoring; cross-validate against backtest
