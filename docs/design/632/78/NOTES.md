# #632 restore assets list width 380px — #78 AFTER

**Tip:** `fix/632-assets-list-width` · Closes #632 · Refs #497  
**AC:** [6574168106](https://github.com/ganjmeng/ComfyArt/issues/632#issuecomment-6574168106)  
**MEASURE:** `ComfyArt-review-assets/497/list-width-fix/MEASURE.md`

## Miss cause
#497 soft tip `c1b3305d` set `.ca-assets-page__left` to `calc(12.5vw - var(--ca-rail-w-collapsed))` / `max-width: 180px`, crushing the list to ~88–104px @1280（「未…」截断）. Pin 误把 Lovart 导航右缘 ~159 当列表列宽；正确结构列表 **240–620 = 380**（exclude icon rail）。

## AFTER shots (`after/`)

| File | What |
|---|---|
| `after-detail-zh-light.png` | zh-light @1280 全页：列表可读 + 详情（复用 #539 AFTER，list≈380） |
| `after-list-left-zh-light.png` | @1280 左侧紧裁：品牌套件/角色 tab + 卡片名完整 |
| `after-detail-1920-zh-light.png` | zh-light @1920 全页 |
| `after-list-left-1920-zh-light.png` | @1920 左侧紧裁 |

Source: `/workspace/ComfyArt-review-assets/497/visual-lr/after/539c-detail-p1-zh-light.png` (+1920 twin). 相对 crushed tip：本 tip 固定 `width: 380px`，撤销 vw/max-180。

## Tip AC check
1. 撤销 `12.5vw` / `max-width:180` / `min-width:88` → **GO**
2. 列表列宽 **380px** fixed @1280/1920（±8）→ **GO**
3. 保留 #631：`var(--ca-rail-bg)`、无「从文件中提取」、默认「未命名」、虚线新建、行距/CTA → **GO**
4. rail 图标正圆；tab/卡片可读无截断 → **GO**（见 left crop）
5. filter/搜索 Out → **GO**
