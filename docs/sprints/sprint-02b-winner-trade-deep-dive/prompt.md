# Sprint 02b — Winner Trade-Level Deep Dive

## Hedef
7 currently-winning hesabin **gercekten ne yaptigini** trade-level analizle çıkar. Yuzeysel fingerprint metrikleri yerine **her tek trade'in spesifik sınıflandırması** + sonucu üzerinden ortak pattern arıyoruz.

## Niye bu sprint var?
Sprint 02'de yuzeysel "6/7 sports favorite buy" pattern'i yanlis ilan edilmisti. Backtest gosterdi ki "buy favorite" Polymarket'ta negative EV. Demek ki ya kazananlar gercekten "favori al" yapmıyor (ben yuzeysel yorumladim) ya da daha incelikli bir is yapıyorlar (entry timing, market selection, vb.). Bu sprint o sorunun cevabini arıyor. (Methodology kuralı: [memory/no_strategy_invention](../../../.claude/projects/...))

## Kapsam

**Yapilacak:**
1. **Trade sınıflandırma:** her trader icin disk'teki trades.parquet'i yukle. Her trade icin:
   - Bought outcome (YES/NO) + entry price
   - Sınıflandır: "buy_favorite" (price > 0.55), "buy_underdog" (price < 0.45), "buy_neutral" (0.45-0.55)
   - Trade size USD
2. **Win/loss per trade:** her trade'in conditionId'sini gamma-api'dan resolution ile karşılaştır. Bought outcome resolved-to-1 ise WIN, 0 ise LOSS, hala open ise UNKNOWN.
3. **Per-trader aggregate:**
   - Trade dağılımı: %X favori, %Y underdog, %Z neutral
   - Per-bucket win rate (gercek karli oran)
   - Per-bucket gross PnL (size × outcome - cost)
4. **Market selection edge:** her trader'in baseline'a gore (rastgele "ayni fiyatta favori al" baseline) edge'i var mi?
5. **Timing patterns:** her trade icin entry timestamp vs event resolution timestamp arası — early-entry vs late-entry dağılımı + per-bucket pnl
6. **Ortak pattern:** 7 trader arasinda **en az 5'inde** tekrarlayan trade-level davraniş(lar)?

**Kapsam disi:**
- Yeni strateji icadı (ortak pattern bulunmadan TASLAK bile öneme)
- Backtest (Sprint 02'de zaten engine var; Sprint 02b'den çıkacak SOMUT pattern'i ileride backtest ederiz)
- Cuzdan/order placement

## Cikti artifaktlari
- `pm_research/winners.py` — trade-level classifier + market resolver + aggregator
- `data/winners/` — per-trader analiz parquet'leri (gitignore)
- `docs/sprints/sprint-02b-winner-trade-deep-dive/findings-deep-dive.md` — committed rapor
- (opsiyonel) Tum 7 trader icin `data/winners/<address>/trade_classification.parquet`

## Kabul kriterleri
- [ ] 7 trader x 3500 trade hepsi sınıflandırılmıs (favorite/underdog/neutral)
- [ ] Her trader icin gercek win rate per bucket hesaplanmis (en az %80 trade'lerin resolution'ı bulunabilmis)
- [ ] Market selection baseline ile karşılaştırma yapılmıs
- [ ] **Ortak pattern var mı yok mu** sorusu **kanıtla** cevaplanmıs
- [ ] Sonuca bagli **bir sonraki adim** önerilmiş (varsa Sprint 03 hazirligi, yoksa daha derin analiz veya stratejiye-baglanmama-kararı)

## Acik sorular (sprint sirasinda)
- 7 trader'in ortak conditionId'leri var mı? (ayni eventte birden cok trader bahis koymus mu?)
- Same-second clustering "burst execution" mi yoksa "tek pozisyonu bolerek market-impact'a girmemek" mi? (size dağılımıyla anlasilir)
- "Buy favorite" gozukenlerin gercekte ENTRY'leri eski (price dusukken alip price yukseldikten sonra trade'in entry price'i hala dusuk) mı?

## Notlar
- 7 hedef trader: surfandturf, swisstony, RN1, beachboy4, kch123, tdrhrhhd, gfjoigfsjoigsjoi (adresler: candidates_v2.parquet'da)
- Trades disk'te: `data/traders/<address>/trades.parquet` (3500 trade her birinde, son ~7-30 gun)
- Resolution: gamma-api/markets?condition_ids=cid (ya da cached sports_closed parquet'ten)
