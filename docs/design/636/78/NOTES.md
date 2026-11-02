# #636 → #78 tip-pin — Phase2-S3 C deferred5 soft wash (FU)

**Branch:** `feat/636-skills-phase2-s3-c-deferred5` · **Asia/Shanghai** · Issue #636 / draft PR #653  
**Scope:** C only — `naive-illustration` `logo-abstract` `photo-split-poster` `ppt-visual` `promo-ecommerce`.  
**Wash:** nearMiss remap Examples-only (`WASH_636=5ccfdf0f` on `assets/636-wash-c-deferred5`; ppt example tall sheet 768×1360 (nearMiss 2n7npu8pocu8, not cover)). naive=`2qapfgd34fsw`.  
**UI:** SkillRunDialog left = Examples-only (isomorphic #637). **No 「当前模板」 row** when presets lack media (Examples-only C5). FieldSelect+custom chevron only when left has real preset media tiles. D style4 untouched. #490 HOLD.

## AC (Ashley + product — same tip)

1. C5 Examples-only: REMOVE entire 「当前模板」 row (right) for logo/photo/ppt/promo/naive — presets as defaults only, no select.
2. LEFT column L|R matches lovart gold Examples layout/slots/media (hardMax remap).
3. ppt hardMax1 — tall deck sheet (contain); no multi-slot empty gray.
4. logo filmstrip exactly ×11 filled/visible (data-count=11 thumbs 56×42).
5. #78 tip-pin absolute raw Markdown image embeds for all AFTER + L|R pairs.

## AFTER (`after/`)

All 5 × zh-light + en-dark SkillRunDialog shots. Left = **Examples-only**; right has **no** 「当前模板」.

| File | Skill | Layout |
|------|-------|--------|
| `after-logo-abstract-dialog-{zh-light,en-dark}.png` | logo-abstract | examples-carousel hardMax**11** |
| `after-photo-split-poster-dialog-{zh-light,en-dark}.png` | photo-split-poster | examples-single-still **1** |
| `after-ppt-visual-dialog-{zh-light,en-dark}.png` | ppt-visual | examples-single-still **1** tall sheet |
| `after-promo-ecommerce-dialog-{zh-light,en-dark}.png` | promo-ecommerce | examples-carousel **4** |
| `after-naive-illustration-dialog-{zh-light,en-dark}.png` | naive-illustration | examples-carousel **4** (near=`2qapfgd34fsw`) |

## L|R composites (`lr-pairs/`)

L = `phase2/bc-refs/c5-nearmiss/<near>/dialog.png`. R = AFTER wash dialog.

| File | Pair |
|------|------|
| `LR-<skill>-zh-light.png` | gold \| AFTER zh-light |
| `LR-<skill>-en-dark.png` | gold \| AFTER en-dark |

nearMiss map: logo=`2ns5q6jxbyf4`×11 · photo=`2pg3z0ftueww`×1 · ppt=`2n7npu8pocu8`×1 · promo=`2q1txsahwp34`×4 · naive=`2qapfgd34fsw`×4.

## Wash pin

`WASH_636 = 5ccfdf0f481bbcbb3392516dba75f1ec3bda3ab6` → `636/wash/<id>/{cover,examples,featured}`.

## Harness

`DESIGN_636_78_SHOOT=1 PYTHONPATH=tests:. pytest -q tests/test_design_636_78_shots.py -s`
