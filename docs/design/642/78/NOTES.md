# #642 → #78 tip-pin — Phase3-S3 thumbnail shell (shell-only split)

**Branch:** `feat/642-skills-phase3-s3-copy-dialog` · **Asia/Shanghai** · Issue #642  
**Base tip:** `a042575e` (main after #659)  
**SSOT:** `PRODUCT-LOCK-PHASE3.md` · `PHASE3-HARDEN-DIFF.md` · design Page Phase3 S2/S3  
**Comments chain to:** `#642` + locks. Soft mainline Phase3 / **#490 HOLD**. Media wash → **#643**. Skill Creator → **#650**.

## Product split (this tip)

| In (mergeable now) | Deferred (follow-up tip/PR) |
|---|---|
| Shared SkillRunDialog **thumbnail shell** Lovart parity — Upload + Additional only | NEW19 sample L/R (empty cover / multi-field S1 skeleton) |
| Card + dialog L/R embeds for `thumbnail` | Per-id NEW19 field map → Upload+Additional |
| Scaffold markers / gold STATUS stubs / static contract tests | Production deepen of NEW19 copy; true gold L for NEW19 |

**Parity, not deepen.** Design signed thumbnail shell **PASS**; NEW19 sample was **HOLD** → stripped from this tip.

## Dialog parity rules (shell)

- Gold site = external Explore dual-column SkillRunDialog; **never** name that brand under `src/`.
- Right column for thumbnail = Upload + Additional notes only (`file`,`note`).
- Shared IA: top → main visual → inputs → primary CTA.
- Do **not** invent Title / Preset chips when gold has none.

## NEW19 (hard lock — deferred out of this tip)

`taobao-product` · `before-after` · `anim-2d` · `creator-identity` · `product-website` · `studio-model` · `youtube-channel-banner` · `ai-model` · `product-to-packaging` · `game-art` · `portrait-studio` · `premium-website` · `animated-poster` · `pose-fission` · `live-promo-decor` · `linkedin-banner` · `logo-animation` · `restaurant-website` · `clothing-swap`

Do **not** re-land dropped-13. Upgrade `thumbnail` path already via #641/#657; this tip only documents shell L/R + S3 scaffold pin.

## AC (this tip = shell)

- [x] Thumbnail card L/R + dialog L/R in PR body (Upload+Additional)
- [x] Tests: `tests/test_skills_phase3_642.py` green; no `Lovart`/`lovart` under `src/`
- [ ] NEW19 per-skill L/R + field map → **follow-up**
- [ ] After #643: pin cover/examples/featured for NEW19 → follow-up

## L/R (this tip)

- `docs/design/642/78/lr/01-lr-shelf-card-thumbnail.png` — gold card vs tip thumbnail card
- `docs/design/642/78/lr/02-lr-skill-dialog-thumbnail.png` — gold dialog vs tip SkillRunDialog **Upload+Additional only**
- NEW19 `03`/`04` sample **removed** (deferred).
