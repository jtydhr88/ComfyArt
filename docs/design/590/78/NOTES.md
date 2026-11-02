# #590 → #78 tip-pin — wash-v2 FEED_V1 featured pin

**Branch:** `feat/590-featured-feed-pin` · **Asia/Shanghai** · Issue #590  
**Tip-pin:** absolute `raw.githubusercontent.com` URLs with the tip commit SHA live in the draft PR body. Do not treat an older tip in chat history as current.

## Pin
- `FEED_V1`: `98a34727037f806895a4baed34dd2a498cb9baa2` → `0e92302302de2102ab6f66aa7633a40945a381c7`
- Paths stay `580/featured-v1/<skill>/0{1..4}.webp` (in-place wash-v2 on assets tip).
- `FEED_SPECIAL_COLLAGE` stays on `FEED_V1` (`580/embed-v1` @200 on that pin).
- **VOID** wash-v1 tip `b85f38cd` / product soft-VOID (Ashley).

## Product / design
- Product PASS wash-v2: https://github.com/ganjmeng/ComfyArt/issues/590#issuecomment-6570025852
- Design wash-v2: https://github.com/ganjmeng/ComfyArt/issues/590#issuecomment-6570010770

## LEFT = ours (AFTER) — live dist 1280×800

Harness: `harness/shoot.py` + `tests/test_design_590_78_shots.py` (`DESIGN_590_78_SHOOT=1`).

| File | Locale / theme | Shows |
|------|----------------|-------|
| `left-ours/AFTER-home-featured-masonry-zh-light-1280.png` | zh / light | Explore forYou masonry — washed featured tiles |
| `left-ours/AFTER-home-featured-masonry-en-dark-1280.png` | en / dark | Explore forYou masonry — washed featured tiles |
| `left-ours/AFTER-home-featured-branding-chip-zh-light-1280.png` | zh / light | Branding chip filtered masonry |
| `left-ours/AFTER-home-featured-ads-chip-en-dark-1280.png` | en / dark | Ads chip filtered masonry |

Washed slots visible in masonry include HALCYON (interior), HELIO (banner), Tide Ledger (social), ARC RIDE / product / poster titles in image pixels.
