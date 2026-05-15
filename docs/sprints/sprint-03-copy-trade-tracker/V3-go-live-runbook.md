# Sprint 03 V3 — Go Live Runbook

**Tarih:** 2026-05-16
**Status:** Hazir, kullanici tetigine bagli.

> Tum kod yazildi + paper-mode test edildi + backtest +33% ROI gosterdi (`findings-v2-backtest.md`). Bu dokuman, **0** -> **canli ilk emir**'e gecis adimlarini iceriyor. Kullanici her adimi tek tek calistirir; otomatik gecis YOK.

---

## On-kontrol (yapilanlar)

| Bilesen | Durum | Komut/Dosya |
|---|---|---|
| `executor.py` (py-clob-client wrapper) | ✅ Yazildi | `pm_research/executor.py` |
| `preflight` CLI | ✅ Yazildi + test edildi | `uv run python -m pm_research preflight` |
| `set-allowance` CLI | ✅ Yazildi | `uv run python -m pm_research set-allowance` |
| `copy --live` flag | ✅ Wired (executor → post_buy) | `pm_research/copy_runner.py` |
| RiskGuard | ✅ Aktif (gross/per-target/daily-loss/rate caps) | `pm_research/risk.py` |
| Aggregation V2.2 | ✅ Aktif (in-poll same-position fills birlestirir) | `pm_research/copy_runner.py` |
| `--skip-underdog-below` filter | ✅ Aktif (backtest +5% bucket'i atlamak icin) | `pm_research/copy_strategy.py` |
| Dedup bug fix | ✅ Fixed (set→dict, cap 500→100K) | 2026-05-16 fix |
| Last preflight result | L1+L2 OK, sig=2, balance=0, allowance=null | Need deposit + allowance |

---

## V3 Acilis: 5 Adim

### Adim 1 — USDC deposit (Polygon network)

Polymarket proxy cuzdan adresi:
```
0x3878fc58633e44fd371ac3db4186bf9a0b60e5b5
```

Buraya **USDC native (Polygon mainnet)** gonder.
- Token contract: `0x3c499c542cef5e3811e1192ce70d8cc03d5c3359`
- **Network: Polygon (chain ID 137)**, Ethereum mainnet'e degil!
- Onerilen miktar: **$300-500** ilk kanarya icin (V3.1'de scale-up)

Ek olarak biraz MATIC lazim gas icin (~$1-2; relay cuzdan'da zaten $2.6 var, ek gerek yok genelde).

### Adim 2 — Re-preflight (deposit dogrulamasi)

```bash
uv run python -m pm_research preflight
```

Beklenen: `usdc_balance` > 0 (6 decimal: 300 USDC = 300000000).

### Adim 3 — Set allowance (one-time)

```bash
uv run python -m pm_research set-allowance
```

CTF Exchange contract'ina USDC harcama yetkisi verir. ~$0.05 gas, sadece bir kere.

### Adim 4 — Re-preflight (allowance dogrulamasi)

```bash
uv run python -m pm_research preflight
```

`usdc_allowance` buyuk sayi → live ready.

### Adim 5 — Live canary baslat

```bash
kill $(cat data/copy/copy.pid) 2>/dev/null

mkdir -p data/copy && nohup uv run python -m pm_research --log-level INFO copy \
  --targets 0x492442eab586f242b53bda933fd5de859c8a3782:0.005 \
            0x9495425feeb0c250accb89275c97587011b19a27:0.005 \
            0x204f72f35326db932158cba6adff0b9a1da95e14:0.0025 \
  --max-trade-usd 10 --min-trade-usd 1 \
  --max-gross-open 50 --max-per-target-open 25 --max-daily-loss 25 \
  --max-copies-min 3 --max-copies-hour 30 \
  --skip-underdog-below 0.45 \
  --log-dir data/copy --live > data/copy/copy.log 2>&1 &
echo $! > data/copy/copy.pid
```

**Kanarya ayarlari:**
- weights 0.005-0.0025 (paper'dan duşurduk)
- max-trade-usd $10 (paper $50)
- max-gross-open $50 (paper $200)
- max-per-target-open $25 (paper $100)
- max-daily-loss $25 → kill switch
- max-copies-min 3, max-copies-hour 30 → rate limit
- surfandturf cıkarildi (sample n=12 cok az)

### Adim 6 — Izleme

```bash
tail -f data/copy/copy.log | grep --line-buffered "LIVE-order\|risk-block\|halt\|NEW trades\|ERROR"
```

Olaylar:
- `[LIVE-order:submitted]` — gercek emir verildi
- `[LIVE-order:error]` — emir basarisiz
- `[risk-block]` — RiskGuard durdurdu
- `halted: ...` — daily loss cap asildi

Durdur: `kill $(cat data/copy/copy.pid)`

Acik pozisyon: `cat data/copy/risk_state.json | python3 -m json.tool`

---

## Beklenen davranis (ilk 24-48h)

1. Detection: 5sn poll, 3 trader, ~3 r/s data-api
2. Aggregation: burst-fill'ler tek decision'a duser
3. Decide: weight × size, $10 cap, slip 5%, underdog skip
4. Risk: per-target $25, gross $50, daily -$25 = halt
5. Execute: `clob.polymarket.com` POST order, fill <5s tipik
6. Resolve: Polymarket otomatik redeem

**Tahmin (backtest extrapolasyonu):**
- Gunde ~5-15 live order
- Toplam acik anlik: $20-50 USDC
- Aylik turnover ~$500-1000
- Aylik PnL +$100-300 (eger backtest ROI tutarsa)

---

## NE YAPMA

- ❌ `--max-trade-usd` 50 ustune cıkartma ilk hafta
- ❌ Cuzdana $500'den fazla deposit etme yenilenmeden
- ❌ NBA aktif sezon disinda 0x492442EaB beklemeden cohort genisletme
- ❌ Live mod'da risk_state.json'i el ile silme

---

## Acil durum protokolu

### "Pozisyon stuck, fill olmuyor"
1. `kill $(cat data/copy/copy.pid)`
2. Polymarket UI → cancel pending orders
3. Log'lardaki son 10 LIVE-order error'una bak
4. Genellikle: book derinligi yetersiz veya allowance expired

### "Halt switch tetiklendi"
1. `tail -50 data/copy/copy.log | grep -i halt`
2. risk_state.json: `realized_pnl_today` ve `halt_reason` oku
3. Karar ver — yeniden baslat veya bir-iki gun durdur

### "Process oluyor olmadan deposit'i bos"
1. Log'da "balance=0 in preflight" → deposit henuz on-chain confirm degil
2. Polygonscan'de tx kontrol et
3. Confirm sonrasi runner otomatik devam, manuel mudahale gerek yok

---

## Pozitif/Negatif sinyaller (V3.1 karar)

**Negatif (kill-switch tetik):**
- LIVE-error > %20
- 7-gun realized PnL net negative
- Kingimiz hala dormant (>%50 zaman)

**Pozitif (V3.1 scale-up):**
- 7-gun realized PnL > +5%
- Decision rate %20+
- Lag distribution stabil
- → Bankroll $300 → $1000, weights 2x, max-trade $25
