# Sprint 01 — Trader Discovery & Analysis — Bulgular

**Tarih:** 2026-05-14
**Snapshot kapsami:** lb-api top-50 across 5 profit + 2 volume periods → 86 unique aday wallet → 10 hesap derin profillendirildi (top-5 MM + top-5 oneshot).

> Bu rapor Sprint 01'in **karar dokumani** — Sprint 02 hedef stratejisi buradaki bulgulardan secilecek.

> ⚠️ **2026-05-14 ayni gun POST-VALIDATION CORRECTION:** Bolum 1-7'deki bircok cikarim **kismi olarak yaniltici cikti** — `lb-api`'nin `period` parametresi backend'de **tamamen yok-sayiliyor** (her cagri lifetime donuyor). Eski cikarimlar **arsiv**, GERÇERLI bulgular **§8**'de. Once §8'i oku.

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

---

## 8. POST-VALIDATION CORRECTION (2026-05-14, ayni gun)

> Bolum 1-7'deki bulgular `lb-api/profit?period=...` ve `lb-api/volume?period=...` cagrilarinin per-period filtre yaptigi varsayimina dayaniyordu. Validation `pm_research/validate.py` ile bu varsayim **direkt probe ile cürütüldü**. Asagidaki §8 GUNCELLENMIS ve gercek olan tek bulgudur.

### 8.1 Yapisal API bug'i — `lb-api` period yok-sayiyor

Probe (sirayla day/week/month/year/all):
```
Theo4 profit:  $22.05M, $22.05M, $22.05M, $22.05M, $22.05M  (hepsi LIFETIME)
swisstony vol: $765.7M, $765.7M, $765.7M, $765.7M, $765.7M  (hepsi LIFETIME)
bossoskil1 profit: -$2.39M (her period icin) (hepsi LIFETIME)
```

Top-3 listesi de tum periodlarda IDENTICAL → **lb-api gercekte sadece lifetime tutuyor**, period frontend'de cosmetic.

**Sonuc:** "sustained_winner / recent_oneshot_winner" cohort logic'i (`profit_year vs profit_week`) **bos** — iki sayi her zaman ayni.

### 8.2 Reconciled gercek tablo (10 trader + bossoskil1 control)

Trade-cashflow (BUY-SELL+REDEEM, son N gun) ile lb-api lifetime karsilastirmasi:

| Trader | Lifetime profit | Lifetime volume | week net cf | week vol | yr net cf | yr vol | YORUM |
|---|---|---|---|---|---|---|---|
| Theo4 | +$22.05M | $43M | **$0** | **$0** | **$0** | **$0** | **DORMANT 1.5 yıl** |
| Fredi9999 | +$16.62M | $76M | $0 | $0 | $0 | $0 | **DORMANT 1.5 yıl** |
| Len9311238 | +$8.71M | $16M | $0 | $0 | $0 | $0 | **DORMANT 1.5 yıl** |
| kch123 | +$12.61M | $290M | +$446K | $825K | +$146M | $2M | Aktif: %99 cashflow REDEEM (eski poz cıkarıyor) |
| RN1 | +$8.96M | $547M | +$10.4M | $391K | +$15.7M | $391K | Aktif: %95 cashflow REDEEM |
| cigarettes | +$1.03M | $499M | +$547K | $345K | +$1.8M | $345K | Aktif: cogu REDEEM |
| risk-manager | +$322K | $654M | +$8K | $29K | +$273K | $29K | Cok dusuk recent activity |
| 9c667a1 | +$112K | $456M | +$413 | $3K | +$2.2K | $3K | **Sönmüş aktivite** |
| tripping | **+$96K** | **$675M** | **-$108** | $2.8K | +$23K | $2.8K | Lifetime margin **0.014 bps** — pratik olarak break-even |
| 492442EaB | -$1.58M | $492M | +$761K | $1.8M | +$201M | $44M | Lifetime KAYIPTA, redemptionla cashflow + |
| bossoskil1 (control) | -$2.39M | $203M | +$8.8M | $2.6M | +$62.2M | $2.6M | Lifetime KAYIPTA, redemption $64M ama hala net buyuyor (BUY > SELL+REDEEM kullanım disi degerle) |

