# #573 → #78 visual review

Upscale panel resolution custom dropdown: collapsed current value left-aligned to match expanded options. CSS-only (`text-align: left` on `.ca-toolpanel__res .ca-pick`). Do **not** put competitor brand string in `src/`.

## LEFT = ours (AFTER)

Harness: `harness/shoot.py` + `tests/test_design_573_78_shots.py` (Playwright vs `app_url`, mock $0).

| File | Shows |
|------|-------|
| `left-ours/AFTER-res-collapsed-zh-light.png` | Resolution trigger collapsed — value left-aligned (zh-light) |
| `left-ours/AFTER-res-open-zh-light.png` | Trigger + options open — both left-aligned (zh-light) |
| `left-ours/AFTER-res-collapsed-en-dark.png` | Trigger collapsed (en-dark) |
| `left-ours/AFTER-res-open-en-dark.png` | Trigger + options open (en-dark) |
| `left-ours/AFTER-panel-zh-light.png` | Full upscale panel collapsed (zh-light) |
| `left-ours/AFTER-panel-en-dark.png` | Full upscale panel collapsed (en-dark) |
| `left-ours/COMPARE-main-vs-after-open-zh-light.png` | MAIN (centered) vs AFTER (left) open — zh-light |
| `left-ours/COMPARE-main-vs-after-open-en-dark.png` | MAIN (centered) vs AFTER (left) open — en-dark |

## MAIN (before)

Copied from #570 r3 review-assets for compare (centered trigger vs left-aligned options). Tight crops for side-by-side.

| File | Source |
|------|--------|
| `main-before/MAIN-res-open-zh-light.png` | `570/pr/r3/570-pr-r3-upscale-res-open-zh-light.png` |
| `main-before/MAIN-res-open-en-dark.png` | `570/pr/r3/570-pr-r3-upscale-res-open-en-dark.png` |
| `main-before/MAIN-panel-zh-light.png` | `570/pr/r3/570-pr-r3-home-upscale-zh-light.png` |
| `main-before/MAIN-panel-en-dark.png` | `570/pr/r3/570-pr-r3-home-upscale-en-dark.png` |
| `main-before/MAIN-res-open-tight-zh-light.png` | Crop of open dropdown from MAIN zh-light |
| `main-before/MAIN-res-open-tight-en-dark.png` | Crop of open dropdown from MAIN en-dark |

Tip-pin: absolute `raw.githubusercontent.com` URLs in draft PR body at tip SHA.
