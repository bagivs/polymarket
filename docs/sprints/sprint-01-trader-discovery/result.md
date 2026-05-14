# Sprint 01 — Trader Discovery & Analysis — Sonuc (review-ready)

> Sprint **kapanis aday** — tum kabul kriterleri karsilandi. Final karar `findings.md`'deki Sprint 02 secimi onayi.
> Detayli bulgular ve oneri: [`findings.md`](findings.md).

## Yapilanlar

### Arastirma fazi
- 4 farkli host probe edildi: `data-api`, `lb-api`, `gamma-api`, `clob`. Detay: [`data-sources.md`](data-sources.md).
- 11 endpoint dogrulandi (canli probe, ornek payload'lar). 5'i Sprint 01'de kullanilacak.
- Sektor referansi 2026: cuzdanlarin ~%7.6'si karli, top %1 karin %75'ini aliyor; arb firsatlari 2.7s'de yutuluyor.

### Gizli endpoint kesfi
- **`lb-api.polymarket.com/{profit,volume}`** — undocumented public leaderboard. `period=day/week/month/year/all`, `limit` veya `address`. **Hard cap: 50 sonuc** (limit ignored if >50, no offset/pagination).

### Kod
- `pm_research/` paketi olusturuldu:
  - `http.py` — async httpx client + per-host token-bucket rate limit (Cloudflare bucketinin %50'si) + tenacity retry/backoff.
  - `leaderboard.py` — lb-api wrapper (top-N, per-address).
  - `data_api.py` — data-api wrapper (trades, positions, closed_positions, activity, value).
  - `discover.py` — multi-period leaderboard fetch + dedup + cohort labeling.
  - `cli.py` + `__main__.py` — `uv run python -m pm_research discover`.

### Ilk discovery snapshot (2026-05-14)
7 leaderboard cagrisi (5 profit period + 2 volume period) → 350 long-form satir → **86 unique aday wallet**.

| Cohort | n | Tanim | Ortalama yıl profit | Ortalama ay volume |
|---|---|---|---|---|
| `recent_oneshot_winner` | 50 | Tum profit window'larda > $5K, ama profit_year < 3×profit_week (yani tum kar son haftada cikti) | $4.75M | $107M |
| `market_maker_candidate` | 36 | Aylik volume > $1M, marjin < %0.5 | $0 | $298M |
| `sustained_winner` | 0 | year ≥ 3×week + her window'da > $5K | — | — |

**Onemli bulgular:**
1. Bugunku top-50 kar listesi tamamen son haftaki winner'lar — **uzun-vadeli sustained winner yok bu snapshot'ta**. "Sustained" tespiti icin gunluk snapshot serisi (multi-day) veya per-trader closed-positions zaman serisi gerek.
2. MM aday'lari ortalama $300M/ay volume + sifir net P&L (ya da P&L < %0.5 marjin) — klasik HFT MM profili.
3. Top 5 recent winner: Theo4 (+$22M), Fredi9999 (+$16.6M), kch123 (+$12.6M), RN1 (+$8.9M), Len9311238 (+$8.7M). Bircogunda volume_month=0 → demek ki kar kapali pozisyonlardan/redemption'dan, surekli trading'den degil.

### Cikti artifaktlari
- `data/leaderboard/2026-05-14_leaderboard_long.parquet` (gitignore — 350 satir, raw long-form)
- `data/leaderboard/2026-05-14_candidates.parquet` (gitignore — 86 satir, cohort'lu)

## Sapmalar
- Plan: 20+ aday hedeflenmisti → 86 toplandi (4x ustte).
- Plan: cohort kategorileri 3 idi → 4 oldu (`recent_oneshot_winner` eklendi: ilk run'da "sustained" cikan herkes aslinda son hafta kazanani idi, ayri kategori sart).
- @bonereaper resolve edilmedi — leaderboard ile gereksizlesti, dokumante edip pas gectik.

## Verilen kararlar (kod-icindeki tercihler)
- Per-host rate limit token-bucket (`aiolimiter`) + tenacity retry. **ADR-006 olarak DECISIONS.md'ye yazilmali** (sonraki commit).
- Persistence: **Polars + Parquet** — uv ile `polars` + `pyarrow` eklendi.
- HTTP: `httpx.AsyncClient`, http2 yok (h2 dep eklemedik).

## PROJECT_CONTEXT.md guncellemeleri
- §3.3 (sektor referans bulgulari) eklendi — bossoskil1 anekdotu dahil.
- §3.1/3.2 reverse-engineer-first cercevesine uydu.

## Per-trader deep-dive (5 MM + 5 oneshot, top by ranking metric)
- `pm_research/profile.py` — async per-trader bulk fetch (trades + closed + open + value).
- `pm_research/metrics.py` — fingerprint hesaplari (trade rate, side balance, market diversity, inter-arrival, paired-event clustering, realized PnL — caveat'larla).
- 10 hesabin per-trader Parquet'leri + fingerprint.json + cohort agregasyonu disk'te (`data/traders/`).
- Smoke testler (6/6 PASS): import, fingerprint logic, cohort summary, mocked HTTP wrappers.

## Onemli teknik bulgular (Sprint 02+ icin onemli)
- `closed_positions` API'si **yalnizca top-50 winning** pozisyon donduruyor — win-rate/cumulative-PnL trade-history'den hesaplanmali. Bossoskil1 sanity check ile dogrulandi.
- `data-api/trades` offset 3000'de hard cap → lifetime trade history erisilemez, 3500 satir sample yeterli archetype tespiti icin.
- Fingerprint'in en ayirt edici sinyalleri: `buy_ratio` (OS=1.0 vs MM=0.61) ve `same_second_trade_pct` (OS=36% vs MM=8.8%).

## Sonraki adim — KULLANICI ONAYI BEKLENIYOR
- `findings.md` Sprint 02 icin **3 opsiyon**, **Opsiyon A (long-shot scalper)** onerisi sundu.
- Kullanici onay verirse Sprint 02 acilir; reddederse opsiyonlar tartisilir.
