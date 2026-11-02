# #638 #78 AFTER — Phase2-S5 Soft mount (A+B)

**Branch:** `feat/638-skills-phase2-s5-mount` · **Asia/Shanghai** · Issue #638  
**Tip-pin:** absolute `raw.githubusercontent.com` URLs live in the Draft PR body (exact tip SHA).  
**Baseline:** `main@42f59675` (#637 wash B merged). **C5 HOLD** (`#636-C`/`#653`); **D out of scope**; **#490 HOLD**.

## Soft mount (production-ready A+B)

| Soft # | id | surface |
|---:|---|---|
| 1–3 | flash-cut-video · style-transfer · person-swap | Explore forYou after Phase1 (B NEW5 wash #637) |
| 4 | social | Phase1 slot retained + Fashion UGC upgrade (A) |
| 5–6 | commerce-strategist · lifestyle-scene | Explore forYou after B 1–3 |
| — | C deferred5 (naive-illustration…promo-ecommerce) | data-contract only — **not Soft-mounted as washed** |
| — | D style4 (yingzao…fabric-collage) | out of Soft mount scope |
| — | #490 | HOLD — not folded |

`PHASE2_SKILL_IDS` + `PHASE2_DEFERRED_SKILL_IDS` + `orderBuiltins` in `src/skills.ts`. Home quick-start stays Phase1 top 6. Home / Skills Explore both `loadSkills()` → same `BUILTIN_SKILLS`. `website` chip from `mobile-ui` + `web-product` (ppt-visual stays C deferred).

## Dialog / regression
- commerce-strategist: text `sellPoints` → Agent (`mode=agent`) e2e ≥1
- social: Fashion UGC presets via `skill-run-preset-select` (`ugc-feed` / `ugc-story`)
- No demo / placeholder media; no competitor name in `src/`
- Tests: `test_skills_phase2_638` + `test_e2e_skills_phase2_638` green

## LEFT = ours (AFTER) — live dist zh-light 1280×800

Harness: `harness/shoot.py` + `tests/test_design_638_78_shots.py` (Playwright vs `app_url`, mock $0).  
`DESIGN_638_78_SHOOT=1 PYTHONPATH=tests:. pytest -q tests/test_design_638_78_shots.py -s`

| File | Shows |
|------|-------|
| `left-ours/AFTER-home-quickstart-order-zh-light.png` | Home「用 Skill 快速开始」 Phase1 first 6 |
| `left-ours/AFTER-home-chip-website-zh-light.png` | Home **网站** chip → mobile-ui + web-product |
| `left-ours/AFTER-skills-explore-phase2-b-order-zh-light.png` | Skills Explore wall: Phase2 B after Phase1 |
| `left-ours/AFTER-skills-explore-website-chip-zh-light.png` | Explore **网站** chip lit |
| `left-ours/AFTER-skill-modal-commerce-strategist-zh-light.png` | commerce-strategist SkillRun dual-col |
| `left-ours/AFTER-skill-modal-social-ugc-zh-light.png` | social Fashion UGC SkillRun |

## @design
Please re-sign Soft mount tip (Phase1 quick-start untouched + Explore B order + website chip + commerce/social dialogs). C5/D/#490 remain HOLD.
