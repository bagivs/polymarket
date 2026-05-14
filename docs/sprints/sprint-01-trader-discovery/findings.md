# Sprint 01 — Trader Discovery & Analysis — Bulgular

**Tarih:** 2026-05-14
**Snapshot kapsami:** lb-api top-50 across 5 profit + 2 volume periods → 86 unique aday wallet → 10 hesap derin profillendirildi (top-5 MM + top-5 oneshot).

> Bu rapor Sprint 01'in **karar dokumani** — Sprint 02 hedef stratejisi buradaki bulgulardan secilecek.

---

## 1. TLDR — yedi madde

1. **"Klasik market maker" goremedik.** Top-10 hesabin **hicbiri** YES+NO paired quoting yapmiyor (`paired_pct_of_events` median <%1, max %2.6). Polymarket'ta gelir Avellaneda-Stoikov tipi MM degil **oz al-tut** ve **uctaki tokenleri scalp** ile geliyor.
2. **Top yillik kar adaylarinin tamami `buy_ratio = 1.0`** — yani sadece BUY yapip resolution'a kadar tutuyorlar. Bu adamlar MM degil, **direksiyonel event-buyer**.
3. **`closed_positions` API'si yaniltici** — sadece **top-50 kazanan pozisyon** donduruyor, kayiplar gozukmuyor. Bossoskil1 -$2.2M aylik kayipta ama API "100% win rate" diyor. Win-rate metrigini trade-history'den hesaplamak zorundayiz.
4. **Long-shot scalper "Tripping"** ($675M/ay volume, %25 buy, $0.22 median trade) **degeri olcusunde tek replikasyona aday model** — pure execution skill, info-edge gerektirmez.
5. **Recent oneshot kazananlarin** P&L / traded-volume orani **2-10x**. Bu replike edilemez (info edge gerek). Ama execution stillerini kopyalayabiliriz (burst-buy, same-second clustering).
6. **Quasi-MM** profili 2 hesapta var (`risk-manager` ve `0x9c667a1`): ~%60 buy oran, dengelisi ama tam paired-quoting degil. Belki "directional bias + spread capture" hibrit.
7. **Polymarket data API yapisal kisitlari:** `/trades` offset 3000'de hard cap, `/closed-positions` top-50 winners only, lb-api top-50 hard cap, no pagination. Lifetime trade history erisilemez — fingerprinting recent activity uzerine kurulur.

---

## 2. Cohort-by-cohort fingerprint

### 2.1 "recent_oneshot_winner" (top 5 by yillik kar)

| Hesap | Trades/day | Buy% | Markets | Median trade $ | Same-sec % | Realized $M | Anlik value $ |
|---|---|---|---|---|---|---|---|
| Theo4 (`0x5668...`) | 161 | 100% | 11 | $49 | 36% | $22.05 | 0 |
| Fredi9999 (`0x1f2d...`) | 464 | 100% | 9 | $42 | 20% | $18.64 | 0 |
| kch123 (`0x6a72...`) | 218 | 100% | 49 | $9 | 26% | $16.87 | $279K |
| Len9311238 (`0x78b9...`) | 264 | 100% | 7 | $33 | 49% | $8.71 | 0 |
| RN1 (`0x2005...`) | **3500** | 100% | 85 | $6 | 45% | $3.46 | $534K |

**Imza:**
- 100% BUY → asla satmiyor, redemption ile kapatiyor (sonuc lehineyse $1, aleyhineyse $0)
- Yuksek same-second % (20-49%) → tek bir buyuk emir kucuk fill'lere boluyor (front-run kacirma)
- Inter-arrival median 2-4s → burst tarzi
- Az sayida market (7-85), buyuk pozisyon → bir kac olaya odaklanmis
- Current value cogunda 0 → kazanc cikarilmis veya pozisyon kapanmis

**Strateji yorumu:** Bu hesaplar **yuksek-itimat bilgi temelli buyuk-bahis** koyup, kucuk burst order'larla pozisyon kuruyor, resolution'i bekliyor. Edge: bilgi/analiz, execution **yardimci**.

