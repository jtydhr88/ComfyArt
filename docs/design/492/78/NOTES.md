# #492 Hide reason=done stop card · #78 shots

**Branch:** `fix/p1-492-hide-done-stop-card` · Closes #492  
**AC:** issue comments [6519682583](https://github.com/ganjmeng/ComfyArt/issues/492#issuecomment-6519682583) / [6526218598](https://github.com/ganjmeng/ComfyArt/issues/492#issuecomment-6526218598) (product confirm 2026-11-02)

## Change
Frontend filter only: in `ChatMessage` / `RunStop`, when stop-card `reason=done`, **do not render** (including reloaded old chats). Backend still emits `run_stop`; payload unchanged. Other stop reasons (budget / stuck / user_stop / error / hard_cap / awaiting_confirm) unchanged.

## Honest source
Tip CSS harness mirroring AssistantBlocks Done ending (prose + 👍) — NOT full Electron / NOT live LLM. Proves the ending has **zero** `.ca-run[data-reason=done]` card.

## After (this tip)
| Shot | Theme | Shows | Priority |
|------|-------|-------|----------|
| `after/normal-complete-zh-light.png` | light / zh | Summary + 👍/👎; **no**「已完成」stop card / **no**「详情」 | **MUST** |
| `after/normal-complete-en-dark.png` | dark / en | Summary + 👍/👎; **no** Done stop card | **MUST** |

## Before
| Shot | Shows |
|------|-------|
| `before/normal-complete-with-done-card-zh-light.png` | Bug repro: title+body both「已完成」+「详情」 under the Done ending |

## Compare (review-assets pin)
Redacted chat-only ending reference: review-assets `c586afd` `491/lovart/C1-edit-in-chat-chat-only-zh.png`  
Raw: https://raw.githubusercontent.com/ganjmeng/ComfyArt/c586afd/491/lovart/C1-edit-in-chat-chat-only-zh.png

## Out of scope
Non-done stop cards (#391/#393 sheet) · Continue / stoppedSubmitted / latest-card logic
