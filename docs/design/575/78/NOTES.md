# #575 residual → #78 tip-pin — cover focus mask / lift (Closes)

**Branch:** `feat/575-cover-focus-residual`  
**Base:** main@`b2811cd501fc24ad94fb55378c08e8f4fd54ed17` (after #620/#573)  
**Prior:** #605 tip `046e9874` delivered `Skill.video` + muted hover loop + scale (Refs, not Closes)  
**Zone:** Asia/Shanghai

## Verdict
soft **PASS** candidate — residual CSS focus polish shipped; design motion×2 pin still open (TODO, non-blocking).

## What this tip ships
1. **Focus mask/gradient** — soft bottom `linear-gradient` overlay on home `.ca-skillcard__cover::after` and explore `.ca-swall__cover::after` (hover / focus-visible / focus-within). Reversible; tune when design gold samples land.
2. **Focus scale + slight lift** — `scale(1.05) translateY(-2px)` on home + explore cover stills **and** video overlays. No-video cards keep dual-fit + focus motion.
3. **No fake video** — no continuous pan/zoom on stills (explicit CSS comments + pytest).
4. **Video hover** — unchanged contract from #605 (`skillCoverVideoHover` muted loop; leave → pause + seek 0). Verified helpers + CSS still present.

## Gaps / blockers (do not invent assets)
| Item | Status |
|---|---|
| **new6 hover mp4** (multi-angle, logo-material, meta-ads, mobile-ui, web-product, marketing-campaign) | **MISSING** — no `594/wash/videos/<id>.mp4` / public mp4s. `SKILL_VIDEO_PENDING_NEW6` keeps `video` unset. Gray-note: wire when Batch A-video lands. |
| **motion×2 wash wiring** | **WAIT design pin** — source `569/wash/motion/templates/` @ `bd043d4c` (`01-poster-animation.mp4` P2 de-shake, `02-first-to-last-frame-animation.mp4` P2 de-blur). TODO in `src/skills.ts`; follow-up commit on this branch when pin lands. |
| Design gold L/R sample for mask strength | Soft — current 28%/8% gradient is a tasteful stub. |

## #78 embeds (absolute raw @ tip SHA — fill after push)
See PR body. Local paths:
- `before/home-explore-still-idle.png`
- `after/home-explore-still-focus-mask.png`
- `after/focus-mask-pair-full.png`
- `after/explore-poster-product-hover-cycle.webm` (carry-forward from #605 hover contract)

## Tests
- `tests/test_skill_cover_video_575.py` — helpers, hover wiring, residual mask/lift CSS, no continuous pan/zoom fake-video, no Lovart in src.

## @design
Please soft-sign focus mask + lift on no-video stills (home + explore). Motion×2 template video pin remains a follow-up on this branch after wash PASS.
