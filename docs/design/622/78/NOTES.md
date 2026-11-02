# #622 → #78 tip-pin — motion×2 wash-v1 `preset.video` (Closes #622)

**Branch:** `feat/622-motion-preset-video`  
**Base:** main@`4fb5f3f026408aec2a9ce2cf3ee21b7c496047ad` (#625 merged; #492 coexistence)  
**Design pin:** `5a8d22ed88f732d38f8709a2c0740f074a400a89` (`assets/575-motion-wash-v1`)  
**Zone:** Asia/Shanghai  
**Node:** 22.20+

## Verdict
soft **PASS** candidate — motion template hover/play wired; Explore scale/scrim untouched (#621); new6 still pending (#623).

## What this tip ships
1. **`preset.video` on motion×2** — `src/skills.ts` pins absolute raw embeds:
   - `…/5a8d22ed…/575/wash/templates/01-poster-animation.mp4`
   - `…/5a8d22ed…/575/wash/templates/02-first-to-last-frame-animation.mp4`
   Convention matches FEED / #605 (`raw.githubusercontent.com/<commit>/…`) — **not** `public/`; assets stay on review-assets pin (no rewash, no copy into tip).
2. **SkillRunDialog PresetTile** — muted hover/focus loop via `presetVideo` + `skillCoverVideoHover`; zoom prefers video when set; no-video tiles unchanged.
3. **CSS** — `.ca-skillrun__preset-video` opacity 0→1 on hover/focus-visible @ 150ms; zoomview video rule.

## #78 embeds (absolute raw @ tip SHA — see PR body)
- `after/AFTER-motion-preset-hover-zh-light.png` — poster tile hover, video playing
- `after/AFTER-motion-preset-hover-en-dark.png`
- `after/AFTER-motion-template-grid-zh-light.png`
- `after/AFTER-motion-template-grid-en-dark.png`

## Mutation
Removing `preset.video` / path literals → `tests/test_skill_cover_video_575.py` + `tests/test_skill_cover_494.py` red.

## Out of scope
- Do **not** rewash; do **not** touch Explore scale/scrim (#621); do **not** wire new6 (#623).

## @design
Please soft-sign motion template hover/play (zh-light + en-dark) on tip.
