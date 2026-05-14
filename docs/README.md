# docs/ — Claude Code'un Beyni

Bu klasor projenin **kalici hafizasi**. Konusma gecicidir, kod degisir, ama burasi tutarli kalir.

## Dosyalar

| Dosya | Amac | Ne zaman guncellenir |
|---|---|---|
| [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) | Hedef, kapsam, mimari, stratejiler, riskler — **proje beyni** | Mimari/strateji degisikliginde, her sprint bitiminde gozden gecir |
| [DECISIONS.md](DECISIONS.md) | Tek-yon ADR kayitlari (Architectural Decision Records) | Kalici bir teknik karar verildiginde (yeni satir ekle, eskileri silme) |
| [GLOSSARY.md](GLOSSARY.md) | Polymarket + HFT terimleri | Yeni kavram aciklandiginda |
| [sprints/](sprints/) | Her sprint = bir klasor (prompt + result) | Sprint basinda + sonunda |

## Yeni conversation acarken
[../CLAUDE.md](../CLAUDE.md) otomatik yuklenir; o dosya buradaki neyin nasil okunacagini soyler.

## Obsidian / wiki gerekli mi?
**Hayir, su an icin gerekli degil.** Sebepler:
- Claude markdown'i native okuyor; backlink/graph gorunumune ihtiyaci yok.
- Repository git ile versiyonlanmis — degisiklik takibi zaten var.
- Obsidian sadece **insan navigasyonunu** kolaylastirir, Claude icin fayda yok.

Ileride **sen** (kullanici) dokuman sayisi 30+ olunca gorsel grafa ihtiyac duyarsan Obsidian'i bu klasore vault olarak isaret edebilirsin — ek konfig gerekmez, salt-okuma vault olur. O zamana kadar gereksiz katman.
