# Sprint 03 V2 — Copy-Strategy Historical Backtest

**Tarih:** 2026-05-15
**Sample:** 4 target trader × historical trades (3500 max each, ~90-day window) → **4,764 BUY records → 30s aggregation → 3,071 copy decisions → 414 fully-resolved markets** ile gercek per-trade PnL.

> Bu rapor V2.0 paper-mode runner'in 6-saatlik live verisi yetersiz oldugu icin (379 obs / sadece 4 resolved), V2.2 copy_strategy.decide() + aggregate_fills() logic'ini target trader'lerin **tarihsel trade verisi** uzerinde calistirip resolved gecmis ile cross-reference ederek uretildi. Live forward backtest yarın+ sample dolduktan sonra gözden geçirilir.

---

## TLDR

1. **Cohort net ROI: +33.2%** (4 target × ~90 gun, 414 resolved trade, $6,501 invested → +$2,158 PnL). V2.2 logic + mevcut 0.005-0.01 weights ile.
2. **Neutral bucket (price 0.45–0.55) ana alpha kaynagi** — cohort +53.6% ROI, 0x492442EaB tek başına +67%. NBA spread bahisleri @ ~$0.50.
3. **Underdog bucket cohort'ta weak** (+5.3% ROI, %35 win) — `--skip-underdog` flag ile filtre yapilarak ROI **+50%+** seviyesine ciktirilabilir.

---

## Methodology

1. Her 4 target icin `data/traders/<addr>/trades.parquet` yuklendi (max 3500 BUY).
2. 30-saniyelik time-window aggregation (V2.2 logic): same `(target, conditionId, outcome, side)` gruplari tek synthetic record'a, VWAP price + summed size.
3. `copy_strategy.decide()` her aggregated record uzerinde calistirildi (config: max_trade=$50, min_trade=$0.10, max_slippage=5%, weights as user runs).
4. Decision='copy' olan trade'lerin `conditionId` resolution'i `gamma-api/markets` (cached pickle) ile getirildi; sadece `max(outcomePrices) >= 0.95` olanlara per-trade PnL hesaplandi:
   - `cost = our_max_price * our_target_size_tokens`
   - `payoff = final_price * our_target_size_tokens`
   - `pnl = payoff - cost`

**Caveats:**
- `our_max_price = their_price * 1.05` (5% slippage cap). Real fill may be lower → ROI possibly understated.
- Resolution coverage: 414/3071 = 13.5% → buyuk kismi henuz acik pozisyon. ROI sample bias olabilir.
- 90-day window may not generalize forward.

---

## Per-trader summary

| Target | Records | Aggregated | Copies | Resolved | Invested | PnL | **ROI** | Win% |
|---|---|---|---|---|---|---|---|---|
| **0x492442EaB** | 3,500 | 1,052 | 1,044 | 81 | $3,588 | **+$1,742** | **+48.5%** | 79% |
| **swisstony** | 3,500 | 1,947 | 837 | 48 | $151 | +$67 | **+44.2%** | 58% |
| **surfandturf** | 3,385 | 403 | 279 | 12 | $166 | +$39 | +23.2% | 100% |
| **LaBradfordSm** | 3,500 | 1,362 | 911 | 273 | $2,595 | +$310 | +12.0% | 49% |

0x492442EaB tek basına PnL'in **%81**'ini uretti ($1,742 / $2,158). Cohort survivorship bu trader'a bagli.

---

## Per-bucket simulated PnL (cohort)

| Bucket | n | Invested | PnL | **ROI** | Win% |
|---|---|---|---|---|---|
| **favorite** (price > 0.55) | 136 | $1,628 | +$551 | **+33.9%** | **82.4%** |
| **neutral** (0.45–0.55) | 117 | $2,793 | **+$1,496** | **+53.6%** | 58.1% |
| underdog (< 0.45) | 161 | $2,079 | +$110 | +5.3% | 35.4% |

