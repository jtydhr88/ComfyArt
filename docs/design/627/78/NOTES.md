# #627 agent step-rail icons/copy align CN live · #78 shots

**Branch:** `feat/627-step-rail-lovart-cn` · Closes #627  
**Product lock:** [comment 6571777033](https://github.com/ganjmeng/ComfyArt/issues/627#issuecomment-6571777033) · unlock [6571830753](https://github.com/ganjmeng/ComfyArt/issues/627#issuecomment-6571830753)  
**Design L/R pin:** `9a316552` on `assets/627-lovart-cn-step-rail` (orphan evidence; not this tip's src)

## Honest source
Real `AssistantBlocks` via `tests/js/process627` + product CSS (`src/styles/{base,canvas,shell,overlays}.css`) — **NOT** full Electron / **NOT** live LLM / **NOT** WaveSpeed. Tip CSS BEFORE is a static forbidden-label card only.

## Change (one tip closes #627)
| Surface | Change |
|---|---|
| `chatMessage.thought` (zh) | **思考完成** (was bare 思考 if any) |
| Image/video row | **runtime model name** (`input.model\|model_name\|modelName`) — never 已生成图片 / Generated images / 图片模型 |
| Post-image thinking | Remap to `ref_analysis` → **参考素材分析结束** when `sawMediaGen` |
| Skill icon | `PROCESS_ICONS.skill` → `Icons.files` (stacked docs) |
| Think icon | double-leaf brain (not bulb) |
| Image icon | frame + sparkle |
| Ref icon | card + chevron on row |
| Web | already `N 个网页` + globe(+favicon) — unchanged |
| End | prose + DoneFeedback 👍/👎 |

## 对照表 (gold vs AFTER vs FORBIDDEN)
| Row | CN live (gold) | This tip AFTER | FORBIDDEN |
|---|---|---|---|
| Think done | 思考完成 | 思考完成 / Thought | 思考 · EN image labeled Thought+Generated images |
| Skill | 技能加载完成 · stacked docs | 技能加载完成 · Icons.files | — |
| Web | N 个网页 · globe(+favicon) | N 个网页 (live) | — |
| Image / media | **runtime model** (Flare / 2.5 Sunburst / GPT Image 2 …) | `opts.model` slot (harness example: GPT Image 2.5 Flare) | 已生成图片 · Generated images · 图片模型 · hardcode Flare only |
| Post-image | 参考素材分析结束 | `ref_analysis` after sawMediaGen | second 思考完成 |
| End | prose + 👍/👎 | DoneFeedback | — |
| Video | Seedance 2.0 视频生成 / GIF 生成完成 (NOTES side) | **Out-of-scope-or-optional** — same model slot if payload exists; do not invent | invented video labels |
| Music / PPT | — | **OUT this tip** | invented Music/PPT rail copy |

## After (this tip)
| Shot | Theme | Shows | Priority |
|------|-------|-------|----------|
| `after/full-rail-zh-light.png` | light / zh | Full one-shot: 思考完成 → tools → **model name** → 参考素材分析结束 → prose+👍 | **MUST** |
| `after/full-rail-en-dark.png` | dark / en | Thought → Skill → web → model → Reference analysis done → prose+👍 | **MUST** |
| `after/simple-turn-zh-light.png` | light / zh | No think rail; model + prose + 👍 | **MUST** |
| `after/simple-turn-en-dark.png` | dark / en | Simple turn EN | SHOULD |

## Before
| Shot | Shows |
|------|-------|
| `before/wrong-labels-zh-light.png` | Forbidden: 思考 / 已生成图片 / second 思考完成 / bulb-ish |

## Tip page
`harness/tip.html` — embeds AFTER/BEFORE + 对照表. Serve:
```bash
python3 -m http.server 8765 --directory docs/design/627/78
# open http://127.0.0.1:8765/harness/tip.html
```

Regenerate AFTER:
```bash
SHOT_DIR=docs/design/627/78/after \
  python -m pytest tests/test_e2e_process_rail_627.py -q
```

## Out of scope
- Music / PPT step-rail copy (**OUT**)
- Video Seedance/GIF labels unless real payload already present (optional wire of same model slot only)
- SkillChip still uses `Icons.scrollText` (rail only changed to files)
- No Lovart string in `src/`

## Design pin (read-only evidence)
Raw pin (commit `9a316552`):  
https://raw.githubusercontent.com/ganjmeng/ComfyArt/9a316552/assets/627-lovart-cn-step-rail/lovart/cn-apple-step-rail-left.png
