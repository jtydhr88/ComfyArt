# #636 → #78 tip-pin — Phase2-S3 C deferred5 soft wash

**Branch:** `feat/636-skills-phase2-s3-c-deferred5` · **Asia/Shanghai** · Issue #636 / draft PR #653  
**Scope:** C only — `naive-illustration` `logo-abstract` `photo-split-poster` `ppt-visual` `promo-ecommerce`.  
**Wash:** nearMiss remap Examples-only (`WASH_636=f11f2a6a` on `assets/636-wash-c-deferred5`). naive=`2qapfgd34fsw`.  
**UI:** SkillRunDialog left = Examples-only (isomorphic #637); right preset `<select>`. D style4 untouched. #490 HOLD.

## AFTER (`after/`)

All 5 × zh-light + en-dark SkillRunDialog shots. Left = **Examples-only** (gold isomorphic; no 「模板」/presets grid; hardMax counts).

| File | Skill | Layout |
|------|-------|--------|
| `after-logo-abstract-dialog-{zh-light,en-dark}.png` | logo-abstract | examples-carousel hardMax**11** |
| `after-photo-split-poster-dialog-{zh-light,en-dark}.png` | photo-split-poster | examples-single-still **1** |
| `after-ppt-visual-dialog-{zh-light,en-dark}.png` | ppt-visual | examples-single-still **1** |
| `after-promo-ecommerce-dialog-{zh-light,en-dark}.png` | promo-ecommerce | examples-carousel **4** |
| `after-naive-illustration-dialog-{zh-light,en-dark}.png` | naive-illustration | examples-carousel **4** (near=`2qapfgd34fsw`) |

## L|R composites (`lr-pairs/`)

L = `phase2/bc-refs/c5-nearmiss/<near>/dialog.png`. R = AFTER wash dialog.

| File | Pair |
|------|------|
| `LR-<skill>-zh-light.png` | gold \| AFTER zh-light |
| `LR-<skill>-en-dark.png` | gold \| AFTER en-dark |

## Wash pin

`WASH_636 = f11f2a6a65687cff7b3f71a5c1e4515ab6ae7009` → `636/wash/<id>/{cover,examples,featured}`.

## Harness

`DESIGN_636_78_SHOOT=1 PYTHONPATH=tests:. pytest -q tests/test_design_636_78_shots.py -s`
