# GLOSSARY — Polymarket + HFT Terimleri

> Bir terim ilk gectiginde buraya ekle. Tanim 1–2 cumle.

## Polymarket

- **CLOB (Central Limit Order Book).** Polymarket'in off-chain emir eslestirme motoru. Settlement Polygon zincirinde.
- **Conditional Token (CTF).** Bir marketin sonucuna baglanmis ERC-1155 token. Her market icin "YES" ve "NO" olmak uzere 2 token.
- **YES / NO token.** Bir ikili marketin iki tarafini temsil eden tokenlar. P(YES) + P(NO) = $1 USDC.
- **Market.** Resolusyon kriteri olan, belirli bir tarihte sonuclanan tahmin sorusu. Ornek: "X olayi 2026 sonunda gerceklesir mi?"
- **Resolution.** Marketin sonuclanmasi; UMA oracle veya manuel arbitraj ile YES/NO belirlenir, token'lar $1 veya $0'a settle olur.
- **L1 Auth.** Polygon private key ile EIP-712 imzasi — order olusturma icin.
- **L2 Auth.** API key + secret + passphrase — REST/WS cagrilari icin (HMAC).
- **Gamma API.** Polymarket'in market metadata REST API'si (market listesi, slug, kategoriler).
- **py-clob-client.** Polymarket'in resmi Python CLOB istemcisi.

## HFT / market-making

- **Maker / Taker.** Maker = order book'a likidite koyar (limit). Taker = mevcut order'i alir (market).
- **Spread.** Best bid ile best ask farki. Market-maker geliri.
- **Skew / Inventory skew.** Stoktaki pozisyona gore bid/ask'in asimetrik kaydirilmasi (Avellaneda-Stoikov).
- **Top-of-book (TOB).** Order book'un en iyi bid + en iyi ask seviyesi.
- **Order book imbalance.** Bid hacmi vs. ask hacmi orani; kisa vade yon sinyali olabilir.
- **Self-trade prevention (STP).** Ayni hesabin kendi order'iyla eslesmesini engelleyen mekanizma.
- **Kill-switch.** Anormal durumda tum order'lari iptal edip yeni order'i durduran acil-stop.
- **Cancel/replace.** Var olan order'i guncellemek; bazi venue'larda tek atomik istek, bazilarinda iptal + yeni place.
- **Drawdown.** Tepe degerinden mevcuta dusus. Risk metrik.
