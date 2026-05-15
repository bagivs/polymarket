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