**Replikasyon zorlugu:** YUKSEK. Bilgi edge'i olmadan execution kopyalamak para kazanmaz.

### 2.2 "market_maker_candidate" (top 5 by aylik volume)

| Hesap | Trades/day | Buy% | Markets | Median trade $ | Same-sec % | Realized $M (cap'li) | Volume/ay $M |
|---|---|---|---|---|---|---|---|
| tripping (`0x6480...`) | 917 | 25% | 16 | $0.22 | 8% | $0.08 | $675 |
| risk-manager (`0xa61e...`) | 2268 | 59% | 25 | (n/a) | 9% | $1.54 | $654 |
| cigarettes (`0xd218...`) | 1760 | 100% | 400 | (n/a) | 32% | $4.55 | $499 |
| `0x9c66...` | 1026 | 62% | 16 | (n/a) | 7% | $0.10 | (orta) |
| `0x4924...` | 66 | 100% | 352 | (n/a) | 39% | $17.81 | (whale) |

**Uc farkli profil cikti:**
- **Long-shot scalper (tripping):** uc-fiyat tokenlere ($0.001-$0.01) cift-tarafli quote, tiny per-trade kar ($1500 median per closed position).
- **Quasi-MM (risk-manager, 0x9c66):** ~%60 buy, multi-market, dusuk same-sec % (7-9%) → daha "geleneksel" ama yine tam paired degil.
- **Multi-market directional buyer (cigarettes, 0x4924):** 100% buy ama 350-400 marketta — event buyer at scale (info edge'li).

### 2.3 Cohort comparisonu — neyi ayirt ediyor?

| Metric | OS median | MM median | Ayirt edici mi? |
|---|---|---|---|
| `buy_ratio` | 1.0 | 0.61 | ✅ Evet — OS asla satmiyor |
| `same_second_trade_pct` | 36.4 | 8.8 | ✅ Evet — OS bursty, MM steady |
| `unique_markets` | 11 | 25 | ⚪ Az |
| `paired_pct_of_events` | 0.8 | 0.0 | ❌ Ikisi de cok dusuk |
| `realized_pnl_total` | $16.9M | $1.5M | ✅ OS daha karli (cap'li) |
| `current_value_usd` | $0 | $4.8K | ⚪ OS kapali kar, MM hala acik |

**Sonuc:** En guclu ayirt edici **buy_ratio + same_second pct**. Bunlari iki-eksenli scatter'a koysak iki cohort temiz ayrilir.

---

## 3. Polymarket platform bulgulari (icraat icin onemli)

| Bulgu | Kaynagi | Etkisi |
|---|---|---|
| Trade size = `size × price` USDC | Probe + dokuman | OK |
| Outcome tokens %0.001-%0.01 likittir | Tripping closed_positions | Long-shot strategi tasarimi icin ana market kategorisi |
| `closed_positions` sadece top-50 winners | Bossoskil1 sanity | Win-rate hesabini trade history'den yap |
| `/trades` offset 3000'de cap | Probe | Lifetime trade erisilemez; sample'la calis |
| lb-api top-50 hard cap | Probe | Aday havuzu ucu sinirli; multi-period unionla genislet |
| Buy ratio ≈ 1.0 → hold-to-resolution | OS cohort | Cuzdan acik pozisyon takibi etkili sinyal |
| Same-second clustering 30%+ → burst | Both cohorts | Ucretli RPC ile execution avantaji bu burst'lerin matchedlimit'inde fark eder |

---

## 4. Tarihsel referans cumlemize uydu mu?

Sektor raporlari (PROJECT_CONTEXT §3.3):
- "Top %1 karin %75'ini aliyor" → bizim top-10 yillik realized ortalamasi $11M, total $125M+. Fiyat yapilanmasi tutarli.
- "Sub-100ms execution captures 73% of arb profits" → biz arb'cilari yakalayamadik (top-volume listesinde yoklar) — onlar ayri bir kategori, smaller per-wallet, very high frequency.
- "Klasik MM ($10K + 0.5-2%/ay)" → top-volume'da yok cunku bu olcekli MM cuzdan basina $1M-$10M aylik volume yapar, bizim top-50 listemize giremez. **Bu bizim Sprint 02 firsat alanimiz olabilir** (kucuk olcekli, az rekabet).

---

## 5. Sprint 02 oneri — UC OPSIYON

### Opsiyon A: Long-shot scalper (Tripping pattern)
**Ne:** Polymarket marketlerinde `0.001-0.01` aralikta yatan token'lara cift-tarafli kucuk quote koy, spread'i scalp et. Resolution riski neredeyse yok cunku 0'a iniyorsa zaten ucuz aldin, 1'e gidiyorsa muthis ROI.

**Zor:** Spread cok dar, cancel/replace'leri rate-limit'e takmadan calistirmak; binlerce tail markete eszamanli quote.

**Sermaye:** $5K-$50K bile yeterli (per-position $0.10-$10).

**Edge:** Pure execution. Info gerek yok. **Replikasyona en uygun.**

### Opsiyon B: Klasik Avellaneda-Stoikov MM (kucuk-orta marketler)
**Ne:** 5-10 secilmis politika/spor/kripto marketinde envanter-skewed bid/ask, bid-ask spread capture.

**Zor:** Polymarket'ta CLOB likidite degisken, news event riski (kotasyonu cek).

**Sermaye:** $10K-$100K (sektor ref).

**Edge:** Spread + envanter yonetimi. Info gerek yok ama klasik HFT MM ile rekabet var.

### Opsiyon C: "Hold-to-resolution" execution layer (info-edge'li hibrit)
**Ne:** Kullanici bir markette pozisyon "hedef" verir; bot burst-execution ile en iyi fiyat alir. Sadece icra otomasyonu, karar insan.

**Zor:** Az - sadece akilli order routing.

**Edge:** Kullanicinin bilgi edge'i + bot execution.

### Onerim
**Opsiyon A**.

Sebep: (1) Kullanici "kazanan botlardan ogrenelim" istedi — Tripping somut ornek; (2) info edge gerektirmiyor; (3) sermaye dusuk; (4) backtestable (uc-fiyat token trade history kayittan replay edilir); (5) Sprint 02-03'te MarketDataFeed + ExecutionClient'i bu use-case ustune insa edebiliriz, sonra Sprint 04+'da daha karmasik stratejilere genisleyebiliriz.

---

## 6. Sprint 01 kapanis sartlari (Sprint 02 oncesi tek atilim)

- [x] Cesitli veri kaynagi (5+) degerlendirildi → 4 host, 11 endpoint canli probe
- [x] @bonereaper → leaderboard ile pas gectik (gerekcesi data-sources.md'de)
- [x] 20+ aday → 86 toplandi, 10 derin profillendi
- [x] Her profillenmis hesap icin: summary.json + dolu fingerprint + insan-okunur paragraf (bu rapor)
- [x] Sprint 02 icin somut 1 strateji onerisi: Opsiyon A (long-shot scalping)
- [ ] **Smoke test (`uv run pytest`)** — yazilacak (bir sonraki commit)
- [ ] Kullanici Sprint 02 hedefini secip onaylayacak

---

## 7. Acik / not edilecek konular

- **Closed_positions semantigi** netlesirilebilir: Polymarket dokuman'inda "closed" tanimi nedir, fee dahil mi, redemption'lari sayiyor mu? Issue acalim.
- **Lifetime trade history** icin alternatif: The Graph subgraph (`polymarket-matic`) muhtemelen on-chain her trade'i tutar. Sprint 02-03'te degerlendirilecek.
- **Multi-day snapshot serisi** ile sustained-winner tespiti — Sprint 02 paralelinde gunluk cron olarak basitce eklenebilir (~5 dk).
- **YES+NO arb traderlarini bulma** — top-volume listede yoklar. /holders endpoint ile per-market top holders tarayip kucuk-dengeli pozisyon sahiplerini bulabiliriz. Sprint 02 opsiyonel ek.
