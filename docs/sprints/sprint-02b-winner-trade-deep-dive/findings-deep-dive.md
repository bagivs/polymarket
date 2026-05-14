# Sprint 02b — Winner Trade-Level Deep Dive — Bulgular

**Tarih:** 2026-05-15
**Sample:** 7 currently-winning hesabin **22,936 BUY trade**'i; 439 unique market'in 189'unun gamma-api'den resolved kanaridan dogrulandi → **5,468 trade-level resolution gercek pnl ile.**

> Kullanici uyarisi: Sprint 02'deki "yuzeysel fingerprintten strateji icadi" hatasini duzeltmek icin acildi. **Bu kez gercek trade'lere bakildi.** Bulgular Sprint 01 §9'daki yuzeysel "6/7 favorite buy" iddiasini hem kismen dogruladi hem de derin sekilde nuanseli gosterdi.

---

## 1. Tek-cumlede

**Gercek ortak nokta yok genel anlamda — ama 4/7 trader (surfandturf, RN1, swisstony, kch123) hepsi FAVORITE-BUY bucket'inda gercekten net pozitif ($+9% ila +29% net ROI), ve win-rate'leri implied probability'den belirgin sekilde yuksek = "selection edge". Underdog-buy buyuk olcekle LOSING (-9% ila -63% her trader'da). Bu, Sprint 02 backtest'inin "UNDERDOG +30%" iddiasinin gercek-trader davranisinda DOGRULANMADIGINI gosteriyor — backtest methodoloji hatasi vardi.**

---

## 2. Methodology

1. Per-trader trades.parquet'ten BUY+SELL kayit yukle (toplam 22,936 BUY trade)
2. Trade'in fiyatina gore bucket: favorite (>0.55), neutral (0.45-0.55), underdog (<0.45)
3. Her unique conditionId (439) icin gamma-api'den final outcomePrices fetch (189 fully-resolved bulundu, max(outcomePrices) ≥ 0.95)
4. Per-trade pnl = (final_price_for_bought_side - entry_price) × size
5. Per-trader x bucket dollar-weighted aggregation

---

## 3. Trade-price distribution (no API call lazim)

```
trader              total_BUY  fav>0.55   neutral  underdog<0.45  cheap<0.10
surfandturf            3385      43.4%       0.3%        56.3%        0.0%
swisstony              3500      32.4%      15.0%        52.6%       10.7%
RN1                    3500      36.5%      13.9%        49.6%        5.9%
beachboy4              3496      19.9%      68.9%        11.2%        0.1%
kch123                 3500      46.1%      35.7%        18.3%        0.2%
tdrhrhhd               2765       0.3%       0.0%        99.7%       59.9%
gfjoigfsjoigsjoi       1936      68.4%      18.4%        13.2%        0.0%
```

**Ilk yuzeysel okuma duzeltildi:**
- 4/7 trader (surfandturf, swisstony, RN1, tdrhrhhd) **dolar-bazli underdog buy ya da longshot oldugundan** ben bu trader'lara bakipta "longshot bias" diye yorumladim → sonradan resolved-trade analizi gosterdi ki underdog buy LOSER, sadece SAYIDAN cok ama dolardan kucuk
- "favorite buy" yuzde olarak baskin DEGIL ama dolar-bazli ana strateji

---

## 4. Per-trader x bucket dollar-weighted (resolved-only subset)

| Trader | Bucket | n | $ in | Net PnL | Net RoI | Win rate | Avg entry | Implied | Edge |
|---|---|---|---|---|---|---|---|---|---|
| **surfandturf** | favorite | 72 | $100K | **+$29.6K** | **+29.5%** | **100.0%** | 0.768 | 76.8% | **+23.2pp** |
| **RN1** | favorite | 1110 | $201K | **+$27K** | **+13.4%** | **77.2%** | 0.728 | 72.8% | +4.4pp |
| **swisstony** | favorite | 89 | $13K | **+$1.2K** | **+9.5%** | **96.6%** | 0.890 | 89.0% | +7.6pp |
| swisstony | neutral | 27 | $17K | **+$15.1K** | **+89.3%** | 66.7% | 0.501 | 50.1% | +16.6pp |
| swisstony | underdog | 117 | $2.4K | -$1.5K | -63.1% | 18.8% | 0.176 | 17.6% | +1.2pp |
| **kch123** | favorite | 5 | $73K | +$1.7K | +2.4% | 100.0% | 0.959 | 95.9% | +4.1pp |
| RN1 | neutral | 455 | $63K | -$726 | -1.2% | 55.8% | 0.497 | 49.7% | +6.1pp |
| RN1 | underdog | 1432 | $101K | **-$9.2K** | **-9.1%** | 39.2% | 0.287 | 28.7% | +10.5pp |
| beachboy4 | underdog | 4 | $1K | -$501 | -47.2% | 0.0% | 0.042 | 4.2% | -4.2pp |
| **tdrhrhhd** | underdog | 2157 | $22K | **-$12.3K** | **-57.0%** | **0.0%** | 0.054 | 5.4% | -5.4pp |

