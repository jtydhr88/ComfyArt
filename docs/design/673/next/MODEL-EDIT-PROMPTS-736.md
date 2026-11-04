# #736 model-edit prompts: replacement tables (DRAFT, needs design review, NOT run, $0 spent)

Angela's rule (2026-11-04 23:35 Asia/Shanghai): **no local text overlay**. No system fonts, no grey boxes. Every text change goes through a model edit that uses the **gold as the base image**, so the gold's font, weight, stroke, colour and position stay. Platform names, festival dates and functional UI (领取 buttons) may stay. Brand names, selling copy and numbers must be ours. Nothing runs until design reviews. Tester's drop list: [docs/qa/736/drops.json](../../../qa/736/drops.json), [docs/qa/736/dropped.jpg](../../../qa/736/dropped.jpg).

Note: the earlier local overlays already committed in #736 (promo 01 双11 restore + 11.11 prefix, ex07 REVENT→SOLVAIR) used system fonts and also fall under this rule. Tech lead to decide whether to revert them. Prompt 1 and prompt 2 cover them in full, so a model edit replaces the whole image.

## 1. promo-ecommerce examples/01 (gold `docs/design/673/gold/promo-ecommerce/ex02.webp`)

| # | Spot (gold bbox) | Gold | Ours |
|---|---|---|---|
| A | top card tag | 双11礼遇季 | keep (festival) |
| B | top time line | TIME: 10.20 - 11.11 | TIME: 10.24 - 11.11 |
| C | top card main | 新品专区 1件低至85折 | 冬季专场 1件低至8折 |
| D | top card sub | 官方立减15% / 可叠加会员券 | 满额再享9折 / 新客专享 |
| E | top card price | 日常价 199 / 预估到手价 169 | 到手价 139 / 预估到手价 139 |
| 1 | band date (70,447) | 10.20 20:00 - 11.11 23:59 | 10.24 20:00 - 11.11 23:59 |
| F | band | 双11狂欢 / 加入店铺会员领取专属优惠券>> / 官方立减15% | 双11狂欢 (keep) / 关注店铺领取冬日好礼>> / 新客满减9折 |
| 2 | row3 sub (355,592) | （官方立减15% / 可叠加会员券） | （会员再享95折 / 店铺券通用） |
| G | row3 | 日常价 199 · 双11狂欢 · 秋冬新品 1件低至85折 | 日常价 229 · 双11狂欢 (keep) · 冬装上新 第二件88折 |
| T1 | row3 dark box (652,588) | 预估到手价 169 | 预估到手价 139 (fixes our typo 预旋到手价) |
| 1b | under dark box (625,693) | 10.20 20:00 - 11.11 23:59 | 10.24 20:00 - 11.11 23:59 |
| H | right card 1 | 夹克限时1件7折 / 叠加优惠更划算 | 限时第2件半价 |
| I | right card 2 | 双11预售 / TIME: 10/24开启 / 付定立减 预估到手价￥599 | 双11预售 (keep) / TIME: 10/25开启 / 预约优惠 预估到手￥459 |
| J | right card 3 | 全店6期免息 ￥400会员专属礼券 / 88VIP消费券 | 全店3期免息 ￥260新客礼券 / 限时特惠 |
| 3 | brown tag (1019,584) | 10/31 - 11/11 | 11/01 - 11/11 |
| K | right card 4 | Jacket Special / 单笔实付≥1000 赠袜子 | Time Offer / 满额≥1288 送围巾 |
| L | coupon 1 | ¥200 全画幅配件券 满1999使用 / 关注领取 | ¥100 镜头清洁券 满2000可用 / 关注领取 (keep) |
| 4 | coupon 2 top (1373,940) | 每满3000减300 / ¥300 / 抢 | 每满2500减250 / ¥250 / 抢 |
| 5 | long ticket left (1007,1194) | 会员专享优惠券 / 点击领取 | 新客专属领券区 / 立即抢券 |
| M | long ticket right | ¥1500 旗舰相机券 | ¥800 冬季焕新券 |
| N | coupon 4 | 点击领取 / ¥1200 镜头专享券 满5999元可用 | 马上领用 / ¥120 限时专享券 满2099元可用 |
| 12 | corner ribbon (1254,1342) | 店铺券 | 限时券 |
| 6 | right card header (1388,1369) | 会员专享优惠券 | 新客专属福利 |
| O | right card body | ¥300 全画幅券 满1999可用 | ¥180 满1599元可用 |
| 7 | red button (1423,1585) | 立即领取 | 立即领取 (functional UI, keep) |
| T2 | small ribbon (956,1525) | 新人礼 | 新客礼 (crisp, fixes our blurred ribbon) |
| P | coupon 5 | ¥500 满2999元使用 | ¥600 满3999元可用 |
| Q | SALE bag | UP TO 20% OFF / 11.11 现货速发 | SAVE 30% NOW / 11.11 当天发货 |
| R | red bag | 狂欢开门红 / 爆款价 / ￥2999 | 双11热卖 / 人气价 / ￥1999 |
| S | price + barcode | ￥2999 双11专享 | ￥1999 双11专享 (keep festival) |
| 8 | barcode vertical (657,1441) | LYSEN DOUBLE ELEVEN | SOLA DOUBLE ELEVEN |
| U | pink circle badges | 长效水润 专利认证 / 0刺激 成分温和 / 敏感肌 不敏感 / 植物提取 / 老客好评 / 植物配方 + rim English | 温和修护 / 0添加香精 / 柔润不紧绷 / 草本精华 / 回购之选 / 臻选原料 + rim GENTLE CARE / PURE FORMULA / DAILY GLOW / HERBAL ESSENCE / WINTER PICKS / SOFT TOUCH |
| 9 | shield top (1028,1863) | BONBUN 镇店 | SOLA 臻选 |
| V | shield main | 大促爆款 | 冬日必入 |
| 10 | shield footer (1035,2076) | — 热销推荐 — | — 店长推荐 — |
| W | round badge | 品牌直营 / 官方正品 / 品质保障 | 冬季上新 / 品质优选 / 放心之选 |
| X | ticket subline | 双十一限时 | 双十一爆款 |
| Y | ticket main | 狂欢7折 | 限时8折 |
| 11 | ticket corner (1367,2390) | 立省30% | 立省20% |