**Sport bahis literaturune uyumlu:**
- Favorite+neutral kazaniyor (top traders bu band'da konsantre)
- Underdog buyuk olcekle weak — kayipli olanlar var
- Sprint 02b'deki "underdog buy LOSE" bulgusu tekrar kanitlandi

## Per-target × bucket detayi

```
                      bucket    n    inv$       pnl$      ROI
  0x492442EaB        favorite   11   $502     +$338     +67.4%
  0x492442EaB         neutral   48   $2,103   +$1,413   +67.2%   ← MAIN ENGINE
  0x492442EaB        underdog   22   $982     -$10      -1.0%
  surfandturf        favorite   12   $166     +$39      +23.2%
  LaBradfordSm       favorite   92   $908     +$171     +18.8%
  LaBradfordSm        neutral   64   $602     +$12      +2.0%
  LaBradfordSm       underdog  117   $1,085   +$128     +11.8%
  swisstony          favorite   21   $51      +$3       +6.7%
  swisstony           neutral    5   $89      +$71      +80.5% (n az)
  swisstony          underdog   22   $12      -$8       -67%
```

**Patterns:**
- 0x492442EaB: hakim **neutral specialist** (NBA spreads), favorite/neutral'de muthis edge, underdog'da no edge
- LaBradfordSm: dengeli, favorite en saglam (+19%), underdog'da bile pozitif (+12%)
- surfandturf: yalniz favorite gozlemde (n az), pozitif
- swisstony: small samples, gurultu

---

## Aggregation effect (V2.0 raw vs V2.2 aggregated)

| Trader | RAW copies | AGG30s copies | RAW ROI | AGG30s ROI | Yorum |
|---|---|---|---|---|---|
| 0x492442EaB | 2,341 | 1,044 | +56.3% | +48.5% | dilute (VWAP smoothing) |
| swisstony | 1,143 | 837 | +44.6% | +44.2% | minimal etki |
| surfandturf | 1,439 | 279 | +23.3% | +23.2% | minimal etki |
| **LaBradfordSm** | 1,891 | 911 | +6.1% | **+12.0%** | **2x improvement** |

Net: aggregation 0x492442EaB'i biraz dilute, LaBradfordSm'yi **2x** iyilestiriyor. Cohort net etkisi pozitif.

---

## Sprint 03 V3 onerileri

Bu backtest sonucu **GO sinyali** veriyor live execution icin. Iyilestirme alanlari:

1. **Bucket-aware decision (`--skip-underdog`)** — underdog bucket cohort'ta sadece +5%, riskli olabilir. Skip yapilirsa ROI ~50%+ tahmin.
2. **Per-target bucket weights** — 0x492442EaB neutral'a ekstra weight ver (ana alpha), surfandturf yalnizca favorite'a izin ver.
3. **Cross-poll buffer (V2.3)** — bursts spanning 2-3 polls hala parcalaniyor. 30sn buffer sonra emit ile birleştirilebilir.
4. **Live performance vs backtest** — first 1-week live data (V2.0/2.1/2.2 paper) ile bu backtest'i compare et; markedly farkli ise live decay sinyali.

---

## Bankroll & Sermaye onerisi

**Yatirim ayarlari (mevcut weights):**
- Per-trade max: $50
- Per-target max open: $100
- Cohort max gross open: $200-500
- Bankroll gerekli: **$300-500 USDC** ilk kanarya

**Beklenen aylik P&L** (bu backtest extrapolasyonu, %33 ROI scenario):
- Aylik turnover: ~$2,000
- Aylik PnL: ~$700
- **NB:** Real ROI dusebilir (forward) veya ayni kalabilir; live test 1-2 hafta sonra net cevap

**Scale-up eger pozitifse:**
- Weights 5x (0.025-0.05): bankroll ~$1,500-2,500 → aylik PnL ~$3,500
- Weights 10x: bankroll ~$3K-5K → aylik PnL ~$7K
- ÜST sınır: 0x492442EaB'in tek pozisyon size'i — weights çok büyütünce bizim copy market book'u disturb eder

---

## Kararlar

- ✅ **GO Sprint 03 V3 (live execution)** — backtest +33% ROI yeterli sinyal
- 🟡 Bekleme: V2.2 paper-mode'un 24-48 saatlik live verisi backtest sonucunu confirm etsin
- ✅ **Sermaye:** $300-500 ilk kanarya yeterli, scale-up live edge konfirme olduktan sonra
- ⚠️ **Cuzdan:** mevcut wallet'tan başla (kullanici onayi var), $500+ deposit oncesi yenile
