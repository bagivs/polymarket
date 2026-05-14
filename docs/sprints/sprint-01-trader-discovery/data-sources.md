# Data Sources Map — Polymarket Trader Discovery

> Sprint 01'in ilk ciktisi. Asagidaki tablo **canli probe** ile dogrulandi (2026-05-14).
> Endpoint'lerin gercekten dondurdugu shape ornek olarak verilmistir.

---

## 1. Yikilan ve sansa kalan tespitler (TLDR)

- **Username → wallet resolution** dogrudan public API ile mumkun degil. `gamma-api/profiles?username=` 401 veriyor (auth gerek). Bunu cozmek icin: ya leaderboard ile basla (bizim secim), ya HTML scraping, ya Polymarket'in resmi auth akisina basvur.
- **Leaderboard public, dokumante degil ama erisilebilir:** `lb-api.polymarket.com/{profit,volume}?period={day,week,month,year,all}&limit=N`. Tek bir cagri ile top 200 hesap.
- **"Top trader" etiketi cok kaygan.** Polymarket frontend'inde #1 (`bossoskil1`, $3.18M overall profit) **bu ay -$2.23M zararda**. Sustained profitability icin **multi-period kesisim** gerekli (gunluk + haftalik + aylik + yillik kesisimi).
- **Bonereaper** (kullanicinin verdigi seed) bu saglikli leaderboard yaklasimi karsisinda cok daha **kucuk olcekli** ($7K positions). Bizim icin temsili bir ornek; gercek aday havuzumuz lb-api'den gelecek.
- **Maker/taker ayrimi** data-api `/trades`'de net degil. Trades aggregated (ayni timestamp+price'ta multiple fills tek satira sigmamis). Order-flow / quote analizi icin **CLOB websocket** (Sprint 04+) lazim olacak.
- **`closed-positions` endpoint goldmine:** her kapali pozisyon icin `realizedPnl` dahil. Backtest ve strateji-fingerprinting icin asil veri kaynagi.

---

## 2. Hostlar ve servisler

| Host | Tipi | Auth | Asil kullanim alanimiz |
|---|---|---|---|
| `data-api.polymarket.com` | Public REST | Yok (cogunlukla) | Trades, positions, activity, value, holders — **fingerprinting'in govdesi** |
| `gamma-api.polymarket.com` | Public REST | Bazi yerlerde gerek | Markets/events metadata, search (markets icin) |
| `clob.polymarket.com` | Public REST + WS | Trading icin L2 API key | Order book, midpoint, book depth — **MarketDataFeed'in govdesi (Sprint 04)** |
| `lb-api.polymarket.com` | Public REST | Yok | **Leaderboard (top-N profit/volume by period)** — aday discovery |
| Polygon RPC (e.g. polygon-rpc.com) | Public JSON-RPC | Yok (paid icin opsiyonel) | On-chain CTF token transferleri, contract event'leri (ileride) |
| The Graph (Polymarket subgraph) | GraphQL | Yok | Karmasik on-chain sorgular (ileride degerlendirilecek) |

---

## 3. Endpoint katalogu (canli probe sonuclari)

### 3.1 `data-api.polymarket.com` — fingerprinting govdesi

| Path | Status | Anahtar query | Don | Bizim kullanim |
|---|---|---|---|---|
| `/trades` | ✅ 200 | `user`, `market`, `side`, `takerOnly`, `limit` (max 500), `offset` | proxyWallet, side, asset, conditionId, size, price, timestamp, title, outcome, transactionHash, name, pseudonym | Trade history, time-series fingerprint |
| `/positions` | ✅ 200 | `user` (req), `market`, `sizeThreshold`, `sortBy`, `limit` (max 500) | proxyWallet, asset, conditionId, size, avgPrice, initialValue, **currentValue**, **cashPnl**, **percentPnl**, **realizedPnl**, curPrice, redeemable, mergeable | Open positions snapshot, mark-to-market PnL |
| `/closed-positions` | ✅ 200 | `user` (req), `limit`, vs. | proxyWallet, asset, avgPrice, totalBought, **realizedPnl**, curPrice, title, outcome | **Realized PnL ground-truth** — strateji backtest'inin temeli |
| `/activity` | ✅ 200 | `user` (req), `type` (TRADE/SPLIT/MERGE/REDEEM/REWARD/CONVERSION), `start`, `end`, `limit` (max 500) | proxyWallet, timestamp, conditionId, type, size, usdcSize, transactionHash, title, outcome, name | TUM aktivite (sadece trade degil — split/merge/redeem dahil) |
| `/value` | ✅ 200 | `user` (req), `market` | `[{user, value}]` (USD) | Hizli portfoy degeri |
| `/holders` | ✅ 200 | `market` (req, conditionId), `limit` | per-token holder list | Belirli marketin buyuk pozisyon sahipleri |

