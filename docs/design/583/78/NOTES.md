# #583 → #78 tip-pin — Skills page header 1:1 gold lock

**Branch:** `feat/583-skills-header` · **Asia/Shanghai** · Issue #583 P0  
**Tip-pin:** absolute `raw.githubusercontent.com` URLs live in the PR body (exact tip SHA). Do not treat an older tip in chat history as current.  
**Scope:** Skills list page ONLY (home tabs stay #589). No competitor brand strings in `src/`.

## Behavior / lock

| Item | Spec |
|------|------|
| Header pad | ~24 60 12; content ~920; left inset ~60 |
| Title「技能」 | 18/26 weight 600, `var(--ca-text)` |
| Create | 80×36 radius 8 split (text + chevron), dark fill — not pill |
| Search | 28×28 on **tab row right**, no border, icon ~16, fg .55; no filter until real filter |
| Tabs | h~36, pad 8 4 0; 13/20 gap 20; selected w500/.9 underline 1px = text width |
| Sticky | title+tabs+chips = chrome sibling above `.ca-skills__scroll` (pinned) |
| Chips | h30 pad 5 12 gap 8; selected bg `.08` |
| Grid | `auto-fill` minmax(296); @1280 ≈ 3×296, gap 24/16 |

## LEFT = ours (AFTER) — live dist 1280×800

Harness: `harness/shoot.py` (Playwright vs `app_url`, mock $0).

| File | Shows |
|------|-------|
| `left-ours/AFTER-skills-header-zh-light.png` | zh-light title/tabs/chips/create/search + top of wall |
| `left-ours/AFTER-skills-header-en-dark.png` | en-dark header chrome |
| `left-ours/AFTER-skills-sticky-scroll-zh-light.png` | chrome stays after scrollTop 600 |
| `left-ours/AFTER-skills-grid-3col-zh-light.png` | adaptive wall ≈ 3 cols |

## @design
Please re-sign after visual check on tip (header 1:1 + sticky + 3-col @1280 vs gold).
