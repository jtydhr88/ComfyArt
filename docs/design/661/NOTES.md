# #661 createSkill white-screen bugfix — screenshots

Tip bugfix only (`chats ?? []`). Not #650 illustration parity.

| File | Meaning |
|------|---------|
| `01-before-createskill-white.png` | Broken: `?createSkill=1` white screen (PAGEERROR `find` on undefined chats) |
| `02-after-createskill-fixed.png` | Fixed tip: Creator UI loads (`技能创建器` chrome) |
| `03-before-after-createskill.png` | Side-by-side before \| after |

Captured from tip dist / local repro on box. Refs #650 (bugfix slice).
