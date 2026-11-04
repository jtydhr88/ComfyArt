# #736 model-edit prompts: replacement tables (DRAFT, needs design review, NOT run, $0 spent)

**Design PASS @2f760e2f with 4 edits applied** (NUVO brand, 双11狂欢价, ppt titles, char-correctness line). ex07 brand stays SOLVAIR. Tech lead approved $0.25 for one run per image.

Angela's rule (2026-11-04 23:35 Asia/Shanghai): **no local text overlay**. No system fonts, no grey boxes. Every text change goes through a model edit that uses the **gold as the base image**, so the gold's font, weight, stroke, colour and position stay. Platform names, festival dates and functional UI (领取 buttons) may stay. Brand names, selling copy and numbers must be ours. Nothing runs until design reviews. Tester's drop list: [docs/qa/736/drops.json](../../../qa/736/drops.json), [docs/qa/736/dropped.jpg](../../../qa/736/dropped.jpg).

Note: the earlier local overlays already committed in #736 (promo 01 双11 restore + 11.11 prefix, ex07 REVENT→SOLVAIR) used system fonts and also fall under this rule. Tech lead to decide whether to revert them. Prompt 1 and prompt 2 cover them in full, so a model edit replaces the whole image.

## 1. promo-ecommerce examples/01 (gold `docs/design/673/gold/promo-ecommerce/ex02.webp`)

Covers all 12 tester spots ([drops.json](../../../qa/736/drops.json)) and 2 typos. Our other existing copy (冬季专场 etc.) and the approved 双11 / 11.11 elements stay as they are.

| # | Gold | Ours |
|---|---|---|
| 1 | band time 10.20 20:00 - 11.11 23:59 (also the line under the 139 box) | 10.24 20:00 - 11.11 23:59 |
| 2 | （官方立减15% / 可叠加会员券） | （会员再享95折 / 店铺券通用） |
| 3 | brown tag 10/31 - 11/11 | 11/01 - 11/11 |
| 4 | 每满3000减300 | 每满2500减250 |
| 5 | 会员专享优惠券 (800 long ticket) | 新客专属领券区 |
| 6 | 会员专享优惠券 (180 right card header) | 新客专属福利 |
| 7 | 立即领取 (red button) | keep (functional UI) |
| 8 | LYSEN DOUBLE ELEVEN | NUVO DOUBLE ELEVEN |
| 9 | BONBUN镇店 | NUVO臻选 |
| 10 | — 热销推荐 — | — 店长推荐 — |
| 11 | 立省30% / 双十一限时 | 立省20% / 双11狂欢价 |
| 12 | 店铺券 (corner ribbon) | 限时券 |
| T1 | typo in ours: 预旋到手价 | 预估到手价 |
| T2 | blurred 新人礼 ribbon | crisp 新客礼 |

**Prompt 1 (image edit, base = gold ex02):**
> Edit this e-commerce promo-component sheet. Keep the layout, every shape, colour, coupon frame, badge, ribbon, bag, barcode, texture and background exactly as they are. Change only the text listed below. Each new string must use the same font, weight, stroke, colour, size, letter-spacing and position as the text it replaces. Do not remove or blank any text. Replace A with B: "10.20 20:00 - 11.11 23:59" → "10.24 20:00 - 11.11 23:59" (every occurrence); "（官方立减15% / 可叠加会员券）" → "（会员再享95折 / 店铺券通用）"; "10/31 - 11/11" → "11/01 - 11/11"; "每满3000减300" → "每满2500减250"; long-ticket "会员专享优惠券" → "新客专属领券区"; right-card header "会员专享优惠券" → "新客专属福利"; "LYSEN DOUBLE ELEVEN" → "NUVO DOUBLE ELEVEN"; "BONBUN镇店" → "NUVO臻选"; "— 热销推荐 —" → "— 店长推荐 —"; "立省30%" → "立省20%"; "双十一限时" → "双11狂欢价"; corner ribbon "店铺券" → "限时券"; ribbon "新人礼" → "新客礼"; any "预估到手价" stays spelled exactly 预估到手价. Keep the red "立即领取" button, 双11 / 11.11 festival marks and 冬季专场 unchanged. Sharp, correctly written Chinese. No extra text, no watermark. All Chinese/English characters must be correct and crisp; no garbled or extra characters; do not overlay new text boxes.

## 2. taobao-product examples/07 (gold `docs/design/643/78/gold/taobao-product/examples/ex-07.webp`)

| Gold | Ours |
|---|---|
| REVENT | SOLVAIR (高速吹风机 stays) |
| 高速干发 (icon + repeated line) | 一吹即干 |
| 负离子护发 | 水润养发 |
| 智能恒温 | 恒温不伤 |
| 轻量便携 | 小巧随行 |
| 低噪设计 | 安静运行 |
| 五大核心卖点 | 核心亮点 |
| 满量护发从容出门 | 晨起吹整 轻松出门 |
| 快速干发体验 | 三分钟吹干 |
| 精密做工细节 | 细节做工 |
| colour names | 珍珠白／玫瑰粉／经典黑 |
| 三色可选 | 配色任选 |

**Prompt 2 (image edit, base = gold ex-07):**
> Edit this multi-panel hair-dryer detail strip. Keep the products, model, lighting, icons, background and layout exactly as they are. Change only the text below, and match each original's font, weight, stroke, colour, size, letter-spacing and position. Do not remove any text. Replace A with B: "REVENT" → "SOLVAIR" (keep "高速吹风机"); "高速干发" → "一吹即干"; "负离子护发" → "水润养发"; "智能恒温" → "恒温不伤"; "轻量便携" → "小巧随行"; "低噪设计" → "安静运行" (both in the icon labels and in the repeated line); "五大核心卖点" → "核心亮点"; "满量护发从容出门" → "晨起吹整 轻松出门"; "快速干发体验" → "三分钟吹干"; "精密做工细节" → "细节做工"; the three colour names → "珍珠白／玫瑰粉／经典黑"; "三色可选" → "配色任选". Sharp, correctly written Chinese. No extra text. All Chinese/English characters must be correct and crisp; no garbled or extra characters; do not overlay new text boxes.

## 3. ppt-visual examples/01 (gold `docs/design/673/gold/ppt-visual/ex01.jpg`)

| Gold | Ours (山野栖居 theme) |
|---|---|
| A RETREAT ABOVE THE CLOUDS | A HAVEN ABOVE THE MIST |
| QUIET PRINCIPLES | SLOW LIVING NOTES |
| NATURAL RETREATS | WILD HIDEAWAYS |
| Cedar Hot Tub | Cedar Soak Pool |

**Prompt 3 (image edit, base = gold ex01):**
> Edit this presentation slide set. Keep the photos, layout, colours and all other text exactly as they are. Replace A with B, keeping each title's font, weight, stroke, letter-spacing, colour, size and position: "A RETREAT ABOVE THE CLOUDS" → "A HAVEN ABOVE THE MIST"; "QUIET PRINCIPLES" → "SLOW LIVING NOTES"; "NATURAL RETREATS" → "WILD HIDEAWAYS"; "Cedar Hot Tub" → "Cedar Soak Pool". Sharp text, no extra text. All Chinese/English characters must be correct and crisp; no garbled or extra characters; do not overlay new text boxes.

## Cost estimate (not run)
3 edit calls; cost to be quoted at review. Needs design review and budget approval first.