**Rate limit (data-api):** general 100 req/s, `/trades` **20 req/s**, `/positions` **15 req/s**. Cloudflare 10s sliding window throttle (delay, hard reject degil).

#### Sample (`/trades?user=...`, traders endpoint):
```json
{"proxyWallet":"0xa5ea...","side":"BUY","asset":"104338...","conditionId":"0x4197...",
 "size":6.666665,"price":0.4,"timestamp":1778771622,
 "title":"Dota 2: Vici Gaming vs Virtus.pro - Game 2 Winner",
 "outcome":"Virtus.pro","outcomeIndex":1,"name":"bossoskil1","pseudonym":"Intent-Noodle",
 "transactionHash":"0x3c8ebe53..."}
```

#### Sample (`/positions`):
```json
{"proxyWallet":"0xa5ea...","asset":"59742...","conditionId":"0xe202...",
 "size":1052878.4441,"avgPrice":0.059,
 "initialValue":62140.89,"currentValue":18425.37,
 "cashPnl":-43715.51,"percentPnl":-70.349,"realizedPnl":0,
 "curPrice":0.0175,"redeemable":false,
 "title":"Will the Detroit Pistons win the 2026 NBA Finals?",
 "outcome":"Yes"}
```

### 3.2 `lb-api.polymarket.com` — aday discovery

| Path | Status | Anahtar query | Don |
|---|---|---|---|
| `/profit` | ✅ 200 | `period` (day/week/month/year/all), `limit` (HARD-CAP 50), `address` | top-50 profit veya tek adres |
| `/volume` | ✅ 200 | ayni | top-50 volume veya tek adres |

**Auth:** Yok. **Rate limit:** Dokumante degil; muhtemel ayni Cloudflare bucketi. Konservatif: <5 req/s baslangic.

**KISIT (canli probe):** `/profit` ve `/volume` **maks 50 sonuc** dondurur, `limit` parametresi 50'nin uzerinde deger alinca yine 50 doner. Pagination da yok (`offset` parametresi yok-sayiliyor; her offset ayni 50'yi getiriyor). Bu yuzden tek board basina aday havuzu = top-50. Daha derin havuz icin **multiple period** (day/week/month/year/all) cross-section veya `/holders` per-market.

#### Sample (`/profit?period=month&limit=3`):
```json
[{"proxyWallet":"0x56687bf4...","amount":22053933.75,"pseudonym":"Theo4","name":"Theo4"},
 {"proxyWallet":"0x1f2dd6d4...","amount":16619506.63,"pseudonym":"Fredi9999"},
 {"proxyWallet":"0x6a72f618...","amount":12606924.47,"pseudonym":"kch123"}]
```

### 3.3 `gamma-api.polymarket.com` — markets metadata + search

| Path | Status | Not |
|---|---|---|
| `/public-search?q=<term>` | ✅ 200 | Markets/events arama. **Username search yapmiyor** (boş donuyor). |
| `/profiles?username=<>` | 🔒 401 | Endpoint var ama auth gerekli. Su an pas. |
| `/events`, `/markets` | (varsayim) | Sprint 03'te kullanacagiz (market metadata) |

**Rate limit (gamma):** general 400 req/s, `/markets` 30, `/events` 50, `/comments+tags` 20, `/public-search` 35.

