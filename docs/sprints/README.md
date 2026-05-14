# sprints/ — Sprint Index

> Her sprint = bir klasor. Klasor adi: `sprint-NN-kisa-kebab-isim`.
> Icinde iki dosya: `prompt.md` (basta yazilir, hedef), `result.md` (sonda yazilir, cikti).

## Sprint listesi

| # | Klasor | Durum | Ozet |
|---|---|---|---|
| 00 | [sprint-00-bootstrap](sprint-00-bootstrap/) | 🟢 Tamamlandi | Proje iskeleti, ilk ADR'lar, sprint dongusu |
| 01 | [sprint-01-trader-discovery](sprint-01-trader-discovery/) | 🟡 Aktif | Karli hesaplari bul, trade verilerini topla, strateji fingerprint cikar |
| 02 | _planlanmadi_ | ⚪ | Hedef strateji secimi (Sprint 01 bulgularindan) |
| 03 | _planlanmadi_ | ⚪ | Polymarket API kesfi + ExecutionClient iskeleti |

**Durum simgeleri:** ⚪ planlanmadi · 🟡 aktif · 🟢 tamamlandi · 🔴 iptal

## Sprint yazim kurallari

### prompt.md sablonu
```markdown
# Sprint NN — <isim>

## Hedef
1–3 cumle. Bu sprint bittiginde dunyada ne degismis olacak?

## Kapsam
- Yapilacak: ...
- Kapsam disi: ...

## Kabul kriteri
- [ ] Olculebilir cikti 1
- [ ] Olculebilir cikti 2

## Notlar / on-okumalar
- Link 1
- Link 2
```

### result.md sablonu
```markdown
# Sprint NN — <isim> — Sonuc

## Yapilanlar
- ...

## Sapmalar
Plandan nerede ayrildik, neden?

## Verilen kararlar
- ADR-NNN: <kisa>
- (DECISIONS.md'ye yansitildi)

## PROJECT_CONTEXT.md guncellemeleri
- Hangi bolumler degisti

## Ogrenilenler / sonraki sprintin tohumlari
- ...
```