**Prompt 1 (image edit, base = gold ex02, 1690×2560):**
> Edit this e-commerce promo-component sheet. Keep the layout, every shape, colour, coupon frame, badge, ribbon, bag, barcode, photo texture and background exactly as they are. Change only the text listed below. Each new string must use the same font family, weight, stroke, colour, size, letter-spacing, alignment and position as the text it replaces, and no text may be removed or left blank. Replace: "TIME: 10.20 - 11.11" → "TIME: 10.24 - 11.11"; "新品专区 1件低至85折" → "冬季专场 1件低至8折"; "官方立减15% / 可叠加会员券" → "满额再享9折 / 新客专享"; top card "日常价 199" → "到手价 139", big "169" → "139"; both "10.20 20:00 - 11.11 23:59" → "10.24 20:00 - 11.11 23:59"; "加入店铺会员领取专属优惠券>>" → "关注店铺领取冬日好礼>>"; "官方立减15%" → "新客满减9折"; "（官方立减15% / 可叠加会员券）" → "（会员再享95折 / 店铺券通用）"; row "日常价 199" → "日常价 229"; "秋冬新品 1件低至85折" → "冬装上新 第二件88折"; dark box "预估到手价 169" → "预估到手价 139"; "夹克限时1件7折 | 叠加优惠更划算" → "限时第2件半价"; "TIME: 10/24开启" → "TIME: 10/25开启"; "付定立减 | 预估到手价¥599" → "预约优惠 | 预估到手¥459"; "全店6期免息 ¥400会员专属礼券 | 88VIP消费券" → "全店3期免息 ¥260新客礼券 | 限时特惠"; "10/31 - 11/11" → "11/01 - 11/11"; "Jacket Special" → "Time Offer"; "单笔实付≥1000 赠袜子" → "满额≥1288 送围巾"; "¥200 全画幅配件券 满1999使用" → "¥100 镜头清洁券 满2000可用"; "每满3000减300" → "每满2500减250", "¥300" (envelope) → "¥250"; "会员专享优惠券 / 点击领取" (long ticket) → "新客专属领券区 / 立即抢券"; "¥1500 旗舰相机券" → "¥800 冬季焕新券"; "点击领取" (stub) → "马上领用"; "¥1200 镜头专享券 满5999元可用" → "¥120 限时专享券 满2099元可用"; corner ribbon "店铺券" → "限时券"; right card "会员专享优惠券" → "新客专属福利", "¥300 全画幅券 满1999可用" → "¥180 满1599元可用", keep the red "立即领取" button; ribbon "新人礼" → "新客礼"; "¥500 满2999元使用" → "¥600 满3999元可用"; "UP TO 20% OFF" → "SAVE 30% NOW"; "11.11 现货速发" → "11.11 当天发货"; "狂欢开门红" → "双11热卖"; "爆款价 ¥2999" → "人气价 ¥1999"; big "¥2999" → "¥1999"; vertical "LYSEN DOUBLE ELEVEN" → "SOLA DOUBLE ELEVEN"; pink circles: "长效水润 专利认证" → "温和修护", "0刺激 成分温和" → "0添加 香精", "敏感肌 不敏感" → "柔润 不紧绷", "植物提取" → "草本精华", "老客好评" → "回购之选", "植物配方" → "臻选原料", circle rim English → "GENTLE CARE", "PURE FORMULA", "DAILY GLOW", "HERBAL ESSENCE", "WINTER PICKS", "SOFT TOUCH"; shield "BONBUN 镇店" → "SOLA 臻选", "大促爆款" → "冬日必入", "— 热销推荐 —" → "— 店长推荐 —"; round badge "品牌直营 / 官方正品 / 品质保障" → "冬季上新 / 品质优选 / 放心之选"; ticket "双十一限时" → "双十一爆款", "狂欢 7折" → "限时 8折", "立省30%" → "立省20%". Keep unchanged: 双11礼遇季, 双11狂欢, 双11预售, 双11专享, 关注领取, 抢, 立即领取, 预估到手价 labels. All text must be sharp and correctly spelled Chinese. No extra text, no watermark.

