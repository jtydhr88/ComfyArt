# #576 → #78 visual review

Skill run dialog template cards: selection ring wraps **image only** (12px radius); title sits outside below with 8px gap (match reference UX). Do **not** put competitor brand string in `src/`.

## LEFT = ours (AFTER)

Harness: `harness/shoot.py` + `tests/test_design_576_78_shots.py` (Playwright vs `app_url`, mock $0).

| File | Shows |
|------|-------|
| `left-ours/AFTER-preset-selected-zh-light.png` | Selected template tile — ring on image, title outside (zh-light) |
| `left-ours/AFTER-preset-unselected-zh-light.png` | Unselected tile — no ring, title outside (zh-light) |
| `left-ours/AFTER-preset-selected-en-dark.png` | Selected tile (en-dark) |
| `left-ours/AFTER-preset-unselected-en-dark.png` | Unselected tile (en-dark) |
| `left-ours/AFTER-template-grid-zh-light.png` | Template grid overview zh-light |
| `left-ours/AFTER-template-grid-en-dark.png` | Template grid overview en-dark |

Tip-pin: absolute `raw.githubusercontent.com` URLs in draft PR body at tip SHA.
