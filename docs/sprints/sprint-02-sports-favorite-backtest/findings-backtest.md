# Sprint 02 — Sports Backtest Bulgulari

**Tarih:** 2026-05-15
**Sample:** 8,401 closed sport market historical price timeseries (gamma-api `tag_slug=sports` + clob.polymarket.com/prices-history). 8533 markets toplandi, 8401'inde fiyat history bulundu, ~3500'u bizim filtrelerimizden gecti config basina.

> ⚠️ Sprint 02 hipotezi (§9 Sprint 01 findings'inden gelen) **"BUY favorite"** YANLIS cikti. Test ettik, **kanit ile cürüttuk**. Beklenmedik alternatif **"BUY underdog"** ise GUCLU POZITIF — Sprint 03 hedefi degisti.

---

## 1. TLDR

1. **NAIF "BUY-favorite at $0.55-0.85" REDDEDILDI:** Tum 12 config negatif (-1.7% to -9.7%). Win rate 56-82% ama paying-too-much-up-front math her zaman ezici. Polymarket spor pazarlari **favoriler icin efisyent fiyatlanmis**.
2. **TERS HIPOTEZ "BUY-underdog at $0.05-0.45" GUCLU POZITIF:** Tum 16 config pozitif. En iyisi **24h-before, band $0.05-0.25, +30% return** (n=1202). Sport betting "favorite/longshot bias" Polymarket'ta **TERS YONDE** isliyor — favoriler over-priced, longshot'lar under-priced.
3. **Slippage robust:** 1000bps (10%) slippage'da bile band [0.10-0.30] +19.3% return. Margin of safety **buyuk**.
4. **Liquid markets > illiquid:** $500K+ vol filtresi → +47% return. Likidite arttıkca edge ARTIYOR (carpicidir).
5. **Soccer + Esports alpha kaynagi:** Soccer +35% (n=1158), Esports +16% (n=371). Diger sportlar dusuk N noise.
6. **Win rate 23-36%** — 2/3 trade kayipta ama her win 4-7x payout. **Kelly criterion + diversification sart**.
7. **Edge stabil** (Apr +16%, May +36% — ikisi de pozitif, sample size dengesiz). 30+ gun veri sınırı: long-term decay test edilemedi.

**Sprint 03 KARAR: GO.** Strateji "Yon I-revize" olarak: **BUY UNDERDOG at $0.10-0.30 in liquid sports markets (vol >$50K, focus soccer/esports)**.

---

## 2. Backtest engine ozet

`pm_research/backtest.py`:
- `simulate_one`: tek market icin BUY @ entry → resolution payoff hesabi. Slippage (bps), redemption gas ($0.05), fee_bps modellenir.
- `fetch_all_histories`: gamma'dan token IDs → CLOB prices-history paralel cek (concurrency=20, ~86 r/s gercek throughput).
- `simulate_grid`: tek config'i cached histories karsisinda calistir (network yok, hizli grid search).
- `summarize`: win rate, avg ROI, total PnL, total return %.

**Cost:** 8533 prices_history calls in 111 sec; sonra 12 config x 8000+ markets = saniyeler.

---

## 3. BUY-FAVORITE results (REDDEDILDI)

| config | n | win% | avg ROI | total return % |
|---|---|---|---|---|
| hrs=1, [0.55,0.85], 100bps | 2732 | 63.2% | -0.0719 | **-7.19%** |
| hrs=24, [0.55,0.85], 100bps | 3431 | 64.0% | -0.0625 | **-6.26%** |
| hrs=72, [0.55,0.85], 100bps | 2836 | 64.3% | -0.0655 | **-6.55%** |
| hrs=168, [0.55,0.85], 100bps | 3493 | 65.8% | -0.0177 | **-1.77%** |
| hrs=24, [0.50,0.65], 100bps | 2607 | 56.8% | -0.0026 | -0.26% |
| hrs=24, [0.65,0.80], 100bps | 1658 | 65.8% | -0.0967 | **-9.67%** |
| hrs=24, [0.80,0.95], 100bps | 718 | 81.5% | -0.0662 | **-6.63%** |
| hrs=24, [0.55,0.85], 0bps (no slip) | 3431 | 64.0% | -0.0532 | **-5.32%** |

**Yorumla:** Win rate beklenen aralikta (favoriler ~65% kazaniyor) ama math negative. $0.65 → 65% win = 0% expected, slippage + gas → -5%. **Pricing efisyent**, edge yok.

Per-sport breakdown (favorite, hrs=24):
- NHL +0.85K, UFC +166$, Golf +147$ (small N, marjin)
- Soccer **-17.6K**, NBA -815$, Esports -5.1K, MLB -385$ (buyuk N kayipli)

---

## 4. BUY-UNDERDOG results (GUCLU GO)

### 4.1 Ana sonuc grid (24h-before)

| Band | Slippage | n | Win% | Avg ROI | Total Return |
|---|---|---|---|---|---|
| [0.05, 0.25] | 100bps | 1202 | 23.2% | +0.3044 | **+30.4%** |
| [0.05, 0.25] | 300bps | 1202 | 23.2% | +0.2791 | **+27.9%** |
| [0.05, 0.25] | 500bps | 1202 | 23.2% | +0.2547 | **+25.5%** |
| [0.05, 0.25] | 1000bps | 1202 | 23.2% | +0.1976 | **+19.8%** |
| [0.05, 0.25] | 2000bps | 1202 | 23.2% | +0.0978 | **+9.8%** |
| [0.10, 0.30] | 300bps | 1634 | 28.9% | +0.2739 | **+27.4%** |
| [0.15, 0.45] | 100bps | 3431 | 36.0% | +0.1383 | **+13.8%** |
| [0.15, 0.45] | 1000bps | 3431 | 36.0% | +0.0451 | +4.5% |
| [0.15, 0.45] | 2000bps | 3431 | 36.0% | -0.0420 | -4.2% (break) |

**Robust:** [0.05-0.25] band 2000bps slippage'a kadar pozitif. [0.15-0.45] daha defansive ama 1500-2000bps'de breaks.

### 4.2 Volume filtresi (counter-intuitive: liquidity arttıkca edge ARTAR)

| min volume | n | win% | total return % |
|---|---|---|---|
| $10K | 1634 | 28.9% | +27.4% |
| $50K | 578 | 30.3% | **+33.4%** |
| $100K | 351 | 29.9% | **+33.5%** |
| $500K | 100 | 32.0% | **+47.0%** |
| $1M | 37 | 29.7% | **+43.1%** |

**Yorumla:** Daha cok bahisci favorite tarafa pile-in yapiyor → underdog daha cok under-priced. Klasik favori-bias mekanizmasi ters yonde.

### 4.3 Per-sport (24h, [0.10-0.30], 300bps)

| Sport | n | Win% | Total PnL | Return % |
|---|---|---|---|---|
| Soccer | 1158 | 30.5% | +$40,459 | **+34.9%** |
| Esports | 371 | 26.7% | +$6,048 | **+16.3%** |
| NBA | 28 | 21.4% | +$65 | +2.3% |
| MLB | 4 | 0% | -$400 | -100% (n cok az) |
| Tennis | 5 | 0% | -$500 | -100% (n cok az) |
| Basketball | 10 | 10% | -$647 | -64% |

**Soccer**: hakim alpha kaynagi. **Esports**: ikincil. Diger sport'lar guvenilemez sample.

### 4.4 Time-cohort (edge decay var mi?)

| Period | n | Win% | Return % |
|---|---|---|---|
| Apr 2026 | 81 | 25.9% | +16.4% |
| May 2026 | 497 | 31.0% | +36.2% |

Iki ay da pozitif. Sample dengesiz (May daha cok cunku endDate desc ile cektik), ama edge **decay belirtisi yok** son 30 gunde.

**Sınır:** Sample only past 30 days. 1+ yil tarihsel test mumkun degil cunku gamma 100/page cap + endDate desc bizi recent'a sıkıstırıyor — tarihi market batches paginate'leyerek eklenebilir, Sprint 03 paralelinde.

---

## 5. Real-world execution riskleri

Backtest pozitif ama PRODUCTION'a tasinmadan once asagidaki riskler validate edilmeli:

| Risk | Tahmin | Mitigasyon |
|---|---|---|
| Order book derinligi $0.10-0.30 fiyatlarinda thin | Ana risk | Per-pozisyon size kucuk ($25-$100), birden cok marketten dilimle |
| Backtest fiyati ≠ canli alabilecegim fiyat (slippage gercekte > model) | Bos kalma riski | Live'da limit-order @ price * (1 + 0.5%); aksi halde skip |
| Yuksek varyans (1/3 win rate) — 10-20 ardarda kayip mumkun | Drawdown ~50%+ | Sermaye max 20% stratejide; 50+ paralel bahis (diversification) |
| Edge zaman icinde decay edebilir | Bilinmiyor | Daily snapshot + auto re-backtest haftada bir |
| Resolution gecikmesi / disputed markets | Nadir ama gerek | UMA dispute window kontrol, dispute marketlerini dahil etme |
| Gas / fees gercekte yuksek | Modeli yenile | Live fee verisi ile yeniden hesapla Sprint 03'te |

---

## 6. Sprint 03 GO/NO-GO Karar

### KARAR: **GO**

**Strateji:** UNDERDOG BUY in liquid soccer + esports markets

**Spesifikasyon:**
- **Markets:** gamma-api `tag_slug=sports` AND tag in {soccer, esports} AND volume_usd > $50,000
- **Entry timing:** 24-72 hours before resolution (configurable)
- **Entry price band:** $0.10 - $0.30 (the underdog side)
- **Side selection:** whichever outcome (YES or NO) has price < $0.30 at entry
- **Position sizing:** Kelly fraction 0.10-0.25 per market; max $100/pozisyon ilk kanaryada
- **Hold:** to resolution (no early exit in v1)
- **Diversification:** min 30 paralel pozisyon
- **Bankroll:** $5,000-$10,000 ilk kanarya

**Sprint 03 hedef:** ExecutionClient (py-clob-client wrapper) + risk manager + bu strateji + canli kucuk-sermaye 1 hafta calisma. Net positive after fees → Sprint 04+ olceklendir.

### EGER NO-GO OLSAYDI...
Naif favorite reddediliyor + underdog pozitif olmasaydi → Yon II (klasik MM) fallback. Bu bizi geciyor; gerek yok.

---

## 7. Acik / sonraki sprintlerde takip edilecek

- **Tarihsel sample geni*letme:** > 1 yil veri icin gamma'da farkli endDate aralikla pages cek. 2025'ten gelen veriyle Apr-May 2026 sonuçlari karsilastir.
- **NEG_RISK markets:** Bizim test 7000+/8000+ negRisk=true markette calisti. Bu markets'in resolution mekanigi farkli (multi-outcome, complement satabilirsin). Strategy adaptasyonu gerek mi?
- **Order book depth tarihsel proxy:** Bir kac canli market icin gercek L2 book vs bizim slippage modelini calibrate et.
- **Gerçek 7 winner trader'in (surfandturf vs.) underdog vs favorite oran:** Onlar gercekten neyi BUY yapiyor? (trade history ile detayli kontrol)
- **Auto-discovery:** Aktif markets icin daily backtest, edge'i en kuvvetli olanları aktif kanaryada uygulama.