### 3.4 Diger

- **CLOB API** (Sprint 04): book/price/midpoint 150 req/s, balance GET 200 req/s. Trading 5000 req/10s burst. Order placement icin L1 (private key) + L2 (API key) auth.
- **Polygon RPC**: ileride on-chain transfer / event okumak icin. Public endpoint yeterli oldugu surece, paid Alchemy/QuickNode'a gerek yok.
- **The Graph (Polymarket subgraph)**: degerlendirildi, su an gerek yok — data-api zaten zengin. Karmasik on-chain join'leri gerekirse Sprint 02+.

---

## 4. Aday discovery stratejisi (Sprint 01 plan)

```
1. lb-api/profit?period=year&limit=200    → ~200 yıl top
2. lb-api/profit?period=month&limit=200   → ~200 ay top
3. lb-api/profit?period=week&limit=200    → ~200 hafta top
4. lb-api/volume?period=month&limit=200   → ~200 ay top-volume
5. Birlestir, dedup → ~500-800 unique address
6. Filtreler:
   a. Tum 4 listede gozuken (sustained) → "stable winner" cohort
   b. Yuksek volume + dusuk profit → "market maker" candidate cohort
   c. Yuksek profit + dusuk volume → "directional/event-driven" cohort
7. Her cohort'tan 5-10 ornek sec, derin profil cikar.
```

Bu sayede @bonereaper gibi tek seed'le bagli kalmayiz; veri-driven secim.

---

## 5. Bot/insan ayirma sinyalleri (lb-api'siz, on-data)

Once 50+ trades/day veya 1000+ trades/all gibi basit filtreler (sektor referansi: Bloomberg/FA Magazine 2026 raporu).
Sonra inter-arrival entropy (bot = duzgun ritim, insan = burst), 24/7 aktiflik, ayni saniye icinde paired YES/NO trade'i.

---

## 6. Alti cizilecek riskler

- **Cloudflare WAF:** Yogun probe Cloudflare blokuna girebilir. Conservative: paralel <3, 10s pencerelerde rate limit'in %50'sini gec, retry-with-backoff (Retry-After yoksa exponential).
- **Aggregated trades:** `/trades` ayni order'in birden cok fill'ini ayri satir gosteriyor; same-timestamp+price+conditionId+side dedup'i analiz oncesi sart.
- **`name` vs `pseudonym`:** Ornek olarak bossoskil1 ‟name=bossoskil1, pseudonym=Intent-Noodle". Profil URL'i icin pseudonym kullanan UI da var; iki alani da kayitla.

---

## 7. Acik sorular (Sprint 01 sirasinda netlesecek)

- [ ] @bonereaper'in adresini bulmak hala ihtiyac mi? (Cevap muhtemelen hayir; lb-api zengin)
- [ ] Maker/taker ayrimi icin sadece `/trades?takerOnly=true|false` yeterli mi, yoksa CLOB book history mi gerekecek?
- [ ] Kapali pozisyon `realizedPnl`'de fee dusulmus mu? (Probe gerek)
- [ ] Aktif strateji "split/merge/redeem" desenleri (CTF token mekanigi) → fingerprint'e nasil dahil edilir?
- [ ] Rate-limit acisindan 200 trader x N period sorgusu = ~800 cagri; tek seferde mi yoksa batch+sleep mi?

---

## 8. Sonraki adim

Bu dokuman onaylanmis sayilirsa, kod tarafina geciyoruz: `pm_research/` paketi olusturulacak, ilk modul `sources.py` (httpx async + rate-limit + retry) + `leaderboard.py` (lb-api wrapper) yazilacak. Sonra `discover.py` ile aday havuzu uretilecek. Onaydan once kullaniciyla:
- Strategy seti (yukaridaki cohort filtresi yeter mi, ekleyelim mi?)
- Persistence (Parquet onerim — saglam, tipli, kolayca tekrar-okunur)
- Sync vs async (async kacinilmaz — 800 cagri sequential cok yavas)

konularinda kisa bir teyit istenecek.
