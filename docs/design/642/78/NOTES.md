# #642 → #78 tip-pin — Phase3-S3 NEW19 field parity (Upload+Additional)

**Branch:** `feat/642-new19-field-parity` · **Asia/Shanghai** · Issue #642  
**Base tip:** `1daf7f75` (main after #663)  
**SSOT:** `PRODUCT-LOCK-PHASE3.md` · design Page Phase3 S2/S3 · gold dialogs under `docs/design/640/78/gold/<id>/dialog.webp`  
**Comments chain to:** `#642` + locks. Soft mainline Phase3 / **#490 HOLD**. Media wash → **#643**. Skill Creator → **#650**.

## Product split (this tip)

| In (mergeable after design/test) | Deferred |
|---|---|
| NEW19 right rail → `NEARMISS_INPUTS` (`file`/`note` = Upload Files + Additional Details) | NEW19 tip dialog L/R screenshots (need tip serve + capture) |
| Drop deepen multi-fields (`personImage`/`garmentImage`/`refs`+`VISUAL` etc.) | inventing Title / Preset chips (gold has none → `presetChips` stays absent) |
| Keep prompt-only `presets` (≥2) for backend style routing | examples/featured/video wash (#643; gold missing) |
| Gold dialog L embeds for sample slots under `lr-new19-fields/` | Production deepen of copy beyond shell parity |

**Parity, not deepen.** Gold dialogs for NEW19 show **Upload Files + Additional Details** only (same family as nearMiss / EFFECT shell). Prior S1 deepen schemas contradicted that.

## Dialog parity rules

- Gold site = external Explore dual-column SkillRunDialog; **never** name that brand under `src/`.
- Right column for NEW19 = Upload Files + Additional Details (`NEARMISS_INPUTS`).
- Shared IA: top → main visual → inputs → primary CTA.
- Do **not** invent Title / Preset chips when gold has none.
- Prompt `presets` without images do not render as left-rail tiles (filtered); chips only if `presetChips` set — NEW19 keep chips off.

## NEW19 hard lock (this tip)

`taobao-product` · `before-after` · `anim-2d` · `creator-identity` · `product-website` · `studio-model` · `youtube-channel-banner` · `ai-model` · `product-to-packaging` · `game-art` · `portrait-studio` · `premium-website` · `animated-poster` · `pose-fission` · `live-promo-decor` · `linkedin-banner` · `logo-animation` · `restaurant-website` · `clothing-swap`

## Field map (gold → tip)

| Slot family | Gold right rail | Tip `inputs` |
|---|---|---|
| All NEW19 (sampled: taobao / before-after / clothing-swap / linkedin / product-website) | Upload Files + Additional Details | `NEARMISS_INPUTS` |
| thumbnail (already #660/#641) | Upload + Additional | `EFFECT_INPUTS` (unchanged this tip) |

## AC

- [x] NEW19 `inputs: NEARMISS_INPUTS`; no deepen multi-fields; no `presetChips`
- [x] Tests: `tests/test_skills_phase3_642.py` asserts NEARMISS; no `Lovart`/`lovart` under `src/`
- [x] Gold dialog L embeds in `docs/design/642/78/lr-new19-fields/`
- [x] Tip dialog R screenshots (5 sample slots; fields=`file`,`note`)
- [ ] After #643 gold for examples/featured/video → pin + wash follow-up

## L/R

- `docs/design/642/78/lr-new19-fields/L-gold-dialog-*.webp` — gold Upload+Additional evidence
- Tip R: `R-tip-dialog-*.png` + composite `LR-*.png` (gold | tip)
