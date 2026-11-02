# #623 → #78 tip-pin — new6 Skill.video hover (Home + Skills wall)

**Tip:** `feat/623-new6-hover-video` (src+dist+#78 same tip; see PR tip SHA) · **Asia/Shanghai**
**Base:** main@`1e251da34b491cb74696537f5d893a1b2136d132` (after #624/#622/#625/#492)
**Design pin:** `d03ea7938877d084c201a94ef51f943dd0e061b9` (`assets/623-new6-hover-v1`)  
**Issue:** Closes #623

## Verdict
soft **PASS** — muted hover loop on new6 Home quick-start + Skills wall; leave/blur → pause + seek 0 (first frame under) via existing #605 `skillCoverVideoHover` contract. No dual-fit / focus scale+scrim redo; motion (#622) and Explore layout untouched.

## Wiring
- `WASH_623_NEW6_VIDEO = d03ea793…` + `video594(id)` → absolute raw `…/594/wash/videos/<id>.mp4` (match #605 pin-SHA raw convention; separate const from upgrade9 `video()` @ 494/wash)
- Wired on: multi-angle, logo-material, meta-ads, mobile-ui, web-product, marketing-campaign
- `SKILL_VIDEO_PENDING_NEW6 = []`

## Surfaces
- Home quick-start: multi-angle + logo-material visible in forYou first row; hover muted loop
- Skills wall Explore: all 6 new6 cards `data-has-video=1` with pin raw src; hover muted loop

## Assets (absolute raw embeds)
- https://raw.githubusercontent.com/ganjmeng/ComfyArt/d03ea7938877d084c201a94ef51f943dd0e061b9/594/wash/videos/multi-angle.mp4
- https://raw.githubusercontent.com/ganjmeng/ComfyArt/d03ea7938877d084c201a94ef51f943dd0e061b9/594/wash/videos/logo-material.mp4
- https://raw.githubusercontent.com/ganjmeng/ComfyArt/d03ea7938877d084c201a94ef51f943dd0e061b9/594/wash/videos/meta-ads.mp4
- https://raw.githubusercontent.com/ganjmeng/ComfyArt/d03ea7938877d084c201a94ef51f943dd0e061b9/594/wash/videos/mobile-ui.mp4
- https://raw.githubusercontent.com/ganjmeng/ComfyArt/d03ea7938877d084c201a94ef51f943dd0e061b9/594/wash/videos/web-product.mp4
- https://raw.githubusercontent.com/ganjmeng/ComfyArt/d03ea7938877d084c201a94ef51f943dd0e061b9/594/wash/videos/marketing-campaign.mp4

## AFTER shots
- `after/AFTER-new6-home-hover-zh-light.png`
- `after/AFTER-new6-home-hover-en-dark.png`
- `after/AFTER-new6-home-grid-zh-light.png`
- `after/AFTER-new6-home-grid-en-dark.png`

## Notes
- No Lovart / competitor names in `src/`
- src + dist + #78 same tip; Node 22.20+
- Coexists with #622 motion×2 wash-v1 preset.video already on main; Explore scale/scrim untouched

## @design
Please re-sign soft PASS on tip (new6 hover muted loop + leave→first frame) for Home multi-angle + Skills wall new6.
