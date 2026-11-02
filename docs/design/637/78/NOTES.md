# #637 #78 AFTER — Phase2-S4 B NEW5 soft wash

Tip-pin via PR body `raw.githubusercontent.com` URLs (absolute, tip SHA). Product AC: person-swap hard max1, lifestyle-scene hard max2; flash-cut/commerce single-video; style-transfer carousel×4. #653 C tip stays parked (EL HOLD).

## AFTER (`after/`)

All 5 × zh-light + en-dark SkillRunDialog shots (no gray placeholders; left column data-driven).

| File | Skill | Layout |
|------|-------|--------|
| `after-flash-cut-video-dialog-{zh-light,en-dark}.png` | flash-cut-video | examples-single-video |
| `after-style-transfer-dialog-{zh-light,en-dark}.png` | style-transfer | examples-carousel ×4 |
| `after-person-swap-dialog-{zh-light,en-dark}.png` | person-swap | examples-single-still hard max1 |
| `after-commerce-strategist-dialog-{zh-light,en-dark}.png` | commerce-strategist | examples-single-video |
| `after-lifestyle-scene-dialog-{zh-light,en-dark}.png` | lifestyle-scene | examples-carousel hard max2 |

## L|R composites (`lr-pairs/`)

L = `phase2/bc-refs/<skill>/dialog.png` (lovart gold left column). R = AFTER wash dialog.

| File | Pair |
|------|------|
| `LR-<skill>-zh-light.png` | gold \| AFTER zh-light |
| `LR-<skill>-en-dark.png` | gold \| AFTER en-dark |

Skills: flash-cut-video, style-transfer, person-swap, commerce-strategist, lifestyle-scene.

## Wash pin

`WASH_637 = 2109c085aa74c617cd34517f99626f357062c81c` on `assets/637-wash-b-new5` → `637/wash/<id>/{cover,examples,featured,example.mp4}`.

## Harness

`DESIGN_637_78_SHOOT=1 PYTHONPATH=tests:. pytest -q tests/test_design_637_78_shots.py -s`
