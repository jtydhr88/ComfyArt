# #575 residual → #78 tip-pin — Explore scale + flat scrim (Closes)

**Branch:** `feat/575-cover-focus-residual`  
**Base:** main@`b2811cd501fc24ad94fb55378c08e8f4fd54ed17` (after #620/#573)  
**Prior:** #605 tip `046e9874` delivered `Skill.video` + muted hover loop + Home scale (Refs, not Closes)  
**Design gold lock:** Explore flat scrim `rgba(0,0,0,.3)` @ 150ms KEEP; Explore ADD `scale(1.05)` @ 300ms ease; NO `translateY(-2px)` / soft bottom gradient  
**Zone:** Asia/Shanghai

## Verdict
soft **PASS** candidate — residual Explore scale + flat scrim aligned to design gold; motion×2 / new6 still TODO (non-blocking).

## What this tip ships
1. **Explore scale** — `.ca-swall__cover img` / `.ca-swall__video` → `scale(1.05)` on hover / `:focus-within` @ `transform 300ms ease` (Explore was transform:none).
2. **Explore scrim** — KEEP flat `.ca-swall__cover::after` → `rgba(0,0,0,.3)` @ 150ms. Not edge/bottom linear-gradient.
3. **Home** — #605 `scale(1.05)` left intact; no invented lift/mask on home.
4. **No-video stills** — scale + flat scrim + bookmark/try chrome OK; no continuous pan/zoom fake-video.
5. **Video hover** — #605 contract unchanged (`skillCoverVideoHover` muted loop).

## Gaps / blockers (do not invent assets)
| Item | Status |
|---|---|
| **new6 hover mp4** (multi-angle, logo-material, meta-ads, mobile-ui, web-product, marketing-campaign) | **MISSING** — `SKILL_VIDEO_PENDING_NEW6` keeps `video` unset. Gray-note; wire when assets land. |
| **motion×2 wash wiring** | **WAIT design pin** — `569/wash/motion/templates/` @ `bd043d4c` (01 de-shake, 02 de-blur). TODO in `src/skills.ts`. |

## #78 embeds (absolute raw @ tip SHA — see PR body)
- `before/home-explore-still-idle.png`
- `after/explore-still-scale-scrim.png`
- `after/explore-scale-scrim-pair.png`
- `after/explore-poster-product-hover-cycle.webm` (carry-forward from #605)

## Tests
- `tests/test_skill_cover_video_575.py` — Explore scale + flat scrim, forbid invent translateY/gradient, no continuous pan/zoom, helpers, no Lovart.

## @design
Please soft-sign Explore `scale(1.05)` + flat `.3` scrim. Motion×2 / new6 remain follow-up.