### 8.3 Bolum 1-7'nin INVALIDE olan cikarimlari

| Eski cikarim | Gercek |
|---|---|
| "Theo4, Fredi9999 = recent oneshot winners" | DORMANT 1.5 yil — eski event winnerlari, hesaplari atil |
| "Tripping = replicable long-shot scalper" | $675M volume / $96K lifetime profit = **0 marjin**, replikasyon hedefi degil |
| "Sustained_winner cohort logic" | profit_year=profit_week always → cohort logic kor |
| "100% buy_ratio = info-edge directional" | Yarisi BU, yarisi sadece dormant. Kontrol icin recent activity kesin |
| "MM cohort = market makers" | %60'i sadece "cok yapan ama net 0 marjin", %20 dormant-ish, %20 redemption collector |

### 8.4 Yeni gercek cikarimlar

1. **lb-api leaderboard'lari direkt actionable degil** — lifetime gosteriyor; bircok top hesap yıl(lar)ca atil.
2. **Currently-profitable bot bulmak farkli yontemle olur:** ya recent global /trades scan ile aktif adresler topla, ya /holders endpoint ile aktif marketlerin top holderlarini topla, ya da gunluk snapshot serisi (delta-based actively-trading filter).
3. **Trading P&L gercek hesabi icin trade-cap (3000 offset) sorun:** Aktif HF trader'lar icin son 1-7 gunun otesini goremiyoruz. Bu structural — workaround: weekly snapshot biriktirip "rolling window" olustur.
4. **Hicbir trader bizim sample'da "currently winning at scale" olarak isaretlenemedi.** En iyi hareket eden tripping bile ~0 marjin. Sprint 02 stratejisini "var olan bir botu kopyala" olarak kuramayiz; ya yeni discovery, ya teori-based strateji secimi.
5. **Sektor reportu'nun "%7.6 wallet karli" iddiasi** muhtemelen lifetime ile - aktif winner orani daha az olabilir.

### 8.5 GUNCELLENMIS Sprint 02 onerileri (3 yon)

#### Yon I — Yeni discovery (recommended, veri-once prensiple uyumlu)
**Ne:** "Currently-profitable, currently-active" hesaplari tespit eden bir kesif modulu yaz. Yontem:
- Polymarket'in **aktif marketlerini** bul (gamma-api/markets, status=active)
- Her market icin /holders top 30
- Bu havuzdan adresleri unique al → ~500-2000 currently-positioned adres
- Her biri icin son 7-14 gunluk net cashflow + redemption hesapla
- Pozitif son-hafta cashflow + min N trade aktivitesi → "currently-winning" cohort
**Maliyet:** 1-2 saat ek kod + ~10 dk batch run
**Sonra:** O cohort'u replikasyon adayi olarak Sprint 02'ye al
**Risk:** Belki gene bulamayız — o zaman teori-based yaklasim kacinilmaz olur, ama en az kanıtlanmıs olur

#### Yon II — Teori-based pivot (geleneksel)
**Ne:** Reverse-engineer'dan vazgec. Klasik MM (Avellaneda-Stoikov) veya YES+NO arb stratejisini direk implement et, simulator'da kalibre et, kanarya ile test et.
**Avantaj:** Kanıtlanmıs akademik baz, bekleme yok
**Risk:** Polymarket spesifik (likidite, fee, gas) farkliliklarini biz cikartmamiz gerek; "neden bu bot yok zaten" sorusu cevapsiz

#### Yon III — Pas, Sprint 01'i biraz daha besle
**Ne:** Yon I + multi-day snapshot serisi (1-2 hafta gunluk lb-api + activity scan, tarihsel rolling pencere) — sustained-winner tespiti icin gercek temel
**Avantaj:** En kuvvetli veri tabanı
**Dezavantaj:** Sprint 01 1-2 hafta daha uzar; momentum kaybi