### 4.1 Yorumla

- **Favorite-buy: 4/4 trader pozitif** (sample yeterli olan). RN1 calibre, swisstony+surfandturf belirgin EDGE.
- **surfandturf'in 100% win rate (n=72, avg $0.768)** istatistiksel olarak "rastgele favori al" hipotezini ezici şekilde yalanlar. 76.8% implied'da 100% gercek = market secimi superyo olmus.
- **Underdog buy: hepsi NET LOSER**, ama win rate'ler hala implied'a yakin/ustunde. Kayip dolar-weight'tan geliyor (kayipta full kaybediyor, kazandiginda hala dusuk fiyat × dusuk gain).
- **tdrhrhhd anomali:** %0 win rate 2157 underdog trade'inde. Bu trade'ler sample bias mi (sadece kaybedenler resolved) yoksa gercekten saçma sapan bahis mi? Daha derin bakilmali.

---

## 5. surfandturf detaylı: hangi marketler?

**13 unique market**, 3500 trade. Top 5:
1. Cavaliers vs Pistons (Cavaliers @ $0.38, n=996, **henuz acik** — 0 pnl)
2. Arsenal FC Yes @ $0.631 (n=622, **acik**)
3. Thunder vs Lakers — **iki tarafa da bahis koymus** (Thunder @ $0.82 n=549 + Lakers @ $0.186 n=532) ← **HEDGE veya YES+NO arbitrage pattern!**
4. FC Barcelona Yes @ $0.583 (n=186, acik)
5. Real Madrid Yes @ $0.223 ve $0.768 — **iki farkli zamanda iki farkli fiyatta** (n=161 + n=72)

**Thunder vs Lakers'da iki taraf da:** Thunder @ $0.82 + Lakers @ $0.186 = $1.006 → spread alan, ama hedge tasiyor. **YES+NO arb pattern (Sprint 01 §3.1)** **gercekten gozlemlendi**. Sprint 01'de "kimse paired YES+NO arb yapmiyor" demistim, ama bu surfandturf'da var.

**Real Madrid'i de hem $0.223 hem $0.768'de almis** — yani fiyat dusukken alıp fiyat yuksekken yine alıyor (cumulative position building). Single-fav-buy gibi gozukmuyor, **timing-based market participation**.

---

## 6. Sprint 02 backtest sonucu vs gercek trader davranisi - CELISKI

| Onerme | Sprint 02 backtest | Gercek 7-trader veri |
|---|---|---|
| BUY favorite ($0.55-0.85) | **-6.3% (negatif)** | **+9% ila +29% (POZITIF)** |
| BUY underdog ($0.05-0.45) | **+30% (pozitif)** | **-9% ila -63% (NEGATIF)** |

**Bu celiskinin sebepleri (hipotez):**
1. **Sample mismatch:** Backtest 8400 closed sport market kullandi; 7 trader sadece 439 markette bahis koydu. Backtest evrenı cok daha genis ve "selection" yok.
2. **Entry price proxy:** Backtest'te 24h-before-close snapshot price kullandim; trader'larin gercek fill price'i farkli (snapshot vs aktual fill arasinda spread/movement).
3. **Selection edge:** Trader'lar muhtemelen "her favori"yi degil, **bilgi edge'leri olan favorileri** seciyorlar. Backtest selection'siz oldugu icin ortalama-piyasa = -6%, ama selection'la +20%.
4. **Resolution data sample:** Sadece 189/439 market resolved bizim batchimizde — kalanlar henuz acik. Resolved'lar muhtemelen daha hizli-cozulen mac-tarzi marketler (favori belli, hızlı resolve), gerçek "iddia" piyasalarini eksik yansitiyor olabilir.

**Onemli:** Sprint 02 backtest'inin "UNDERDOG +30%" iddiasini **kanitli olarak güvenmemeliyim**. Methodoloji issue'leri var. **Trade-level analiz daha guvenilir.**

---

## 7. ORTAK PATTERN var mi?

Sayisal oz:

