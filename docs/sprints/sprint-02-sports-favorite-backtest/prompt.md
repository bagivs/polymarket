# Sprint 02 — Sports Favorite Strategy: Backtest

## Hedef
Sprint 01'de gozlemlenen "BUY favori takim YES + hold to resolution" pattern'ini Polymarket'in **resolved** spor pazarlarinin gercek datasıyla **backtest** edip viable olup olmadigini ölç. Sonuc yesilse Sprint 03'te canli kanarya, kirmiziysa Yon II (klasik MM) fallback.

## Niye bu strateji?
[`../sprint-01-trader-discovery/findings.md §9`](../sprint-01-trader-discovery/findings.md) — top-7 currently-winning trader'in 6'sı bu pattern'i kullaniyor: surfandturf, beachboy4, kch123, RN1, swisstony, gfjoigfsjoigsjoi. Edge: spor pazarlarinda **favorite/longshot bias** (favori takima sistematik underpricing). [ADR-007](../../DECISIONS.md).

## Kapsam

**Yapilacak:**
1. **Veri katmani:** gamma-api ile resolved spor pazarlari (kategori filtresi + closed=true) listele. Her pazar icin: kategori, takimlar, resolution, **entry-time price**, en az son N saatlik trade hacmi/derinlik proxy'si.
2. **Backtest engine:** parametrik strateji. Giris esigi (P(YES) in [low, high]), pozisyon boyutu policy, hold-to-resolution exit, fee + slippage modellemesi.
3. **Variations grid search:**
   - Esik araligi: 0.50-0.85, 5 farkli kombinasyon
   - Spor kategorisi: futbol / basketbol / tenis / hokey / NBA / NFL / soccer ayrimi
   - Position size: sabit / Kelly / fractional Kelly
   - Entry timing: resolution'dan N saat once; N = {1, 6, 24, 168}
4. **Slippage modeli:** burst-execution patterns'a benzer 5-30 fill'e bolme, her fill icin tahmini price impact (orderbook depth proxy ile)
5. **Cikti:** her config icin net return, sharpe, max drawdown, win rate, per-sport breakdown — `findings-backtest.md`'ye yazilir.
6. **Karar:** En iyi config'in net return >5%/ay (gas + fee dahil) → Sprint 03 GO. Yoksa Sprint 03 fallback (Yon II klasik MM).

**Kapsam disi:**
- Live order placement (Sprint 03)
- Cuzdan altyapisi (Sprint 03)
- WS feed (Sprint 04)
- Tradeplay/replay simulator (gerekirse Sprint 02'nin son fazinda)

## Cikti artifaktlari
- `pm_research/markets.py` — gamma-api wrapper (markets endpoint + filtering + categories)
- `pm_research/backtest.py` — backtest engine + config grid
- `data/markets/` — cekilen resolved sports markets parquet'leri (gitignore)
- `data/backtest/` — sonuc parquet + json'lari (gitignore)
- `docs/sprints/sprint-02-sports-favorite-backtest/findings-backtest.md` — committed rapor
- `docs/sprints/sprint-02-sports-favorite-backtest/data-sources-v2.md` — gamma-api sport-market spesifik notlar

## Kabul kriterleri
- [ ] En az **1000 resolved sport market** datasi cekilmis
- [ ] En az **8 farkli parametre kombinasyonu** backtest edilmis
- [ ] Per-sport-kategori breakdown raporlanmis
- [ ] Slippage modeli somut bir formul/kalibrasyona dayanir (sabit %X degil)
- [ ] Net return + sharpe + max drawdown her config icin acik
- [ ] **Sprint 03 GO/NO-GO karari** veriyle desteklenip yazilir
- [ ] `uv run pytest` smoke + en az 2 backtest engine integration test gecer

## Acik sorular (sprint sirasinda netlesecek)
- gamma-api kategori taksonomisi nasil? "category" alani mi var, "tags" mi? "Sports" subkategorileri (NFL, NBA, EPL, vs.) ayrı listelenir mi?
- Resolved market icin son trade fiyati gamma-api'da mi yoksa data-api/trades'de mi?
- Polymarket fee yapisi — maker/taker, gas, USDC transferi?
- Order book depth tarihsel veride var mi yoksa proxy ile (avg trade size'a gore) mi modellemek gerekiyor?
- Slippage icin gercek validation: birkac canli market icin bizim modelimizin tahmini vs gercek fill'leri karsilastir
- Bias kontrol: bizim 7-trader sample'inda spor-favori dominant cikti — ama _baska_ winner stratejileri de var olabilir (tdrhrhhd long-shot SELL gibi). En az 1 alternatif strateji ile ucu karsilastirmali mi?

## Notlar / on-okumalar
- Sports betting "favorite/longshot bias" referansi: Snowberg & Wolfers (2010) "Explaining the favorite-longshot bias"
- Polymarket Gamma API: https://docs.polymarket.com/api-reference/gamma
- 7-trader fingerprint: [`../sprint-01-trader-discovery/findings.md §9.3-9.4`](../sprint-01-trader-discovery/findings.md)

## Calisma modu
1. Once **veri kesfi** — gamma-api'da hangi alanlar var, kac resolved spor market var, nasil paginate edilir? (kod yazmadan probe)
2. Sonra **backtest iskeleti** — tek market icin end-to-end ince dilim (1 market, 1 config, 1 ROI)
3. Sonra **batch + grid** — 1000+ market x 8+ config
4. Sonra **rapor** — findings-backtest.md, GO/NO-GO karari
