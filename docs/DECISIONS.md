# DECISIONS — Architectural Decision Records

> Tek-yonlu kayit. Yeni karar = yeni satir (ADR). Eski kararlari **silme**, "superseded by ADR-NNN" diye isaretle.
> Format kisa: 1 paragraf neden, 1 paragraf ne, 1 paragraf alternatifler.

---

## ADR-001 — Bagimlilik yonetimi: `uv`
**Tarih:** 2026-05-14
**Durum:** Kabul

**Neden.** Hizli kurulum, deterministik kilit dosyasi (`uv.lock`), `pyproject.toml` ile tek-kaynak. Pip + venv'den belirgin hizli; conda agirligi gereksiz.

**Ne.** `uv init` + `uv venv` ile proje kuruldu. Bagimlilik ekleme `uv add <paket>`. Calistirma `uv run`. Python 3.12 sabit (`.python-version`).

**Alternatifler.** poetry (yavas), conda (data-science odakli, ag agir), pip+venv (deterministik degil). uv hepsinden iyi.

---

## ADR-002 — Dokuman tabanli hafiza (`docs/`)
**Tarih:** 2026-05-14
**Durum:** Kabul

**Neden.** Claude'un konusma hafizasi geciciligi var. Mimari/strateji kararlari, sprint geciskeni kalici tutulmali. Git ile versiyonlanir, insan-okur.

**Ne.** Tum kalici proje bilgisi `docs/` altinda markdown. `CLAUDE.md` repo kokunde — her conversation'da otomatik yuklenir, hangi dosyalari okumasi gerektigini soyler. Sprint dongusu: `docs/sprints/sprint-NN-isim/{prompt,result}.md`.

**Alternatifler.** Obsidian vault (insan icin guzel, Claude icin gereksiz katman), Notion (gizli/uzak, code-pair'e zor), JSON metadata (insan okumaz). Markdown + git = en az surtunme.

---

## ADR-003 — Iletisim ve kod dili
**Tarih:** 2026-05-14
**Durum:** Kabul

**Neden.** Kullanici Turkce calisiyor; ekipsiz solo proje. Ama kod paylasilabilir/portatif olmali.

**Ne.** Tum dokuman + kullanici-AI iletisim **Turkce**. Kod icindeki identifier, yorum, log, commit mesaji **Ingilizce**. Sprint adlandirma `kebab-case-en`.

**Alternatifler.** Hepsi Turkce (kod portatif degil), hepsi Ingilizce (kullanici akiciligi dusuk). Karma cozum optimal.

---

## ADR-004 — Reverse-engineer-first strateji yaklasimi
**Tarih:** 2026-05-14
**Durum:** Kabul

**Neden.** Polymarket'ta hangi stratejilerin gercekten kar ettigi onceden bilinmiyor. Teoride iyi gorunup pratikte zarar eden seyler sik (likidite, fee, slippage). Karli hesaplarin davranisi gercek ground-truth.

**Ne.** Sprint 01 tamamen karli hesap kesfine + on-chain/API verisinden trade-history toplamaya + strateji parmak izi cikartmaya ayrildi. Replikasyon hedefi Sprint 02'de bu bulgulardan secilir. Avellaneda-Stoikov ve diger akademik referanslar sadece **fingerprint kategori** olarak kullanilacak, baslangic hipotezi olarak degil.

**Alternatifler.** Teori-once (akademik MM modeli ile basla — riski yuksek), greenfield-deneme (kuc sermaye ile dene-ogren — yavas ve sermaye yakar). Reverse-engineer en hizli ogrenme yolu, sermaye riski sifir.

---

## ADR-005 — Tek-makine operasyon, GitHub akisi Claude'de
**Tarih:** 2026-05-14
**Durum:** Kabul

**Neden.** Kullanici tek-makineli calisma + Claude'un tum repo islemlerini yurutmesini istiyor. Coklu region/dagitik gereksinim yok.

**Ne.** Tum bot tek bir Linux makinede calisir; lokasyon optimizasyonu, multi-region failover **kapsam disi**. Git/GitHub islemleri: commit, branch, push, PR, issue, release **Claude tarafindan** yapilir. Destructive operasyonlar (force push, branch silme, vb.) icin kullanici onayi alinir. Repo: `github.com/bagivs/polymarket`.

**Alternatifler.** Cok-makine (gereksiz karmasiklik), elle git (yavas iteration). Mevcut secim solo proje icin optimal.

---

## ADR-006 — HTTP istemcisi: httpx + aiolimiter + tenacity, Polars + Parquet persistance
**Tarih:** 2026-05-14
**Durum:** Kabul

**Neden.** Polymarket data-api/lb-api/gamma-api'a yapilan cagrilar yogun (Sprint 01'de 7+ paralel; ileride yuzlerce/dakika). Senkron istemci kabul edilemez. Rate-limit Cloudflare-style sliding window — token bucket en uygun. Veri 100K+ satira cikinca CSV/JSON cok yavas, Pandas hafiza-yiyici.

**Ne.** Kod katmani: `httpx.AsyncClient` (HTTP 1.1; HTTP/2 simdilik yok — `h2` dep'i gereksiz). `aiolimiter.AsyncLimiter` per-host (rate Cloudflare bucketinin %50'si — ayrintilar `pm_research/http.py`). `tenacity` retry: 5 try, exponential backoff 1–30s, sadece 429 + 5xx + transport hatalari. Persistance: Polars 1.40+ DataFrame, Parquet (pyarrow backend) `data/...` altinda gunluk dosyalar.

**Alternatifler.** `aiohttp` (httpx daha modern, sync+async tek API), `requests + threading` (eski paradigma), Pandas (Polars 5–10x daha hizli, daha az hafiza), CSV (5x buyuk, tipsiz), DuckDB (Polars yeterli simdilik).