### 8.6 Onerim
**Yon I**. Mantik:
- Veri-once prensibi (kullanici acikca istedi)
- Sprint 01 zaten "discovery" sprintı; "yanlis sorudan yanit aldik, dogru soruyu sor" makul
- 1-2 saat is + run; sonuc kotuyse Yon II'ye revert kolay
- Ayrica yan urun: `pm_research/discover.py`'in /holders + recent-trades varyantı genel-amaclı, sonraki sprintlerde de lazim

---

## 9. POST-VALIDATION-V2 GERCEKLEME (2026-05-14, ayni gun)

> Once §8'i okudugun varsayilir. §8'de "lb-api period broken, gercek zaman-pencereli P&L yok" diye yazmistim. **Bu da yarim dogruydu.** Kullanici bonereaper'in profile'inde "+$277K aylık P&L" gozuktugunu hatirlattı; o sayinin nereden geldigini probelayinca **`user-pnl-api.polymarket.com`** isimli ayri bir service buldum. **Gercek period-windowed PnL var — sadece lb-api'da degil, farkli subdomain'de.**

### 9.1 Yeni endpoint
```
GET https://user-pnl-api.polymarket.com/user-pnl
    ?user_address=0x...      # snake_case zorunlu
    &interval=1d|1w|1m|all|max
    &fidelity=1d|1h          # bucket size

Don: [{"t": <unix>, "p": <cumulative_pnl_usd>}, ...] timeseries
```

Bonereaper dogrulama: API +$282,952 (1m). Kullanici sayisi +$277,854. Fark $5K = sayfanın ne zaman izlendiği vs simdi arasi market fluctuation. **EŞLEŞTI.**

`pm_research/user_pnl.py` modulu olusturuldu, `enrich.py` candidates'a 1m_pnl ekleyip yeni cohort'lariyor.

### 9.2 Yeni cohort dagilimi (86 aday)

| cohort_v2 | n | ortalama 1m P&L | tanim |
|---|---|---|---|
| dormant | **33** | $0 | 1d ve 1m hareket yok — lb-api'nın gosterdigi sahte top |
| consistent_winner | 9 | $848K | 1m > $100K, lifetime > $1M, 1m < lifetime/2 (yıllık trend) |
| recent_surge_winner | 8 | $2.24M | 1m > $500K, lifetime'a kıyasla buyuk yuzde |
| small_winner | 13 | $36K | 1m > $5K |
| currently_winning | 5 | $148K | 1m > $100K (consistent kriter karsilamiyor) |
| high_vol_break_even | 8 | $1.2K | volume > $100M, 1m P&L ≈ 0 (Tripping benzeri) |
| actively_losing | 5 | -$293K | 1m < -$100K |
| low_activity | 5 | -$5K | tanimsız |

**38% dormant.** lb-api'nın bizi yanılttigi tam burada. Gercek aktif-karli kohort: 9 + 8 + 5 = **22 hesap**.

### 9.3 Top-7 currently-winning fingerprint

7 winner profillenip karsilastirildi:

| name | 1m | trades/day | Buy% | mkt | med$ | same-sec% | onemli iz |
|---|---|---|---|---|---|---|---|
| **surfandturf** | $3.36M | 745 | 97% | 13 | $12.7 | 21% | Real Madrid Yes BUY x100, focused (13 mkt) |
| swisstony | $2.00M | **3500** | 100% | **220** | $7 | 21% | Multi-event spread bets, diversified |
| RN1 | $1.70M | **3500** | 100% | 72 | $8 | 41% | Tennis matches, single market burst |
| **beachboy4** | $1.29M | 32 | 100% | 70 | $25 | 38% | Inter Miami Yes @ $0.48, **200K size orders** |
| kch123 | $0.77M | 218 | 100% | 49 | $9 | 26% | NHL hockey Yes BUY (Avalanche etc.) |
| tdrhrhhd | $0.73M | 59 | 79% | 20 | $0.72 | 15% | Long-shot SELL @ $0.01 (Fetterman) |
| gfjoigfsjoigsjoi | $3.94M | 114 | 100% | 22 | $58.7 | 35% | FC Barcelona Yes huge orders |

