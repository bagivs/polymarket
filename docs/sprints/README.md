# sprints/ — Sprint Index

> Her sprint = bir klasor. Klasor adi: `sprint-NN-kisa-kebab-isim`.
> Icinde iki dosya: `prompt.md` (basta yazilir, hedef), `result.md` (sonda yazilir, cikti).

## Sprint listesi

| # | Klasor | Durum | Ozet |
|---|---|---|---|
| 00 | [sprint-00-bootstrap](sprint-00-bootstrap/) | 🟢 Tamamlandi | Proje iskeleti, ilk ADR'lar, sprint dongusu |
| 01 | [sprint-01-trader-discovery](sprint-01-trader-discovery/) | 🟢 Tamamlandi | Discovery + 17 hesap fingerprint + user-pnl-api kesfi; [`findings.md §9`](sprint-01-trader-discovery/findings.md): sports-favorite pattern dominant |
| 02 | [sprint-02-sports-favorite-backtest](sprint-02-sports-favorite-backtest/) | ⏸️ Paused | Genel-amacli backtest engine yazildi (8K market, 28 config). YANLIS hipotez ("favorite buy") test edildi; UNDERDOG alternatif uretildi ama bu **yuzeysel fingerprintten strateji icadi** olduğu icin **methodologi hatasi** sayildi. Findings reference olarak kalir, strateji secimi DEGIL. |
| 02b | [sprint-02b-winner-trade-deep-dive](sprint-02b-winner-trade-deep-dive/) | 🟡 Aktif | 7 currently-winning hesabin **trade-level** analizi: per-trade favorite/underdog sınıflandırma, market selection edge, timing patterns. Gercek pattern **veriden** cikartilir. |
| 03 | _planlanmadi_ | ⚪ | Sprint 02b sonucundan strateji + ExecutionClient + canli kanarya |
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
