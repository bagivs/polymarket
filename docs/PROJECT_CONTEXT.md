# PROJECT_CONTEXT — Polymarket HFT Bot

> **Proje beyni.** Hedefler, kapsam, mimari, stratejiler, riskler.
> Sprint sonlarinda + her kalici karardan sonra gozden gecir. Eskiyen bilgiyi sil.
> Son guncelleme: 2026-05-14 (Sprint 00 oncesi iskelet)

---

## 1. Vizyon ve hedef

### 1.1 Tek cumlede vizyon
Polymarket CLOB'da, dusuk operasyonel maliyetli, denetlenebilir bir piyasa-yapici + arbitraj botu calistirmak; spread ve yanlis fiyatlamalardan tutarli getiri elde etmek.

### 1.2 Yaklasim: kopyala-once, icat-sonra
Strateji **once kazanan botlardan reverse-engineering** ile cikartilacak; sifirdan teori-tasarim ile baslamiyoruz. Ornek seed hesap: [@bonereaper](https://polymarket.com/@bonereaper?tab=activity). Sprint 01 bu hesaplari bulup verilerini toplamaya ayrildi.

### 1.3 Basari kriteri (ilk surum)
*V1 hipotezleri (analiz sonucu netlesecek):*
- En karli 3–5 hesabin strateji parmak izi cikartilmis (MM / arb / direksiyonel ayrimi).
- Bu stratejilerden en az birinin replikasyonu simulasyonda pozitif net P&L (gas + fee dahil).
- Sonra kanarya sermaye ile live.

### 1.4 HFT tanimi (bu projede)
Polymarket *gercek* HFT degil (mikrosaniye degil). Bizim icin "HFT" = saniye-alti reaksiyon, otomatik order yonetimi, surekli kotasyon. Mikrosaniye gecikme optimizasyonu **kapsam disi**.

### 1.5 Operasyonel cerceve
- **Donanim:** Tek makine. Coklu region / dagitik calisma kapsam disi.
- **Regulasyon:** Kisitlama yok (kullanici beyan etti).
- **GitHub:** Tum repo islemleri (commit / branch / PR / issue) Claude tarafindan yapilir. Repo: https://github.com/bagivs/polymarket

---

## 2. Polymarket platform notlari (HFT acisindan)

> Detayli terimler: [GLOSSARY.md](GLOSSARY.md). Burasi **yatirim alan** notlari.

- **CLOB (Central Limit Order Book)**: Polymarket'in kendi off-chain matching engine'i + on-chain settlement (Polygon).
- **Pazar yapisi**: Her market = ikili sonuc (YES/NO). Her sonuc icin ayri **conditional token** (ERC-1155).
- **Fiyat invariant'i**: `P(YES) + P(NO) = 1$` (USDC). Sapma → arbitraj firsati.
- **Settlement**: USDC, Polygon. Order imzasi EIP-712.
- **Auth**: L1 (Ethereum private key, on-chain) + L2 (API key/secret, off-chain CLOB).
- **Rate limit**: Resmi limitler `docs.polymarket.com`'da — sprint-01'de net cikarilacak ve burada listelenecek.
- **Resmi client**: [`py-clob-client`](https://github.com/Polymarket/py-clob-client) (REST + WS).

### 2.1 Cevaplanmasi gereken sorular (Sprint 00 backlog)
- [ ] Min order boyutu? Min tick size?
- [ ] Maker rebate var mi? Taker fee yapisi?
- [ ] WebSocket order-book full-depth mi, top-of-book mu?
- [ ] Cancel/replace tek istek mi, iki istek mi?
- [ ] Self-trade prevention var mi?
- [ ] Gerekli on-chain operasyonlar (allowance, deposit, withdraw) kac gas?

---

## 3. Strateji portfoyu

> **Yaklasim degisti:** Bizim teori-once strateji listemiz **aday hipotezler**. Gercek hedef strateji Sprint 01'de karli botlardan reverse-engineering ile cikartilacak. Asagisi sadece arama yaparken aklimizda olacak kategoriler:

### 3.1 Aday kategoriler (parmak izi referansi olarak)
- **Pasif market making**: cift-tarafli kotasyon, yuksek cancel oranı, envanter-duyarli skew.
- **YES+NO arbitraj**: P(YES) + P(NO) ≠ 1 sapmalarinda paired trade.
- **Order-book imbalance**: depth orani ile aktif fiyat kaymasi.
- **Korelasyonlu market stat-arb**: ayni olayin farkli marketleri arasinda.
- **Resolusyon-once decay**: bilinen-sonuca yakin pozisyonlar.
- **Haber/sinyal tabanli direksiyonel**: olay tetiklemesiyle yon alma.

### 3.2 Hedef strateji secimi
Sprint 01 ciktisindan **3.1**'deki kategorilerin her birine "var/yok, hangi hesaplarda, ne agirlikta" haritasi cikar. Sprint 02'de en uygun (replike edilebilirlik + getiri + risk) strateji secilir.

### 3.3 Sektor referans bulgulari (2026)
- Polymarket cuzdanlarinin sadece **~%7.6**'si karli; top %1 karlarin **%75**'ini aliyor. Asimetri yuksek. (FA Magazine 2026 raporu)
- 4 yasayan bot strateji: (1) Pasif MM ($10K + ~0.5–2%/ay), (2) AI prob. arb (3–8%/ay, %65–75 win), (3) Korelasyon/logical arb (2–5%/ay, %70–80 win), (4) HFT momentum (8–15%/ay, %60–70 win, MaxDD ~%9). (Medium 2026 yazisi)
- Arbitraj firsatlari ortalama **2.7 sn**'de yutulup gidiyor (2024'te 12.3 sn'di). Sub-100ms execution **profit'lerin %73**'unu aliyor.
- **Leaderboardlar yaniltici**: polymarket.com'da #1 olan `bossoskil1` bu ay **-$2.23M zararda**. Sustained profit icin **multi-period kesisim** (week + month + year ust ust) sart.

---

## 4. Mimari (taslak)

> Sprint 02'de kod baslangiciyla netlesir. Asagisi **kavramsal**.

```
                ┌───────────────────────────────────────────┐
                │   Polymarket CLOB (REST + WS)             │
                └───────────────┬───────────────────────────┘
                                │
                  ┌─────────────┴─────────────┐
                  │   MarketDataFeed (async)  │  ← WS bagli, order-book + trade akisi
                  └─────────────┬─────────────┘
                                │  in-mem snapshot
                  ┌─────────────┴─────────────┐
                  │   StrategyEngine          │  ← sinyal + hedef pozisyon hesabi
                  │   (MM / Arb plug-in'leri) │
                  └─────────────┬─────────────┘
                                │  hedef order'lar
                  ┌─────────────┴─────────────┐
                  │   OrderManager            │  ← gercek order'larla diff al, place/cancel
                  └─────────────┬─────────────┘
                                │
                  ┌─────────────┴─────────────┐
                  │   ExecutionClient         │  ← py-clob-client wrapper, rate-limit, retry
                  └───────────────────────────┘

  Yan servisler:
  - RiskGuard (pozisyon, drawdown, kill-switch)
  - Persistor (SQLite/Parquet — fills, P&L, latency)
  - Metrics (Prometheus expo? — sprint-03)
```

### 4.1 Bilesen sorumluluklari (one-liner)
- **MarketDataFeed**: WS bagli, sira numarasi takibi, snapshot+delta yonetimi.
- **StrategyEngine**: Saf fonksiyon — state + market data → hedef quote'lar. Yan etki yok.
- **OrderManager**: Hedef → fiili order diff. Idempotent. Çift-place koruma.
- **ExecutionClient**: I/O sinir. Tum CLOB API cagrilari burada. Retry/backoff.
- **RiskGuard**: Sert limitler. Asilirsa kill-switch tetikler.

---

## 5. Risk yonetimi (sert kurallar)

> Bu boluk uzerinde tartismadan kod yazma. Sprint 00'da netlestir.

- **Max gross pozisyon** (USDC) — TBD.
- **Market basina max net pozisyon** — TBD.
- **Gunluk max drawdown** → kill-switch (otomatik tum order iptal, yeni order yok).
- **Manuel kill-switch**: dosya bayragi veya CLI komutu ile aninda durdurma.
- **Self-DoS koruma**: rate-limit'in %70'ini gecme.
- **Heartbeat**: WS kopukluk → 5 sn icinde tum acik order iptal + yeniden baglan.
- **Cuzdan ayrimi**: Trade cuzdani != ana cuzdan. Sadece gerekli USDC + gas yatirilir.

---

## 6. Veri ve gozlemlenebilirlik

- **Kalici veri**: her fill, her order state degisikligi, her quote → Parquet (gunluk dosya) veya SQLite (sprint-02 karar).
- **Loglar**: structured JSON, `loguru` veya stdlib. PII/secret yazilmaz.
- **Metrikler**: latency (decision→ack), inventory, P&L, hit-rate, cancel-ratio. Once stdout, sonra Prometheus + Grafana (opsiyonel).
- **Backtest/replay**: kayitli WS akisindan offline replay yapilabilmeli.

---

## 7. Open questions / brainstorm backlog

Cevap geldikce ust bolumlere tasi:

**Cevaplandi:**
- ✅ Tek-makine — coklu region kapsam disi.
- ✅ Regulasyon endisesi yok.
- ✅ GitHub: tum islemler Claude tarafindan, repo https://github.com/bagivs/polymarket.
- ✅ Yaklasim: reverse-engineer-first.

**Hala acik:**
- [ ] Hedef sermaye buyuklugu (kanarya / V1 / V2)?
- [ ] Hangi market kategorileri oncelik (politika / spor / kripto / makro)?
- [ ] Max gross USDC pozisyonu? Gunluk max drawdown?
- [ ] Tam-otomatik mi, gun basi manuel onay mi?
- [ ] Wallet: hot key encrypted dosya mi, KMS, hw-wallet?
- [ ] Monitoring/alarm kanali (Telegram / Discord)?
- [ ] Veri persist: SQLite mi, Parquet mi?
- [ ] Logging: `loguru` mu, stdlib `logging` mi?
- [ ] Simulator gerekli mi, replay yeterli mi?

---

## 8. Yol haritasi (kaba sprint listesi)

| Sprint | Hedef | Cikti |
|---|---|---|
| 00 | Bootstrap + ilk brainstorm | 🟢 docs/ iskelet, ADR-001..005, sprint dongusu kuruldu |
| 01 | Trader Discovery & Analysis | 🟢 86 aday → user-pnl-api enrich → 22 currently-winning. Top-7 fingerprint: 6/7 **sports-favorite burst-buy** pattern |
| 02 | **Sports Favorite Strategy backtest** | Resolved spor pazarlarinda BUY-favorite + hold simulasyonu; Sprint 03 GO/NO-GO bu sprintten |
| 03 | ExecutionClient + canli kanarya **(Sprint 02 + ise)** | py-clob-client wrapper, place/cancel, kucuk sermaye live test. Sprint 02 - olursa Yon II MM fallback. |
| 04 | MarketDataFeed | WS bagli, in-mem order book, replay kayit |
| 05 | StrategyEngine + RiskGuard | Sprint 02'de validate edilen strateji + simulator |
| 06 | Olcek + monitoring | Production-ready, dashboard, alarm |

> Bu plan **iskelet**. Her sprint sonunda gozden gecir. Sprint 02+ Sprint 01 bulgularina gore yeniden sirayalanabilir.
