# Sprint 03 V1 — Copy-Trade Tracker (Read-Only)

## Hedef
0x492442EaB ve secilmis 1-2 ek winner'i **gercek-zamanli izlemek**, her yeni trade'lerini disk'e log'lamak, **bizim copy-trade'imiz olsa ne yapardik** simulasyonunu paralel kayitla yurutmek. **HIC GERCEK ORDER YOK** — sadece veri toplama.

## Niye bu sprint?
Sprint 02b'de 22 sport trader analizi sonucu **tek istatistiksel olarak anlamli edge** 0x492442EaB'de cikti (NBA spread @ ~$0.50, 85% win rate, n=232, 10+ sigma). Backtest copy-trade simulasyonu **lag<5dk + 300bps slippage'da +52% ROI** gosterdi. Live read-only tracker bu cikarimı dogrulayacak — 1 hafta calisan loop, gercek trade verisi + gercekten copy-yapsak ne ROI gorurduk simulasyonu.

## Kapsam

**Yapilacak:**
1. **Tracker module** (`pm_research/tracker.py`) — N adresi her 5 saniyede polla (data-api/trades), yeni trade'leri JSONL log'a yaz.
2. **CLI subcommand** `track` — adresler CLI'dan veya config dosyasindan, log dir, poll interval.
3. **Restart-tolerant state** — kaldigi yerden devam (last seen tx_hashes diskte).
4. **CLOB price enrichment** (opsiyonel V1+) — yeni trade gelince anlık book/midpoint cek; bizim copy-trade'imizin entry'si o fiyat olur, simulated PnL kayit.
5. **1 hafta calisma + gözlem** — günlük log'lar `data/tracker/trades_YYYYMMDD.jsonl`, haftalık özet üretimi (basit script).
6. **Sprint 03 V1 sonuc raporu** — gozlem hafta sonunda: kac trade detected, lag dağılımı, simulated copy-PnL.

**Kapsam disi:**
- Gercek order placement (V2 Sprint 03'te yer alacak)
- Cuzdan/CLOB auth (sadece read-only public API)
- ExecutionClient implementation
- RiskGuard

## Cikti artifaktlari
- `pm_research/tracker.py` — async polling tracker
- CLI: `uv run python -m pm_research track --addresses 0x... --poll 5 --log-dir data/tracker`
- `data/tracker/trades_YYYYMMDD.jsonl` — ham trade log
- `data/tracker/state.json` — restart state
- `docs/sprints/sprint-03-copy-trade-tracker/findings-tracker-week1.md` — 1 hafta sonu gozlem raporu
- `docs/sprints/sprint-03-copy-trade-tracker/winner-trade-lists.md` — top 10 winner'in son 30-50 trade'i, kullaniciya gorulebilir referans

## Kabul kriterleri
- [ ] Tracker module yazılı + smoke testte calisiyor (10 sn / 1 adres / >=1 trade detected veya boş ama temiz)
- [ ] Restart-tolerant: kapatip aynı state ile yeniden çalıştırınca yeni trade'ler doğru log'lanir
- [ ] CLI ile arka planda (nohup ya da systemd) calistirilabilir
- [ ] 1 hafta calisma sonrasi en az 50 trade detected; haftalik ozet hesaplanabilir
- [ ] Simulated copy-PnL hesabı ile karşılaştırma (theirs vs ours @ X lag) yapilir

## Acik sorular
- Hedef adres listesi: 0x492442EaB tek mi, yoksa 2-3 ek (ornek RN1, surfandturf) eklensin mi? Fazlali = daha cok sample ama gurultü artıyor.
- Poll interval 5s yeterli mi? data-api /trades 20 r/s rate limit; 3 adres × 1 call/poll × 0.2 r/s OK.
- Log format: JSONL (kolay tail/grep) vs Parquet (efficient analiz). JSONL once, week sonu Parquet konversiyonu.
- CLOB price enrichment ne zaman: V1'de mi V1.5'ta mı?

## Calisma modu
1. Yaz `tracker.py` minimal versiyon → smoke
2. CLI ekle
3. 1 saat foreground test (sample veri görme)
4. Sonra arka planda 24/7 calistirma
5. Hafta sonunda findings raporu
