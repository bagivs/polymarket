# Sprint 00 — Bootstrap & Brainstorm

## Hedef
1. Proje iskeletini kurmak (uv venv, docs/, sprint dongusu).
2. Kullanici + Claude arasinda strateji + kapsam beyin firtinasi yapip cikti `PROJECT_CONTEXT.md`'ye yansitmak.
3. Kalici ilk kararlari `DECISIONS.md`'ye yazmak.

## Kapsam
**Yapilacak:**
- `uv` ile Python 3.12 venv kurulumu (done).
- `docs/` iskelet: CLAUDE.md, README, PROJECT_CONTEXT, DECISIONS, GLOSSARY, sprints/ (done).
- Asagidaki sorulari kullaniciyla netlestirme — cevaplari ust dokumantasyona islet.

**Kapsam disi:**
- Kod yazimi (sprint-02'den itibaren).
- Polymarket'a baglanti / API testleri (sprint-01).

## Cevaplanmasi gereken sorular (sprintin asil isi)
Bunlari kullaniciyla tartis, cevaplari `PROJECT_CONTEXT.md` ilgili bolumlerine yaz:

### Vizyon ve olcek
- [ ] Hedef sermaye (kanarya / V1 / V2)?
- [ ] Tek-makineli mi calisacak? Lokasyon onemli mi (AWS region)?
- [ ] Kullanici lokasyon/regulasyon kisitlamasi var mi (US/UK Polymarket erisimi)?

### Strateji oncelikleri
- [ ] V1'de hangi strateji once: pasif MM mi, YES+NO arb mi, ikisi paralel mi?
- [ ] Hangi market kategorileri (politika / spor / kripto / makro)? Liste cikar.
- [ ] Hedef market sayisi (5 mi, 20 mi, 100 mu)?

### Risk profili
- [ ] Max gross USDC pozisyonu?
- [ ] Gunluk max drawdown (% veya $)?
- [ ] Tam-otomatik mi, yoksa "her gun manuel onay" gibi human-in-loop mu?

### Teknik tercihler
- [ ] Veri persist: SQLite mi, Parquet mi, ikisi mi?
- [ ] Async framework: vanilla `asyncio` + `aiohttp`/`websockets` mi, `anyio` mi?
- [ ] Logging: `loguru` mu, stdlib `logging` mi?
- [ ] Backtest: kayitli WS replay yeterli mi, ayrica simulator gerekli mi?

### Operasyon
- [ ] Wallet yonetimi: dosyada hot key mi (encrypted)? KMS? hw-wallet?
- [ ] Monitoring/alarm kanali (Telegram / Discord / email)?
- [ ] Kullanici gun icinde ne sikkikta dashboard'a bakar — gercek-zamanli mi, gunluk ozet mi?

## Kabul kriteri
- [x] uv venv kurulu, `uv run python --version` calisiyor
- [x] `docs/` iskelet hazir, `CLAUDE.md` entry-point yazildi
- [ ] Yukaridaki sorularin en az %80'i cevaplandi ve `PROJECT_CONTEXT.md`'ye islendi
- [ ] En az 3 yeni ADR yazildi (uv + docs disinda)
- [ ] `result.md` doldurulup sprint 🟢 olarak isaretlendi

## Notlar / on-okumalar
- Polymarket docs: https://docs.polymarket.com/
- py-clob-client: https://github.com/Polymarket/py-clob-client
- Avellaneda-Stoikov referans: "High-frequency trading in a limit order book" (2008)
