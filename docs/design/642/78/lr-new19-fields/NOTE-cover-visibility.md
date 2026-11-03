# #664 L/R — why tip dialog looks empty of product images

## Verified (main `73c76099`)
- Cover pins (`WASH_643` = `675a2220…`) **HTTP 200** on raw.githubusercontent.com.
- Skills wall cards load cover (`wall-tip-cover-*.png`); `naturalWidth > 0`.
- Tip dialog fields = Upload Files + Additional Details only (`NEARMISS_INPUTS`).

## Why `R-tip-dialog-*.png` left has no product media
`SkillRunDialog` left templates render **only** from `examples[]` / preset media tiles
(`#637` — **no cover-fallback**). NEW19 still has `examples: []` / `featured: []`
until #643 gold lands, so left pane is title/author/desc + brand avatar only.
Re-shooting with a 15s cover wait cannot invent left media.

## Residual
Examples / featured / video strips stay empty until #643 gold assets are pinned.
Do not hard-wash from dialog crops.
