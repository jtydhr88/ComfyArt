# #497 soft visual 1:1 — #78 AFTER

**Tip:** `feat/497-assets-visual-1to1` · Closes #497  
**Gold pin:** `ad48d344` (`assets/497-visual-lr`) · AC [6573167553](https://github.com/ganjmeng/ComfyArt/issues/497#issuecomment-6573167553)

## AFTER shots (`after/`)

| File | What |
|---|---|
| `after-detail-zh-light.png` | zh-light Assets detail (list + upload + sections + CTA) |
| `after-detail-en-dark.png` | en-dark same (tokens borrowed; no Lovart dark gold) |
| `539c-detail-*.png` / `539b-*` | full e2e capture set (`ASSETS_539_SHOTS`) |

Harness: `ASSETS_539_SHOTS=docs/design/497/78/after pytest tests/test_e2e_sidebar_495.py -k 'assets_detail_539b or assets_c_539'`.

## Tip AC check (visual)

1. List divider ≈159px @1280 (12.5vw − rail) — measured on AFTER
2. List bg `var(--ca-rail-bg)` `#f5f5f5` / dark `#1c1c1c`
3. Upload solid fill; extract subline hidden when embedded
4. Default name 「未命名」/「Untitled」 via `kitDisplayName` → `projectHeader.untitled`
5. Embedded section padding/gaps compressed; 「+ 添加」 untouched
6. CTA height/radius/foot padding tuned; 800-content right-edge kept
7. 「新建」 dashed, no yellow plus fill
8. Dark = existing AFTER tokens

Out held: no filter/search; no preview/download; no character/product extensions; #539 entry/URL/20MB/CTA intact.
