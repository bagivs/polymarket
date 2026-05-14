# sprints/ — Sprint Index

> Her sprint = bir klasor. Klasor adi: `sprint-NN-kisa-kebab-isim`.
> Icinde iki dosya: `prompt.md` (basta yazilir, hedef), `result.md` (sonda yazilir, cikti).

## Sprint listesi

| # | Klasor | Durum | Ozet |
|---|---|---|---|
| 00 | [sprint-00-bootstrap](sprint-00-bootstrap/) | 🟢 Tamamlandi | Proje iskeleti, ilk ADR'lar, sprint dongusu |
| 01 | [sprint-01-trader-discovery](sprint-01-trader-discovery/) | 🟡 Review | Discovery + 10 hesap fingerprint, [`findings.md`](sprint-01-trader-discovery/findings.md) Sprint 02 onayi bekliyor |
| 02 | _planlanmadi_ | ⚪ | Sprint 01 onerisi: long-shot scalper (Opsiyon A); kullanici karari sonra |
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
