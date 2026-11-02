# #640 → #78 tip-pin — Phase3-S1 data contract (20 slots)

**Branch:** `feat/640-skills-phase3-s1` · **Asia/Shanghai** · Issue #640  
**Tip-pin:** absolute `raw.githubusercontent.com` URLs live in the draft PR body (exact tip SHA).  
**SSOT:** `PRODUCT-LOCK-PHASE3.md` · `PHASE3-HARDEN-DIFF.md` · review gold `ComfyArt-review-assets/phase3/DESIGN-GOLD.md`  
**Comments chain to:** `#640` + locks. Soft mainline Phase3 / **#490 HOLD**. Skill Creator → **#650** (out of slots).

## Gold embeds (cover + dialog only)

Per product steering: S1 tip-pin = embed **cover + dialog** for all 20 hard slots (examples / wash pack → S4). Files under `gold/<id>/{cover,dialog}.webp` (resized tip copies of `bc-refs/<id>/`).

| Bucket | Count | ids |
|---|---:|---|
| wash **ready** | 14 | `taobao-product` `before-after` `anim-2d` `creator-identity` `youtube-channel-banner` `ai-model` `product-to-packaging` `thumbnail` `game-art` `portrait-studio` `premium-website` `pose-fission` `live-promo-decor` `restaurant-website` |
| **need wash** (thin6 → S4, does **not** block S1) | 6 | `product-website` `studio-model` `animated-poster` `linkedin-banner` `logo-animation` `clothing-swap` |
| **need capture** | 0 | — |

## Scope note

S1 = **data contract only** — `BUILTIN_SKILLS` + locales + tests. NEW19: empty `examples`/`featured`, no `cover`/`video` pins in product. Upgrade `thumbnail` kept (deepen in S2). No homepage mount (S5). Dropped-13 out. No `Lovart` in `src`.

## Website chip

NEW website sources: `product-website` · `premium-website` · `restaurant-website` (plus Phase1/2).
