# #576 → #78 visual review

Skill run dialog template cards: selection ring wraps **image only** (12px radius); title sits outside below with 8px gap (match reference UX). Do **not** put competitor brand string in `src/`.


## Refresh after #618

- Merged `origin/main` @ `d152c320f2285cbcc62df4b51a75057bb2d4bb5a` (#618/#601 soft FU) into `feat/576-template-select-frame`.
- VOID prior tip `00e2d2dd6e9502b9e1a06d8ca3a05666f997ae9f` (CONFLICTING/DIRTY vs main). Image-only select ring CSS kept; dist rebuilt Node 22.20 (src+dist same tip).
- AFTER shots re-shot post-merge (`DESIGN_576_78_SHOOT=1`); tip-pin absolute raw URLs in draft PR body at **new** tip SHA.
- #541 `test_examples_carousel_is_data_driven` want updated for #593 new-6 example counts absorbed from main.

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
