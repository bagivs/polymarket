# Sprint 01 — Trader Discovery & Analysis

## Hedef
Polymarket'ta tutarli kar eden hesaplari (insan ve bot) bul, **trade gecmislerini topla**, davranis verisinden **strateji parmak izi** (fingerprint) cikar.
Cikti, Sprint 02'de hangi stratejinin replike edilecegine karar verecek **veri ve raporu** ureteceK.

## Niye bu sprint?
Kor bir teorik MM modeline gomulmek yerine, gercekten para kazanan oyuncularin **ne yaptigini** anlayip, replike edilebilirlik + risk + getiri uclusunde en uygun olani secmek istiyoruz. (Karar: [ADR-004](../../DECISIONS.md))

## Kapsam

**Yapilacak:**
1. **Veri kaynaklarini haritala.** Polymarket data-api, Gamma API, Polygon RPC, Dune Analytics, The Graph subgraph — hangisi neyi veriyor, rate-limit'i ne, auth gerekli mi?
2. **Seed hesabi cozumle.** [@bonereaper](https://polymarket.com/@bonereaper?tab=activity) → on-chain wallet adresi. Username → address cozumu nasil yapilir?
3. **Aday hesap listesi olustur.** Seed'den genisleyerek (leaderboard, top-volume, on-chain whale akisi, sosyal ipuclari) en az **20** aday adres listele.
4. **Data collector yaz.** Verilen bir adres icin tum trade gecmisini (timestamp, market, side, size, price, maker/taker, fee, P&L) cek, lokal disk'e yaz.
5. **Aggregate metrikler.** Adres basina: trade sayisi, hacim, P&L egrisi, sharpe-benzeri, win-rate, market diversite, trade inter-arrival, side-balance, hold-time dagilimi, maker/taker orani, paired-trade (YES+NO) orani.
6. **Strateji fingerprinting.** Yukaridaki metrikler `PROJECT_CONTEXT.md §3.1`'deki kategorilere haritalanir: bu hesap **MM mi, arb mi, direksiyonel mi, karma mi**?
7. **Bulgu raporu.** `findings.md` — en az 5 adres icin profil + ortak desenler + Sprint 02 onerisi.

**Kapsam disi:**
- Order book / live WS bagisi (Sprint 04).
- Place/cancel order (Sprint 03).
- Cuzdan/auth altyapisi.
- Strateji replikasyonu (Sprint 02+).

## Cikti artifaktlari
- `pm_research/` — yeni Python paketi (sprint-01 boyunca yasayacak)
  - `sources.py` — API endpoint'leri tek dosyada, rate-limit + retry
  - `resolve.py` — username/slug → wallet address
  - `collect.py` — adres → trade history → Parquet
  - `metrics.py` — trade df → aggregate metrics
  - `fingerprint.py` — metrics → strateji kategorisi
  - `cli.py` — `uv run python -m pm_research collect <address>` gibi
- `data/traders/<address>/trades.parquet` (gitignore)
- `data/traders/<address>/summary.json` (gitignore)
- `notebooks/sprint-01-analysis.ipynb` — interaktif kesif (Jupyter)
- `docs/sprints/sprint-01-trader-discovery/findings.md` — final bulgu raporu (commit'lenir)
- `docs/sprints/sprint-01-trader-discovery/data-sources.md` — kaynak haritasi notu

## Kabul kriterleri
- [ ] En az 5 farkli veri kaynagi degerlendirilmis, en az 2'si bizim collector'umuzda kullanilan.
- [ ] @bonereaper'in cuzdan adresi cozulmus, trade verisi toplanmis.
- [ ] En az **20 aday adres** taranmis, 5+ tanesi detayli profillenmis.
- [ ] Her profillenmis adres icin: `summary.json` + dolu fingerprint + insan-okunur bir paragraf.
- [ ] `findings.md` raporu: bulgular + Sprint 02 icin somut **1 strateji onerisi**.
- [ ] Tum Python kodu `uv run pytest` ile en az smoke-test'ten geciyor.

## Acik sorular (sprint icinde netlesecek)
- Polymarket data-api / Gamma rate-limit'leri? Auth gerekli mi?
- Username (`@bonereaper`) cozumu hangi endpoint?
- "Kar" tanimi: net P&L mi, mark-to-market mi, realized only mi? (resolve olmus pozisyonlardan)
- Tarihsel pencere: son 30 gun, 90 gun, all-time?
- Bir hesap "bot mu" nasil anlasilir? (trade inter-arrival entropy + 24/7 aktiflik mi temel sinyal?)

## Notlar / referans
- Polymarket data API kesif baslangic: https://docs.polymarket.com/
- Polygon Polymarket exchange contract'i: data-sources.md'de toplanacak.
- The Graph / Dune Polymarket sorgulari topluluk repolarinda mevcut — once ara, sifirdan yazma.
- Veri buyukse Parquet zorunlu (Polars veya pyarrow). JSON sadece summary icin.

## Calisma modu
- Once `data-sources.md`'yi doldur (kod yazmadan).
- Sonra @bonereaper icin **end-to-end ince dilim**: 1 adres, 1 endpoint, 1 metrik kumesi. Insan-okunur ozet uret. **Once dogrula, sonra olcekle.**
- Olcekledikten sonra topluca 20+ adres icin batch tarama.
- Bulgulari `findings.md`'ye yaz, gerekirse PROJECT_CONTEXT §3 / §7'i guncelle.
