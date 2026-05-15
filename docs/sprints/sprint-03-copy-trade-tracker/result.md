# Sprint 03 V1 — Copy-Trade Tracker — Sonuc

> Sprint **aktif**. 1 hafta calisma sonunda doldurulur.

## Yapilanlar
- [x] `pm_research/tracker.py` — async polling tracker (5s, restart-tolerant state, JSONL log)
- [x] CLI subcommand `track --addresses ... --poll N --log-dir DIR`
- [x] Smoke test (5 poll, 25 sec) — baseline 50 trades indexed, 0 yeni (sakin period)
- [x] [`winner-trade-lists.md`](winner-trade-lists.md) — top 10 sport + bonereaper'in son 30 trade'i + ozet
- [ ] **1 hafta arka plan calistirma** — kullanici baslatacak (asagidaki komut)

## Tracker'i baslatma

Foreground (test):
```bash
uv run python -m pm_research --log-level INFO track \
  --addresses 0x492442eab586f242b53bda933fd5de859c8a3782 \
  --poll 5 --log-dir data/tracker --iterations 60
```

Background (gercek 1 hafta):
```bash
nohup uv run python -m pm_research --log-level INFO track \
  --addresses 0x492442eab586f242b53bda933fd5de859c8a3782 \
              0x9f2fe025f84839ca81dd8e0338892605702d2ca8 \
              0x2005d16a84ceefa912d4e380cd32e7ff827875ea \
  --poll 5 --log-dir data/tracker > data/tracker/tracker.log 2>&1 &
echo $! > data/tracker/tracker.pid
```

Stop: `kill $(cat data/tracker/tracker.pid)`

## Hafta sonu yapilacaklar
- Logs: `data/tracker/trades_YYYYMMDD.jsonl` günlük dosyalar
- Aggregate: `data/tracker/state.json` ile tx_hash deduplication
- `findings-tracker-week1.md` raporu — kac trade detected, simulated copy-PnL, edge devam ediyor mu?

## Sapmalar
- (sprint sirasinda)

## V2 hazırlığı
- Eger V1 sonucu pozitif → V2: real execution layer (yeni cuzdan + py-clob-client + RiskGuard)
- Yakilan PRIVATE_KEY kullanilmaz, **yeni cuzdan** ZORUNLU (memory rule)

---

## V2.0 — paper-mode copy strategy (2026-05-15)
- `pm_research/copy_strategy.py` — pure decide() logic (skip rules + size scaling)
- `pm_research/risk.py` — RiskGuard (max gross/per-target, daily loss halt, copy rate limit)
- `pm_research/copy_runner.py` — wires tracker→decide→risk→executor; 3 log files per day
- CLI: `copy --targets addr:weight ... --max-trade-usd N --max-gross-open N --max-daily-loss N`
- Unit tests passed (7 decide cases + risk cap)
- Currently running in production (paper) by user

## V2.1 — live executor scaffold (2026-05-15)
- `uv add py-clob-client` → installed
- `pm_research/executor.py` — ClobClient wrapper with config from .env
- CLI subcommands:
  - `preflight --sig-type N` — auth + balance + allowance check (no orders)
  - `set-allowance --sig-type N` — one-time CTF exchange approval
- copy_runner now accepts `executor: Executor | None`; `--live` flag wires it in
- **Preflight verified GREEN:**
  - L1 + L2 auth OK
  - signature_type=2 (POLY_GNOSIS_SAFE) confirmed
  - funder = 0x3878fc58... (proxy wallet)
  - **USDC balance: 0** → deposit gerek
  - **Allowance: null** → set-allowance gerek

## Live moduna gecmek icin (kullanici tarafi)
1. **USDC deposit** to proxy wallet `0x3878fc58633e44fd371ac3db4186bf9a0b60e5b5`
   - $50–200 yeterli kanarya icin
   - Polygon network (USDC native), bridge from anywhere
2. **One-time allowance:**
   ```bash
   uv run python -m pm_research set-allowance
   ```
3. **Re-preflight** to confirm balance > 0 + allowance set:
   ```bash
   uv run python -m pm_research preflight
   ```
4. **Live canary:**
   ```bash
   kill $(cat data/copy/copy.pid) 2>/dev/null
   nohup uv run python -m pm_research --log-level INFO copy \
     --targets 0x492442eab586f242b53bda933fd5de859c8a3782:0.005 \
               0x9495425feeb0c250accb89275c97587011b19a27:0.005 \
     --max-trade-usd 10 --max-gross-open 50 --max-daily-loss 25 \
     --max-copies-min 3 --max-copies-hour 30 \
     --log-dir data/copy --live > data/copy/copy.log 2>&1 &
   echo $! > data/copy/copy.pid
   ```
   Konservatif kanarya: $10/trade, $50 toplam acik, $25/gun max kayip, 3/dk rate.
5. **Izleme:** `tail -f data/copy/copy.log | grep --line-buffered "LIVE-order\|risk-block\|NEW"`