## 2. taobao-product examples/07 (gold `docs/design/643/78/gold/taobao-product/examples/ex-07.webp`, 3072×1024, 5 panels)

| Gold | Ours |
|---|---|
| REVENT | SOLA |
| 高速吹风机 | 高速吹风机 (product type, keep) |
| 高端护发科技 | 新一代护发科技 |
| 高速干发 (icon label + line) | 一吹即干 |
| 负离子护发 | 水润养发 |
| 智能恒温 | 恒温不伤 |
| 轻量便携 | 小巧随行 |
| 低噪设计 | 安静运行 |
| 五大核心卖点 | 核心亮点 |
| 清晨护发 从容出门 | 晨起吹整 轻松出门 |
| 快速干发体验 | 三分钟吹干 |
| 每一处都经得起细看 | 每一处细节都是品质 |
| 精密做工细节 | 细节做工 |
| 象牙白 / 曜石黑 / 樱花粉 | 珍珠白 / 经典黑 / 玫瑰粉 |
| 三色可选 | 配色任选 |

**Prompt 2 (image edit, base = gold ex-07):**
> Edit this 5-panel hair-dryer detail strip. Keep every product, the model, the lighting, icons, background and layout exactly as they are. Change only the text below, and match each original's font, weight, size, colour, letter-spacing and position exactly. Every original line must still have text in the same place, with nothing removed. Replace: "REVENT 高速吹风机" → "SOLA 高速吹风机"; "高端护发科技" → "新一代护发科技"; icon labels "高速干发 / 负离子护发 / 智能恒温 / 轻量便携 / 低噪设计" → "一吹即干 / 水润养发 / 恒温不伤 / 小巧随行 / 安静运行", same five in the subline above "五大核心卖点"; "五大核心卖点" → "核心亮点"; "清晨护发 从容出门" → "晨起吹整 轻松出门"; "快速干发体验" → "三分钟吹干"; "每一处都经得起细看" → "每一处细节都是品质"; "精密做工细节" → "细节做工"; "象牙白 / 曜石黑 / 樱花粉" → "珍珠白 / 经典黑 / 玫瑰粉"; "三色可选" → "配色任选". Sharp, correctly written Chinese. No extra text.

## 3. ppt-visual examples/01 (5-page stitch, theme 「山野栖居」; gold `docs/design/673/gold/ppt-visual/ex01.jpg` is style only, so the base for this edit is **our current** `673/wash/ppt-visual/examples/01.webp`, the first image in this doc not based on the gold)

| Page | Ours now (gold word) | Ours new |
|---|---|---|
| p1 subtitle | A RETREAT ABOVE THE CLOUDS | A MOUNTAIN STAY ABOVE CLOUDS |
| p2 section title | QUIET PRINCIPLES | MOUNTAIN NOTES |
| p3 section label | NATURAL RETREATS | MOUNTAIN SCENES |
| p4 card title | Cedar Hot Tub | Cedar Spring Pool |

**Prompt 3 (image edit, base = current ppt-visual examples/01, run per page crop and restitch):**
> Edit this presentation slide. Keep the photo, layout, colours and all other text exactly as they are. Replace only these English words, keeping each one's serif or sans font, weight, letter-spacing, colour, size and position: "A RETREAT ABOVE THE CLOUDS" → "A MOUNTAIN STAY ABOVE CLOUDS"; "QUIET PRINCIPLES" → "MOUNTAIN NOTES"; "NATURAL RETREATS" → "MOUNTAIN SCENES"; "Cedar Hot Tub" → "Cedar Spring Pool". Leave the underline accent and the page numbers untouched. Sharp text, no extra text.

## Cost estimate (not run)
3 edits (ppt as 4 page crops = 6 calls) at roughly $0.038/1K edit is about $0.23. Each retry adds the same per call. Needs design review and budget approval first.
