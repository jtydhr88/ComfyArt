# Small text erased to background in washed images (follow-up $0 text-fix PR, not #736)

Team standard: wherever the gold has text, ours must have text of similar length, size, weight and position. Per Angela's rule, the fix is a model edit with the gold as the base. No local overlay.
Block counts below come from RapidOCR. Counts not yet computed.

| Image | Gold blocks | Ours blocks | Status |
|---|---|---|---|
| 673/wash/promo-ecommerce/examples/01 (gold ex02) | – | – | in #736: 12 spots + 2 typos ([drops.json](../../../qa/736/drops.json)), fix via prompt 1 |
| 643/wash/taobao-product/examples/07 | – | – | in #736: copy verbatim, fix via prompt 2 |
| 673/wash/ppt-visual/examples/01 | – | – | in #736: 4 English words, fix via prompt 3 |
| promo-ecommerce ex01 (6 posters, docs/design/673/next/promo-ex01.webp) | TBD | TBD | follow-up: recount |
| 643/wash/taobao-product/examples/02 | TBD | TBD | follow-up (gold text still present per test) |
| 643/wash/taobao-product/examples/03 | TBD | TBD | follow-up |
| 643/wash/taobao-product/examples/04 | TBD | TBD | follow-up |
| 643/wash/taobao-product/examples/06 | TBD | TBD | follow-up |
| 673/wash/photo-split-poster/cover | TBD | TBD | follow-up |
| 673/wash/photo-split-poster/examples/01 | TBD | TBD | follow-up |

TBD: the recount was stopped when the rule changed (23:35 Asia/Shanghai). Test is counting blocks per region in the follow-up issue.