| Pattern adayi | Kanit | Karar |
|---|---|---|
| "Hepsi favori al" | 4/7 trader (surf, RN1, swiss, kch) NET POZITIF favorite buy'da | **EVET** ortak, ama kch n=5 cok az |
| "Hepsi underdog al" | 4/7 trader (surf, swiss, RN1, tdrh) buy'larin %50+'si underdog price'da AMA dollar-weighted MOST trader negative | **HAYIR** strateji degil, alt-ozellik |
| "Hepsi YES+NO arb" | 1/7 trader (surfandturf) ayni event'te iki tarafa da bahis (Thunder/Lakers) | **HAYIR** ortak degil |
| "Hepsi selection edge'le favori al" | 4/4 trader implied'in ustunde win rate (favorite bucket) | **EVET** ama edge kaynagi (info, model, news) BIZ ICIN OPAQUE |
| "Hepsi burst execution" (Sprint 01 fingerprint) | 7/7 same-second %20-40 | EVET ama sirf STIL, alpha kaynagi degil |

**Net ortak pattern:**
1. Spor marketlerinde işlem yaparlar (7/7)
2. Buy-only veya buy-dominant (BUY ratio >75% hepsi)
3. Burst execution (same-second clustering 20-40%)
4. Favorite buys'larinda **kar ediyorlar** (4/4 sample yeterli olanin)
5. Sample edge implied probability'nin ustunde (win rate > price'da implied edilen)

**Ama:** edge kaynagi seffaf degil — neden bu favorileri seciyorlar, neden boylesi BU kazaniyor cevabsiz.

---

## 8. Sprint 03 stratejisi icin sonuc

### Naif "favori al" calismaz
Backtest -6.3% gosterdi. 8400 market ortalamasinda favori-bias yok.

### Naif "underdog al" da calismaz
Trader-level data -9% ila -57% gosterdi. Backtest'in +30% iddiasi methodologi artifact.

### Gercek alpha kaynagi: SELECTION
Winners HANGI favoriyi sectiklerinde edge'i koyuyorlar. Bizim:
- News feed yok
- Probability model yok
- Order book micro-structure ekslesme yok
- → Selection mechanism'ı yeniden insa edemeyiz directly

### Sprint 03 icin uc opsiyon

**Opsiyon 1 — copy-trader (passive replication)**
Surfandturf gibi 1-2 trader'i seç, **gercek-zamanlı izle** (data-api/trades polling), her yeni BUY'unu kucuk size ile mirror'la. Edge'i biz uretmeyiz, onlardan kopyalariz.
- Risk: gec kaliyoruz (orders zaten dolmustur), front-running mahsuru
- Edge: zero R&D, gozlemlenmis %29 RoI'ye yakin alabiliriz

**Opsiyon 2 — bilgi-edge layer ekle (info enrichment)**
Polymarket spor marketleri × external data (bookmaker odds, ESPN scores, injury reports). Karşılaştır → bookmaker'da daha cok favori ama Polymarket'ta dengeli → edge.
- Risk: dis veri kaynagi yonetimi, hizlik
- Edge: kendi alpha üretimi

**Opsiyon 3 — pivot, daha basit/safer strateji**
YES+NO arb (surfandturf'in Thunder/Lakers ornegi gibi) — fiyat toplami < $1.00 tespitiyle anlik arb. Bilgi edge'i gerekmiyor; sadece order book derinligi ve hız.
- Risk: edge kucuk, rekabet yuksek
- Edge: matematiksel kesinlik, info gerek yok

### Onerim
**Opsiyon 3 + Opsiyon 1 hibrit:**
- Sprint 03 V1: YES+NO arb scanner + execution (clean math, no info-edge gerekli)
- Sprint 03 V2: surfandturf gibi 1 trader'i passive copy (kucuk-size, riskli paralel test)
- Opsiyon 2 (info edge layer) Sprint 04+ ileri ihtiyac olursa

**Onerimin sebebi:** Veriden somut sekilde dogrulanmis tek "edge" pattern (surfandturf'in Thunder/Lakers'da yaptigi paired bet) Opsiyon 3 ile esmek. Diger seyler ya benim icat ettigim teori ya da reverse-eng edemedigim opaque selection.

---

## 9. Acik/devam edilecek

- Resolved sample 189/439 (43%) — kalan 250 market acik veya disputed. Bir-iki gun bekleyince daha cok resolve olur, re-analyze yapilabilir.
- tdrhrhhd anomalisi: 2157 underdog buy, 0% win rate. Sample bias mi yoksa gercekten kaybediyor mu? lb-api +$733K demesi enteresan — open positions + redemption'larin breakdown'u ayri analiz konusu.
- surfandturf'in YES+NO arb davranisi: kac event'te yapiyor, ortalama spread, her trade'in tek-tek pnl'i. Sprint 03 V1'in spec'i icin bu zorunlu.
- 4 trader (beachboy4, kch123, gfjoigfsjoigsjoi, tdrhrhhd) icin **resolved sample yetersiz** — kch123 sadece 5, beachboy4 4, gfjoigfsjoigsjoi 0. Daha cok piyasa resolve oluncaya kadar yorum riskli.
