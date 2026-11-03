# #666 SkillRunDialog cover main-preview

## Change
When `examples[]` / preset media tiles are empty but `skillCover(skill)` exists, left column
renders a **dedicated cover hero** (`data-left="cover"`, `skill-run-cover-preview`).
Does **not** push cover into `examples[]` or invent 「模板」 / SkillExamples carousel (#637 preserved).

## Evidence (tip local 4173)
Five NEW19 dialogs: left cover `naturalWidth>0`, fields still Upload+Additional (`file`/`note`).
Examples/featured remain `[]` until #643 gold.

## Paths
- `R-tip-dialog-*.png` — tip dialog
- `LR-*.png` — gold L | tip R
- wall covers unchanged
