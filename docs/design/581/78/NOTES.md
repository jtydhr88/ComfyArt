# #581 → #78 tip-pin — skill card footer real usage (+ modal meta/share)

**Branch:** `feat/581-skill-card-stats` · **Asia/Shanghai** · Issue #581 P0  
**Tip-pin:** absolute `raw.githubusercontent.com` URLs live in the PR body (exact tip SHA). Do not treat an older tip in chat history as current.  
**Scope:** Skills Explore card author row + SkillRunDialog creator row. Covers already in #587; hover video → #575. No competitor brand strings in `src/`. No fake favorite counts.

## Behavior / lock

| Item | Spec |
|------|------|
| Card usage | Shown only when `loadSkillUsage()[id] > 0`; play icon + short count; hidden when empty |
| Favorite count | Never shown (membership-only `loadFavourites`); bookmark toggle stays on cover |
| Modal share | Copies `?skill=<id>` deep link via clipboard; real action |
| Modal favourite | `toggleFavourite` — no count badge |
| Modal meta | `已使用 N 次 · N 个模板` when usage>0; else template-count-only |

## LEFT = ours (AFTER) — live dist 1280×900

Harness: `harness/shoot.py` (Playwright vs `app_url`, mock $0).

| File | Shows |
|------|-------|
| `left-ours/AFTER-skills-card-author-no-usage-zh-light.png` | zh-light product card author — no usage (fresh store) |
| `left-ours/AFTER-skills-card-author-with-usage-zh-light.png` | zh-light product card author — usage=3 from local store |
| `left-ours/AFTER-skills-card-author-en-dark.png` | en-dark product card author — usage=2 |
| `left-ours/AFTER-skill-modal-creator-meta-zh-light.png` | zh-light modal creator (share+fav) + joined meta |

## @design
Please re-sign after visual check on tip (real usage only; no fav count; share copies deep link).
