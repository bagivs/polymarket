# Polymarket HFT Bot — Claude Code Entry Point

> Bu dosya her sohbetin basinda **otomatik** yuklenir. Burada **karar verme** — sadece nereye bakacagini soyle.

## Proje ozeti tek cumlede
Polymarket (Polygon uzerinde tahmin piyasasi) icin Python tabanli yuksek-frekansli ticaret botu. Once piyasa-yapici (market-maker) ve Yes/No arbitraji, sonra istatistiksel ve haber tabanli stratejiler.

## Once oku (sirayla)
Her yeni conversation'da once **bu uc dosyayi** oku, sonra calismaya basla:

1. [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md) — **Proje beyni.** Hedefler, kapsam, mimari, stratejiler, riskler. Bu dosya guncel kalir.
2. [docs/DECISIONS.md](docs/DECISIONS.md) — Verilmis teknik kararlar (ADR formatinda). "Neden bu sekilde?" sorusunun cevabi.
3. [docs/sprints/README.md](docs/sprints/README.md) — Aktif/tamamlanmis sprint listesi. Hangi sprintteyiz, ne yapildi, sirada ne var?

Sonra ihtiyac olursa:
- [docs/GLOSSARY.md](docs/GLOSSARY.md) — Polymarket terimleri (CLOB, conditional token, vs.)
- [docs/sprints/sprint-NN-xxx/](docs/sprints/) — Aktif sprintin prompt + result dosyalari
- [https://docs.polymarket.com/](https://docs.polymarket.com/) — Polymarket'in resmi dokumani (API)

## Calisma akisi (kurallar)

### Sprint dongusu
Her sprint = bir klasor: `docs/sprints/sprint-NN-kisa-isim/`
- `prompt.md` — Sprintin hedefi, kapsami, kabul kriterleri. Sprint **basinda** yazilir.
- `result.md` — Ne yapildi, hangi kararlar verildi, sapmalar, ogrenilenler. Sprint **bittiginde** doldurulur.
- Sprint icinde alinan kalici teknik kararlar `DECISIONS.md`'ye, mimari/strateji guncellemeleri `PROJECT_CONTEXT.md`'ye yansitilir.

### Brainstorm modu vs. kod modu
- Kullanici acikca **"kod yazalim" / "implement et"** demediyse → kod yazma. Sadece tartis, plan cikar, `PROJECT_CONTEXT.md`'yi guncelle.
- Kod modunda bile: yeni bir dosya/klasor olusturmadan once `PROJECT_CONTEXT.md`'deki mimariye uydugundan emin ol.

### Dokuman guncelleme
- Bir karar `DECISIONS.md`'ye yazildiysa, ilgili bolum `PROJECT_CONTEXT.md`'de de guncellenir (cift-kayit kabul, tek-kaynak gercek = DECISIONS.md).
- Eskimis bir bilgi gorursen **sil veya guncelle**, "TODO eski" diye birakma.

### Dil
Tum dokuman ve kullanici iletisimi **Turkce**. Kod icindeki yorum/log/identifier **Ingilizce** (endustri standardi, sonradan paylasilabilir).

## Teknik yigin (ozet — detay PROJECT_CONTEXT.md'de)
- Python 3.12, `uv` ile bagimlilik yonetimi
- Polymarket CLOB icin `py-clob-client` (resmi)
- Async io: `asyncio` + `websockets` / `aiohttp`
- Veri: `polars` veya `pandas` (sprint-2'de karar)
- Test: `pytest`, `pytest-asyncio`

## Calisma ortami
```bash
# Sanal ortami aktive et
source .venv/bin/activate
# Bagimlilik ekle
uv add <paket>
# Calistir
uv run python <script>.py
```

## Ne YAPMA
- `requirements.txt` olusturma (uv `pyproject.toml` + `uv.lock` kullaniyor).
- Sprint klasoru disinda gecici/draft markdown atma. Gecici notlar konusma icinde kalsin.
- Gercek API key, private key, mainnet adres `.env` disindaki hicbir yerde gozukmesin. `.env.example` her zaman placeholder ile.
- Mainnet'te otomatik trade calistirma — sadece kullanici acikca onay verdiginde.