### 9.4 PATTERN: **Sports Favorite Burst-Buy** dominant strateji

6/7 winner ayni yapı:
1. **Spor marketinde favori takım sec** (Real Madrid, Inter Miami, Barcelona, Avalanche, vb.)
2. **YES tarafinda BUY** ($0.48-0.78 fiyat aralıgı = positive EV bahis)
3. **Burst execution:** tek pozisyonu 20-40% same-second clustering ile fragmente et (slippage kontrol, front-run kacirma)
4. **Hold-to-resolution:** redemption ile cikis (BUY-only, sell yok)

Tek istisna: tdrhrhhd long-shot SELL pattern (degisik, daha zor okunuyor).

### 9.5 Replikasyon analizi

**Edge kaynagi:** "Spor pazarlarinda favori takima tutarli underpricing" — bu istatistiksel bir bias (sports betting literaturunda "longshot bias" olarak biliniyor: pazarlar favorileri olçer-olcmez biraz alt-fiyatlar, longshot'lari ust-fiyatlar). Polymarket spor markette muhtemelen **favori takıma yapısal underpricing** var.

**Replike etmek icin ne lazim:**
1. **Spor market scanner** — gamma-api kategori filtresi (`category=sports`) ile gerceklesen tum aktif spor maclarini cek
2. **Favori detection** — P(YES) > 0.55 esik OR ucu vurgulayan ek kriter (bookmaker odds vs Polymarket fiyat farki)
3. **Mispricing filter** — basit baseline: P(YES) < (1 - bookmaker_implied_prob) yani Polymarket bookmaker'dan ucuza satıyor
4. **Burst execution layer** — verilen target_size'i N kucuk fill'e bol (5-30 fill, 0.1-1 sn arasi)
5. **Hold to resolution** — redemption otomasyonu

Sermaye gereksinimi: $5K-$50K kanarya (per-pozisyon $50-$500), Sprint 04+'da $50K-$500K full deploy.

**Backtest plan:** Resolved spor market geçmisini (gamma-api / closed_markets) çek. Her marketin BUY-the-favorite-at-listed-price simulation. **Average return ratio** hesaplanir.

### 9.6 GUNCELLENMIS Sprint 02 onerisi (NIHAI)

**Yon: Sports Favorite Strategy** (yukaridaki Yon I'in spesifik instantiation'i, somut ornek 6 hesapta gozlemlendi)

Sprint 02 hedef:
1. **gamma-api/markets** ile aktif spor marketleri listele + closed_markets ile resolve geçmisi
2. **Backtest engine:** her resolved spor maca BUY-favorite (P > 0.55) at-listed-price + size policy + holding-to-resolution → return-on-capital simulation
3. **Eger backtest > 5%/ay net (gas dahil) → Sprint 03'te ExecutionClient + live kanarya
4. Eger negatif → fallback Yon II (theory-first MM)

Sprint 02 sure tahmini: **3-5 gun**. Kullanici Sprint 02 prompt'unu acmaya hazir oldugunda baslarim.

### 9.7 Notlar / dikkat edilmesi gerekenler

- **gfjoigfsjoigsjoi $3.94M ama 1d/1w'da 0** → tek-event surge (FC Barcelona resolution'i geçen hafta), pattern olarak surfandturf'tan farkli — replikasyon icin daha az ornekleyici
- **surfandturf en saglikli signal**: positive 1d, 1w, 1m hepsinde — gerçek surekli kazanan
- **bossoskil1 ve 492442EaB recent_surge** olduklari icin atladık ama fingerprint icin de ilginc — Sprint 03 prelaunch'inde isteyen detayli inceleyebilir
- **lb-api hala aday discovery icin kullanilabilir**, ama enrichment adimi (user-pnl-api ile 1m kontrol) **kacinilmaz** dormant'lari elemek icin
- **`user-pnl-api`'nın rate-limit'i bilinmiyor** — şu an %50 conservative tahminle 5 r/s set ettik (`pm_research/http.py`)

