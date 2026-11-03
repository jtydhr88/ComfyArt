import { atom } from 'tldraw'
import { unzipSync } from 'fflate'

import { deleteUserFile, listUserFiles, readUserText, uploadImage, viewUrl, writeUserText } from './comfy'
import { lang, t } from './i18n'
import { uuid } from './id'
import { BRAND } from './brand'

/** #494 — zh/en copy carried by the skill data itself (not locales), so adding a skill never touches UI code. */
export interface LocText { zh: string; en: string }
/** #494 — Explore category (data only, never hardcoded in components). Unset = only under 「为你推荐」. A category with no skill gets no chip. */
export type SkillCategory = 'ecommerce' | 'branding' | 'social' | 'website' | 'ads'
/** #494 — one preset (template): `prompt` is the style text appended after the skill's instructions when the user runs
 *  the skill with this preset (step 2). `image` is the preset's own example image; unset → the skill's list cover. */
export interface SkillPreset { id: string; name: LocText; prompt?: string; image?: string; /** #575 — optional template hover/detail mp4; unset → still `image` / skill cover. */ video?: string }
/** #494 — one field of the skill's input dialog. Label / placeholder / default / required all come from here. */
export interface SkillInput {
  key: string; label: { zh: string; en?: string }; type: 'text' | 'textarea' | 'select' | 'image'; required?: boolean
  options?: { value: string; label: { zh: string; en?: string } }[]; default?: string; placeholder?: LocText
}
export interface Skill {
  id: string; name: string; description?: string; instructions: string; files?: Record<string, string>; images?: Record<string, string>; custom?: boolean; learned?: string[]
  /** #494 built-in metadata. Imported / personal skills have none of these and need no migration. */
  category?: SkillCategory; cover?: string; video?: string; presets?: SkillPreset[]; inputs?: SkillInput[]
  /** #541/#575 「效果示例」 carousel media (commit-pinned stills and/or short mp4). Unset → the section is not rendered.
   *  #641: an explicit empty list renders 「暂无示例」 when `presetChips` is set. */
  examples?: string[]
  /** #641 — text preset chips (first preset selected). No per-preset still; switching stays inside the dialog. */
  presetChips?: boolean
  /** #580 cut 2 — the three image slots, one per surface: `cover` = Skills module (above, unchanged);
   *  `quickStartCover` = home 「用 Skill 快速开始」 row (fixed 4:3); `featured` = home masonry images
   *  (natural ratio, full-bleed). Unset → fall back to the existing images (see skillQuickStartCover / skillFeaturedCases). */
  quickStartCover?: string
  /** #602 — home quick-start cover object-fit. Default `cover` (full-bleed). Set `contain` for letterbox on the card plate. */
  quickStartCoverFit?: 'cover' | 'contain'
  featured?: string[]
  /** #580 P2 — preset id shown first for this skill in home 「Skill 案例」 (fallback path only). */
  featuredPreset?: string
}
export interface SkillVersion { time: number; skill: Skill }

const ROOT = 'comfyart/skills'
const TEXT_FILE = /\.(md|txt|json|csv|ya?ml|html?|css|js|ts|svg)$/i
const IMAGE_FILE = /\.(png|jpe?g|webp|gif)$/i

/** #494 — list covers + wash presets on orphan review-assets (commit-pinned; washed outputs only).
 *  Legacy local `/comfyart/skills/<id>/cover.webp` kept as SKILL_ASSET_BASE for any non-data callers. */
export const SKILL_ASSET_BASE = '/comfyart/skills'
/** #581 final list covers (11×462x346 webp), manifest review-assets 494/covers-final/manifest.json @7237c371.
 *  Each entry is [dir, commit]: v3 for 9, banner v3.1, character v3.2 (composed from the merged #574 templates). */
const COVER_V3 = '3c9b87e7eae72164efdd1fe30e00f576144475f4'
/** #594 Phase1 new6 covers (494/covers-v4) + featured-v2 + 594/wash examples — eye PASS 6/6 incl. mobile-ui cover regen. */
const WASH_594 = 'cc76d743d416c3d9a9a6852d811a7a80caf40319'
const COVER_V4 = WASH_594
const COVERS_581: Record<string, readonly [string, string]> = {
  poster: ['494/covers-v3', COVER_V3], social: ['494/covers-v3', COVER_V3], brand: ['494/covers-v3', COVER_V3],
  packaging: ['494/covers-v3', COVER_V3], thumbnail: ['494/covers-v3', COVER_V3],
  banner: ['494/covers-v3.1', '9b23a3e8e3ca2f6b64dc16c0cf36fbf9c41fcaf4'],
  character: ['494/covers-v3.2', 'dc335056e81e0350e2f98487fb680e22ffb14bb9'],
  product: ['494/covers-v3', COVER_V3], motion: ['494/covers-v3', COVER_V3], interior: ['494/covers-v3', COVER_V3],
  'multi-angle': ['494/covers-v4', COVER_V4], 'logo-material': ['494/covers-v4', COVER_V4],
  'meta-ads': ['494/covers-v4', COVER_V4], 'mobile-ui': ['494/covers-v4', COVER_V4],
  'web-product': ['494/covers-v4', COVER_V4], 'marketing-campaign': ['494/covers-v4', COVER_V4],
}
const cover = (id: string) => {
  const [dir, commit] = COVERS_581[id]
  return `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${commit}/${dir}/${id}.webp`
}
/** #580 cut 2 — home-feed image sets, parallel to COVERS_581 / WASH_569: skill id → [dir, commit, files[]] on
 *  review-assets (commit-pinned). Empty until design delivers the washed home sets; skills absent here fall back. */
const QUICK_START_COVERS: Record<string, readonly [string, string, string]> = {}
const FEED_V1 = '0e92302302de2102ab6f66aa7633a40945a381c7'  // #590 wash-v2 PASS (supersedes #588 pin / wash-v1 b85f38cd)
const FEED_V2 = WASH_594  // #594 new6 featured-v2
const FEED_COVERS: Record<string, readonly [string, string, readonly string[]]> = {
  poster: ['580/featured-v1/poster', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  social: ['580/featured-v1/social', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  brand: ['580/featured-v1/brand', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  packaging: ['580/featured-v1/packaging', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  thumbnail: ['580/featured-v1/thumbnail', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  banner: ['580/featured-v1/banner', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  character: ['580/featured-v1/character', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  product: ['580/featured-v1/product', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  motion: ['580/featured-v1/motion', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  interior: ['580/featured-v1/interior', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  'multi-angle': ['580/featured-v2/multi-angle', FEED_V2, ['01.webp', '02.webp', '03.webp', '04.webp']],
  'logo-material': ['580/featured-v2/logo-material', FEED_V2, ['01.webp', '02.webp', '03.webp', '04.webp']],
  'meta-ads': ['580/featured-v2/meta-ads', FEED_V2, ['01.webp', '02.webp', '03.webp', '04.webp']],
  'mobile-ui': ['580/featured-v2/mobile-ui', FEED_V2, ['01.webp', '02.webp', '03.webp', '04.webp']],
  'web-product': ['580/featured-v2/web-product', FEED_V2, ['01.webp', '02.webp', '03.webp', '04.webp']],
  'marketing-campaign': ['580/featured-v2/marketing-campaign', FEED_V2, ['01.webp', '02.webp', '03.webp', '04.webp']],
}
const pinned = (dir: string, commit: string, file: string) => `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${commit}/${dir}/${file}`
const quickStartCover = (id: string) => { const e = QUICK_START_COVERS[id]; return e ? pinned(e[0], e[1], e[2]) : undefined }
/** #588 — the two masonry special cards' collage images (580/embed-v1/manifest.json, commit-pinned). */
export const FEED_SPECIAL_COLLAGE: Readonly<Record<string, string>> = {
  capture: pinned('580/embed-v1', FEED_V1, 'inspiration@thumb.webp'),
  connector: pinned('580/embed-v1', FEED_V1, 'connector@thumb.webp'),
}
const feedCovers = (id: string) => { const e = FEED_COVERS[id]; return e ? e[2].map((f) => pinned(e[0], e[1], f)) : undefined }
/** #529 list/detail cover videos (10× short mp4 on review-assets; commit-pinned). */
const WASH_VIDEO_COMMIT = '1bbb3f208f18b26ef95c8d9f16efeea111c43ac7'
const video = (id: string) =>
  `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${WASH_VIDEO_COMMIT}/494/wash/videos/${id}.mp4`
/** #575 — media URL is a short cover/example video (mp4/webm/mov). Stills stay images; no fake video badge without data. */
export function isSkillMediaVideo(src: string | null | undefined): boolean {
  return !!src && /\.(mp4|webm|mov)(\?|#|$)/i.test(src)
}
/** #623 — new6 hover mp4s wired @ design pin `assets/623-new6-hover-v1` (soft PASS).
 *  Paths: 594/wash/videos/<id>.mp4 via absolute raw.githubusercontent commit-pin (same as #605 / FEED).
 *  Empty pending list = all six shipped; keep export for harness mutation surface. */
export const SKILL_VIDEO_PENDING_NEW6 = [] as const
/** #623 design soft PASS pin SHA for new6 cover hover videos. */
const WASH_623_NEW6_VIDEO = 'd03ea7938877d084c201a94ef51f943dd0e061b9'
const video594 = (id: string) =>
  `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${WASH_623_NEW6_VIDEO}/594/wash/videos/${id}.mp4`
/** #622 — motion×2 wash-v1 template mp4s (design soft PASS pin `assets/575-motion-wash-v1`).
 *  Still thumbs stay wash569 @ bd043d4c; old 569/wash/motion/templates/ kept on review-assets.
 *  Convention: raw.githubusercontent commit-pin (same as FEED / #605 skill videos) — not public/. */
const WASH_575_MOTION_VIDEO = '5a8d22ed88f732d38f8709a2c0740f074a400a89'
/** Literal repo-relative paths so tip embeds + mutation asserts stay absolute/pin-visible. */
const WASH_575_MOTION_POSTER = '575/wash/templates/01-poster-animation.mp4'
const WASH_575_MOTION_FIRSTLAST = '575/wash/templates/02-first-to-last-frame-animation.mp4'
const wash575MotionVideo = (rel: string) =>
  `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${WASH_575_MOTION_VIDEO}/${rel}`
/** #541 AC rev 2 washes on review-assets (541/wash/<skill>/<skill>__<preset>.webp; each pinned to its own commit). */
const WASH_541 = {
  product: '688a702a1f322082cde4e5ed46200c3593db9c43', // 1:1, Amazon 商品主图
  productDetail: '2422dc53d37b8f4437a7f9f7986440d2ea79bbf1', // detail → true macro
  brand: 'f2045022727c73e24bd6d5ebcb3815bedb7b8797', // 4:3 stacked, Logo 系统
  packaging: 'c26cfaddc5e12c8652b151ef09ad12c47b2062a0', // 4:3, 品牌包装设计系统 (5); manifest c26cfad (mockup dropped, same 5 images as 1014ef2)
  packagingShelf: '35c819e64b38cc7d64dcd814ae8b86133976fc8a', // shelf re-wash: retail shelf rows (manifest d574dda6)
}
/** #541 「效果示例」 carousel washes (541/wash/<skill>/examples/<n>.webp), pinned to each IMAGE commit (manifest commit in comment). */
const EX_541 = {
  poster: '6d864bd2dd53b9f5b487829f2834d94be013b0a5', // 5 @3:4, manifest 5eb216e
  thumbnail: '5fc35b17f11ee58fde21671b16b574ecb0d35e5a', // 6 @16:9 (#5 single-scene re-wash), manifests 249b9e09 / 88824ff1
  interior: '535d9568d1b8ca25e300fa32db1eca887889ba88', // 4 = 3 scenes @4:5 + 1:1 material mood board, manifest ea13dd4
  social: 'cb41cb8a450139cd903e777c8f84024019d517cd', // 10 @3:4 (小红书封面制作器), manifest e1b34fa
  banner: '8cc3fb305f7ce29ebbab63525680e3436e964dbb', // 1 × ~2:1 composite (4:3 + 3:4 side by side), manifest cd871d76
}
const ex541 = (skillId: keyof typeof EX_541, ids: number[]) =>
  ids.map((n) => `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${EX_541[skillId]}/541/wash/${skillId}/examples/${n}.webp`)
/** #594 「效果示例」 — 594/wash/<id>/examples/01–04.webp @ WASH_594. */
const ex594 = (skillId: string, ids: number[]) =>
  ids.map((n) => pinned(`594/wash/${skillId}/examples`, WASH_594, `${String(n).padStart(2, '0')}.webp`))
// #637 Phase2-S4 B NEW5 soft wash — cover/examples/featured (+ single-video example.mp4).
// Layout hardMax from phase2/bc-refs meta: flash-cut/commerce = 1 video slot;
// style-transfer = 4 stills; person-swap = 1 still; lifestyle-scene = 2 stills.
const WASH_637 = '2109c085aa74c617cd34517f99626f357062c81c'
const cover637 = (id: string) => pinned(`637/wash/${id}`, WASH_637, 'cover.webp')
const ex637 = (id: string, ids: number[]) =>
  ids.map((n) => pinned(`637/wash/${id}/examples`, WASH_637, `${String(n).padStart(2, '0')}.webp`))
const feat637 = (id: string, ids: number[]) =>
  ids.map((n) => pinned(`637/wash/${id}/featured`, WASH_637, `${String(n).padStart(2, '0')}.webp`))
const video637 = (id: string) => pinned(`637/wash/${id}`, WASH_637, 'example.mp4')
// #643 Phase3-S4 true wash (kie offline) — thumbnail + NEW19 covers; batch1 examples wired (featured empty).
const WASH_643 = '0be4350be224066cccf5e2929bfcb02e0bf8f7a9'
const cover643 = (id: string) => pinned(`643/wash/${id}`, WASH_643, 'cover.webp')
// #643 per-slot PRs: optional per-slot pin so each slot merges independently.
const ex643 = (id: string, ids: number[], pin: string = WASH_643) =>
  ids.map((n) => pinned(`643/wash/${id}/examples`, pin, `${String(n).padStart(2, '0')}.webp`))
const feat643 = (id: string, ids: number[]) =>
  ids.map((n) => pinned(`643/wash/${id}/featured`, WASH_643, `${String(n).padStart(2, '0')}.webp`))
// #636 Phase2-S3 C deferred5 soft wash — nearMiss remap Examples-only (hardMax layouts).
// logo carousel11; photo-split/ppt still1; promo/naive carousel4; featured 3–5 cycle.
const WASH_636 = '5ccfdf0f481bbcbb3392516dba75f1ec3bda3ab6'
const cover636 = (id: string) => pinned(`636/wash/${id}`, WASH_636, 'cover.webp')
const ex636 = (id: string, ids: number[]) =>
  ids.map((n) => pinned(`636/wash/${id}/examples`, WASH_636, `${String(n).padStart(2, '0')}.webp`))
const feat636 = (id: string, ids: number[]) =>
  ids.map((n) => pinned(`636/wash/${id}/featured`, WASH_636, `${String(n).padStart(2, '0')}.webp`))
const wash541 = (commit: string, skillId: string, presetId: string) =>
  `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${commit}/541/wash/${skillId}/${skillId}__${presetId}.webp`
const washProduct541 = (presetId: string) => wash541(presetId === 'detail' ? WASH_541.productDetail : WASH_541.product, 'product', presetId)
/** #569 character (7) + motion (2) template washes, from review-assets manifest 881494ff (assets pinned to bd043d4c). */
const WASH_569_COMMIT = 'bd043d4cff5019fc4117b5b2f3a33ae437015a28'
// character final (manifest review-assets f81ce12a): v3 @b63d44ea under templates/v3/, 04/05 v3.1 @9024565c under templates/v3.1/
const CHARACTER_V2 = 'b63d44ea61085a77a1c990605c31ae552db36c71'
const CHARACTER_V3_1 = '9024565c9857c5cb79e3bce85e636f5f102ad181' // 04 + 05 re-washed under templates/v3.1/
type Wash569 = string | readonly [string, string, string]
const WASH_569: Record<'character' | 'motion', readonly Wash569[]> = {
  character: [['v3/01-character-turnaround-sheet', '569/wash', CHARACTER_V2], ['v3/02-expression-pose-sheet', '569/wash', CHARACTER_V2], ['v3/03-modeling-detail-reference-sheet', '569/wash', CHARACTER_V2], ['v3.1/04-outfit-form-variation-sheet', '569/wash', CHARACTER_V3_1], ['v3.1/05-prop-interaction-sheet', '569/wash', CHARACTER_V3_1], ['v3/06-basic-character-sheet', '569/wash', CHARACTER_V2], ['v3/07-complete-technical-character-sheet', '569/wash', CHARACTER_V2], ['v3/08-luxury-editorial-character-sheet', '569/wash', CHARACTER_V2]],
  motion: ['01-poster-animation', '02-first-to-last-frame-animation'],
}
// Manifest-driven (review-assets 569/wash/manifest.json @f81ce12a): an entry is a file name at WASH_569_COMMIT, or
// [name, dir, commit] when the manifest pins that template to another assets commit. A re-wash only edits this data.
const wash569 = (skillId: keyof typeof WASH_569, n: number) => {
  const e = WASH_569[skillId][n]
  const [name, dir, commit] = typeof e === 'string' ? [e, '569/wash', WASH_569_COMMIT] : e
  return `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${commit}/${dir}/${skillId}/templates/${name}@thumb.webp`
}
const P = (id: string, zh: string, en: string, prompt: string, image?: string, video?: string): SkillPreset =>
  ({ id, name: { zh, en }, prompt, ...(image ? { image } : {}), ...(video ? { video } : {}) })
type L = [zh: string, en: string]
function I(key: string, [zh, en]: L, type: SkillInput['type'], required = false, ph?: L): SkillInput {
  return { key, label: { zh, en }, type, ...(required ? { required } : {}), ...(ph ? { placeholder: { zh: ph[0], en: ph[1] } } : {}) }
}
/** #569 effect-example skills: right side is only 上传文件 + 补充描述. */
const EFFECT_INPUTS: SkillInput[] = [I('file', ['上传文件', 'Upload file'], 'image'), I('note', ['补充描述', 'Additional notes'], 'textarea', false, ['有什么想补充的吗？', 'Anything you want to add?'])]
/** #691/#693: multi-angle — Upload stays optional; Additional placeholder recommends uploading a reference. */
const MULTI_ANGLE_INPUTS: SkillInput[] = [I('file', ['上传文件', 'Upload file'], 'image'), I('note', ['补充描述', 'Additional notes'], 'textarea', false, ['有什么想补充的吗？建议上传参考图', 'Anything you want to add? Uploading a reference image is recommended'])]
/** #636 C5 nearMiss Examples-only: gold isomorphic right rail — Upload Files + single-line Additional Details only. */
const NEARMISS_INPUTS: SkillInput[] = [I('file', ['上传文件', 'Upload Files'], 'image'), I('note', ['补充描述', 'Additional Details'], 'text', false, ['还有什么想补充的吗？', 'Anything else to add?'])]
/** #569 template skills: shared third field 视觉呈现方式. */
const VISUAL = I('visual', ['视觉呈现方式', 'Visual presentation'], 'text', false, ['补充想保留或避开的视觉要求，没有可以留空', 'Visual preferences to keep or avoid; leave blank if none'])

/** #494 — pick the current UI language from data-carried copy. */
export const loc = (text: { zh: string; en?: string }) => (lang === 'en' && text.en) || text.zh

/** #595 — Phase1 15 ids in hot-mapping uses order (product lock TOP15 unique).
 *  Home forYou / Explore forYou / quick-start / featured queues follow this via orderBuiltins.
 *  website chip lit by mobile-ui + web-product. interior kept after Phase1 (custom-workflow removed: no gold card) (not Phase1 slots). */
export const PHASE1_SKILL_IDS = [
  'product', 'multi-angle', 'brand', 'character', 'logo-material', 'packaging',
  'motion', 'meta-ads', 'poster', 'thumbnail', 'mobile-ui', 'social',
  'marketing-campaign', 'web-product', 'banner',
] as const
export const PHASE1_SKILL_ID_SET: ReadonlySet<string> = new Set(PHASE1_SKILL_IDS)
export const UNTOUCHED_SKILL_IDS = ['interior'] as const
/** #634 Phase2-S1 — 14 NEW ids (upgrade `social` is not listed here). */
export const PHASE2_NEW_SKILL_IDS = [
  'flash-cut-video', 'style-transfer', 'person-swap', 'commerce-strategist', 'lifestyle-scene',
  'naive-illustration', 'logo-abstract', 'photo-split-poster', 'ppt-visual', 'promo-ecommerce',
  'yingzao', 'crt-interface', 'crayon-sketch', 'fabric-collage',
] as const
export const PHASE2_NEW_SKILL_ID_SET: ReadonlySet<string> = new Set(PHASE2_NEW_SKILL_IDS)

/** #638 Phase2-S5 Soft mount — PRODUCT-LOCK-PHASE2 Soft order slots 1–6 production-ready (A social upgrade + B NEW5 washed).
 *  `social` also lives in PHASE1_SKILL_IDS (upgrade, no dup card). C deferred5 + D style4 stay unmounted as production (#653/#636-C HOLD; D out of scope). #490 HOLD. */
export const PHASE2_SKILL_IDS = [
  'flash-cut-video', 'style-transfer', 'person-swap', 'social', 'commerce-strategist', 'lifestyle-scene',
] as const
export const PHASE2_SKILL_ID_SET: ReadonlySet<string> = new Set(PHASE2_SKILL_IDS)
/** #638 — C deferred .art5 + D style4: data-contract only; do not treat as washed production mount. */
export const PHASE2_DEFERRED_SKILL_IDS = [
  'naive-illustration', 'logo-abstract', 'photo-split-poster', 'ppt-visual', 'promo-ecommerce',
  'yingzao', 'crt-interface', 'crayon-sketch', 'fabric-collage',
] as const
export const PHASE2_DEFERRED_SKILL_ID_SET: ReadonlySet<string> = new Set(PHASE2_DEFERRED_SKILL_IDS)

/** #640 Phase3-S1 — 19 NEW ids (upgrade `thumbnail` is not listed here). PRODUCT-LOCK-PHASE3 + PHASE3-HARDEN-DIFF. Skill Creator → #650.
 *  #642 Phase3-S3 — NEW19 field parity Upload+Additional (NEARMISS_INPUTS); media wash → #643; no competitor strings in src). */
export const PHASE3_NEW_SKILL_IDS = [
  'taobao-product', 'before-after', 'anim-2d', 'creator-identity', 'product-website',
  'studio-model', 'youtube-channel-banner', 'ai-model', 'product-to-packaging',
  'game-art', 'portrait-studio', 'premium-website', 'animated-poster', 'pose-fission',
  'live-promo-decor', 'linkedin-banner', 'logo-animation', 'restaurant-website', 'clothing-swap',
] as const
export const PHASE3_NEW_SKILL_ID_SET: ReadonlySet<string> = new Set(PHASE3_NEW_SKILL_IDS)

/** Phase1 hot order → Phase2 Soft mount NEW (B) → deferred C/D → untouched / other. */
function orderBuiltins(skills: Skill[]): Skill[] {
  const phase1Rank = new Map<string, number>(PHASE1_SKILL_IDS.map((id, i) => [id, i]))
  // Soft mount NEW only (exclude `social` — already ranked in Phase1)
  const phase2MountIds = PHASE2_SKILL_IDS.filter((id) => !phase1Rank.has(id))
  const phase2Rank = new Map<string, number>(phase2MountIds.map((id, i) => [id, i]))
  const deferredRank = new Map<string, number>(PHASE2_DEFERRED_SKILL_IDS.map((id, i) => [id, i]))
  const phase1: Skill[] = []
  const phase2: Skill[] = []
  const deferred: Skill[] = []
  const rest: Skill[] = []
  for (const s of skills) {
    if (phase1Rank.has(s.id)) phase1.push(s)
    else if (phase2Rank.has(s.id)) phase2.push(s)
    else if (deferredRank.has(s.id)) deferred.push(s)
    else rest.push(s)
  }
  phase1.sort((a, b) => (phase1Rank.get(a.id)! - phase1Rank.get(b.id)!))
  phase2.sort((a, b) => (phase2Rank.get(a.id)! - phase2Rank.get(b.id)!))
  deferred.sort((a, b) => (deferredRank.get(a.id)! - deferredRank.get(b.id)!))
  return [...phase1, ...phase2, ...deferred, ...rest]
}

/** #591 Phase1-S1 data contract + #592 Phase1-S2 upgrade-9 + #593 new-6 instructions/presets + #594 wash pins + #595 hot mount order.
 *  Upgrade 9: brand packaging poster product character social motion banner thumbnail.
 *  New 6 media: covers-v4 + featured-v2 + 594/wash examples @ WASH_594; dual-fit contain (#602); hover video @ WASH_623_NEW6_VIDEO (#623).
 *  #634 Phase2-S1 — PRODUCT-LOCK-PHASE2: 14 NEW ids (B .ai5 + C deferred.art5 + D style4).
 *  #635 Phase2-S2 — deepen `social` Fashion UGC production instructions/presets/inputs (keep RedNote; no fashion-ugc id).
 *  #636/#637 Phase2-S3/S4 — B NEW5 production + soft wash; C5 HOLD / D out of scope for Soft mount.
 *  #638 Phase2-S5 — Soft mount A+B via PHASE2_SKILL_IDS + orderBuiltins (home + Skills Explore same BUILTIN_SKILLS); C/D deferred; #490 HOLD.
 *  #642 Phase3-S3 — NEW19 NEARMISS_INPUTS field parity (scaffold); assets empty until #643 wash pins.
 *  Skill Creator Out → #650. `interior` untouched. Gold UX site external — never name it in src.
 */
export const BUILTIN_SKILLS: Skill[] = orderBuiltins([
  { id: 'poster', name: t('skills.posterDesign'), instructions: 'You are a production poster designer. Deliver print-ready compositions, not loose mood sketches.\n1) Brief: pull headline, subject, audience and use (event, promo, editorial) from the upload and notes.\n2) Hierarchy: one hero subject, strong headline typography in quotes, clear subcopy ladder, generous margins.\n3) Ratio: default 3:4; keep safe margins for print crop. Offer 2 distinct art directions when the brief is open.\n4) Finish: high contrast, legible at arm length, no clipped type. Put every on-art phrase in quotes.\n5) Refs: when the user uploaded a file, pass its shape id in refs (ref_modes content) on every generate_image call.',
    category: 'ads', cover: cover('poster'), quickStartCover: quickStartCover('poster'), featured: feedCovers('poster'), video: video('poster'), examples: ex541('poster', [1, 2, 3, 4, 5]),
    inputs: EFFECT_INPUTS },
  // #635 Phase2-S2 A: deepen `social` Fashion UGC (candid / off-duty) + keep RedNote covers/set; DO NOT invent fashion-ugc.
  { id: 'social', name: t('skills.socialMediaSet'), instructions: 'You are a production social content designer for RedNote / lifestyle covers AND candid fashion UGC stills. Deliver post-ready frames, never a staged studio look.\n1) Brief: brand voice, product, person, and channel (feed 1:1 / story 9:16 / RedNote cover) from uploads and notes.\n2) Fashion UGC path: candid off-duty real-person energy; product clearly in frame; natural light or everyday locations; never seamless studio backdrops, never stiff catalog poses.\n3) RedNote / lifestyle covers: bold subject, clean negative space for title stickers, high thumb-stop contrast; share one palette across a 1:1 feed, a 4:5 post and a 9:16 story when shipping a set.\n4) Copy: keep text short and mobile-legible; every on-art phrase in quotes; Fashion UGC may stay near-textless when the look is the message.\n5) Refs: when productRef / personRef / file are uploaded, pass each shape id in refs (ref_modes content) on every generate_image call; lock product identity and person likeness across the set.',
    category: 'social', cover: cover('social'), quickStartCover: quickStartCover('social'), featured: feedCovers('social'), video: video('social'), examples: ex541('social', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
    presets: [P('ugc-feed', '时尚UGC信息流 1:1', 'Fashion UGC feed 1:1', 'Style: candid off-duty fashion UGC still, 1:1 feed crop, real-person feel, product clearly in frame, never staged studio look, natural everyday light.'), P('ugc-story', '时尚UGC故事 9:16', 'Fashion UGC story 9:16', 'Style: candid off-duty fashion UGC still, 9:16 story crop, real-person energy, product in hand or worn, never staged studio backdrop, mobile-first.')],
    inputs: [I('file', ['上传文件', 'Upload file'], 'image'), I('productRef', ['商品参考', 'Product reference'], 'image'), I('personRef', ['人物/穿搭参考', 'Person / outfit reference'], 'image'), I('note', ['补充描述', 'Additional notes'], 'textarea', false, ['有什么想补充的吗？频道、场景或必须入镜的单品', 'Anything to add? Channel, scene, or must-show product'])] },
  { id: 'brand', name: t('skills.brandIdentity'), instructions: 'You are a production brand-identity designer. Deliver a usable VI kit, not a single decorative mark.\n1) Discover: brand name, category, positioning and any elements to keep from brandInfo and brandAssets.\n2) Mark: design a primary logo mark on a plain background (1:1). State shape language, hex colors and type style precisely.\n3) System board: color palette swatches, primary + secondary lockups, and a clear typography specimen.\n4) Applications: at least one stationery or object mockup applying the mark; keep geometry identical across frames.\n5) Scope: when a template is selected, follow that template focus (logo system board vs mockup). Do not invent a new category.\n6) Refs: when brandAssets are uploaded, pass each shape id in refs (ref_modes content) on every generate_image call.',
    category: 'branding', cover: cover('brand'), quickStartCover: quickStartCover('brand'), featured: feedCovers('brand'), video: video('brand'), presets: [P('geometric', '极简几何', 'Minimal geometric', 'Style: minimal geometric mark built from simple shapes, strict grid, two-color palette; deliver primary mark, lockup and palette board production-ready.', wash541(WASH_541.brand, 'brand', 'geometric')), P('handmade', '手作温暖', 'Handmade warmth', 'Style: hand-drawn warm mark, organic lines, earthy palette, craft paper textures; deliver primary mark plus warm stationery application.', wash541(WASH_541.brand, 'brand', 'handmade')), P('tech', '科技未来', 'Tech future', 'Style: futuristic tech identity, precise linework, gradient-free electric blue accents, monospace details; deliver mark, lockup and UI-ready glyph.', wash541(WASH_541.brand, 'brand', 'tech')), P('beauty', '美妆个护', 'Beauty & personal care', 'Style: beauty and personal care logo system presentation board, soft refined mark with primary and secondary lockups, monogram, color swatches and typography specimen laid out on a clean board, no product mockups.', wash541(WASH_541.brand, 'brand', 'beauty')), P('foodbev', '食品饮料', 'Food & beverage', 'Style: food and beverage logo system presentation board, lively mark with primary and stacked lockups, icon variant, color swatches and typography specimen laid out on a clean board, no product mockups.', wash541(WASH_541.brand, 'brand', 'foodbev')), P('pet', '宠物用品', 'Pet supplies', 'Style: pet supplies logo system presentation board, friendly playful mark with primary and secondary lockups, mascot icon, color swatches and typography specimen laid out on a clean board, no product mockups.', wash541(WASH_541.brand, 'brand', 'pet'))],
    inputs: [I('brandInfo', ['品牌资料', 'Brand details'], 'text', true, ['简单介绍品牌名称和主营业务，已有定位或要沿用的元素也写上', 'Brand name and main business, plus any positioning or elements to keep']), I('brandAssets', ['品牌素材', 'Brand assets'], 'image'), VISUAL] },
  { id: 'packaging', name: t('skills.packagingDesign'), instructions: 'You are a production packaging designer. Deliver shelf-ready concepts through structure, not flat posters.\n1) Brief: product, size, pack form and brand cues from packInfo and packAssets.\n2) Front: package front view on a clean studio background; call out material, finish and label layout.\n3) Structure: when relevant, show dieline / panel logic or a clear 3/4 mockup in context.\n4) Shelf: ensure the design reads at eye level in a retail row; keep logo and claims legible.\n5) Apply the selected packaging style focus (eco, foil, playful, panels, shelf).\n6) Refs: when packAssets are uploaded, pass shape ids in refs (ref_modes content) on every generate_image call.',
    category: 'ecommerce', cover: cover('packaging'), quickStartCover: quickStartCover('packaging'), featured: feedCovers('packaging'), video: video('packaging'), presets: [P('eco', '自然环保', 'Natural eco', 'Style: natural eco packaging, kraft and recycled paper, botanical line art, muted greens; show front label hierarchy and material callouts.', wash541(WASH_541.packaging, 'packaging', 'eco')), P('gold', '奢华烫金', 'Luxury gold foil', 'Style: luxury packaging, deep matte color with gold foil stamping, embossed logo; keep foil readable at shelf distance.', wash541(WASH_541.packaging, 'packaging', 'gold')), P('playful', '潮玩插画', 'Playful illustration', 'Style: playful illustrated packaging, bright characters, bold outlines, pop colors; keep character on-pack consistent across panels.', wash541(WASH_541.packaging, 'packaging', 'playful')), P('panels', '展开结构图', 'Panels & structure', 'Style: packaging panels and structural dieline, flat unfolded box with front, back and side panels laid out.', wash541(WASH_541.packaging, 'packaging', 'panels')), P('shelf', '货架陈列', 'Shelf display', 'Style: packaging shelf display, the product repeated in rows on a retail shelf, eye-level store lighting.', wash541(WASH_541.packagingShelf, 'packaging', 'shelf'))],
    inputs: [I('packInfo', ['商品与包装资料', 'Product & packaging details'], 'text', true, ['简单说明要包装的商品、规格和包装形式', 'What product is being packaged, its size and package type']), I('packAssets', ['商品与包装素材', 'Product & packaging assets'], 'image'), VISUAL] },
  // #641 Phase3-S2: YouTube 16:9 CTR thumbnail — dialog parity Upload+Additional only (no presets / no required titleCopy); keep id; DO NOT invent youtube-thumbnail id.
  // Media: #643 true-wash cover/examples/featured (kie); hover video stays Phase1 until video wash.
  { id: 'thumbnail', name: t('skills.youtubeThumbnail'), instructions: 'You are a production YouTube thumbnail designer for 16:9 click-rate covers. Deliver thumb-stop frames built for mobile feed CTR, not vague key art or short-drama posters.\n1) Brief: from upload and notes, lock the video topic, emotion, and 16:9 YouTube crop; treat vertical short-drama only as a secondary path when the brief explicitly asks.\n2) Hook triad: one oversized expressive face or reaction, a three-word bold title in quotes, and extreme high contrast so the frame reads at phone-grid size.\n3) Type: prefer exactly three punchy words; keep lettering thick, high-contrast, and clear of faces; never more than a short phrase in quotes on-art.\n4) Variants: offer 2 crops or emotion shifts that keep the same three-word lockup and subject identity.\n5) Refs: when a face or subject file is uploaded, pass its shape id in refs (ref_modes content) on every generate_image call; lock likeness across variants.',
    category: 'social', cover: cover643('thumbnail'), quickStartCover: quickStartCover('thumbnail'), featured: feat643('thumbnail', [1, 2, 3, 4]), video: video('thumbnail'), examples: [video('thumbnail'), ...ex643('thumbnail', [1, 2, 3, 4, 5, 6])],
    inputs: EFFECT_INPUTS },
  { id: 'banner', name: t('skills.bannerDesign'), instructions: 'You are a production banner designer for web and campaign placement. Deliver crop-safe wide frames, not square posts.\n1) Brief: campaign goal, offer and placement width from the upload and notes.\n2) Layout: wide 21:9 or 16:9; headline on one side, visual on the other; clear CTA text in quotes.\n3) Safe margins: protect type and logo from edge crop across common ad slots.\n4) Hierarchy: one focal product or scene; avoid cluttered multi-offer walls.\n5) Refs: when a file is uploaded, pass its shape id in refs (ref_modes content) on every generate_image call.',
    category: 'ads', cover: cover('banner'), quickStartCover: quickStartCover('banner'), featured: feedCovers('banner'), video: video('banner'), examples: [video('banner'), ...ex541('banner', [1])],
    inputs: EFFECT_INPUTS },
  { id: 'character', name: t('skills.characterSheet'), instructions: 'You are a production character-sheet designer. Deliver turnaround-ready reference boards for downstream art and IP.\n1) Lock identity: from characterRef and characterInfo, freeze face, body, outfit colors and key props.\n2) Board: follow the selected template (turnaround, expression, modeling detail, outfit, prop, basic, technical, editorial).\n3) Consistency: identical proportions, palette and costume language across every cell in the sheet.\n4) Presentation: prefer clean backgrounds; label nothing with stray UI chrome; keep sheets readable as production refs.\n5) Refs: when characterRef images are uploaded, pass each shape id in refs (ref_modes content) on every generate_image call.',
    cover: cover('character'), quickStartCover: quickStartCover('character'), featured: feedCovers('character'), video: video('character'), featuredPreset: 'editorial', presets: [P('turnaround', '角色转身板', 'Character Turnaround Sheet', 'Template: character turnaround sheet, full-body front, side and back views evenly spaced in one row on a white background.', wash569('character', 0)), P('expression', '表情动作板', 'Expression & Pose Sheet', 'Template: expression and pose sheet, a row of head-shot expressions above full-body poses (standing, walking, sitting).', wash569('character', 1)), P('modeling', '建模细节参考板', 'Modeling Detail Reference Sheet', 'Template: modeling detail reference sheet, full-body angles on the left and close-up cells of face, eyes, lips, ears, hair, hands and shoes on the right.', wash569('character', 2)), P('outfit', '服装/形态变体板', 'Outfit / Form Variation Sheet', 'Template: outfit variation sheet, the same character in three different outfits shown full body side by side.', wash569('character', 3)), P('prop', '道具互动板', 'Prop Interaction Sheet', 'Template: prop interaction sheet, full-body poses holding a prop on top and close-up cells of hands and prop below.', wash569('character', 4)), P('basic', '基础角色板', 'Basic Character Sheet', 'Template: basic character sheet, full-body three views on the left and four head-shot expressions on the right.', wash569('character', 5)), P('technical', '完整技术角色板', 'Complete Technical Character Sheet', 'Template: complete technical character sheet, multi-angle full body, an expression grid, outfit items, color swatches and detail close-ups.', wash569('character', 6)), P('editorial', '时装大片角色板', 'Editorial Fashion Sheet', 'Template: editorial fashion sheet, the reference character as the lead in a luxury-brand fashion campaign style; full-body standing pose, half-body and face close-ups of the same person, keeping facial features, hairstyle and body shape consistent, soft studio lighting, clean light background, no text or logos.', wash569('character', 7))],
    inputs: [I('characterRef', ['角色参考图片', 'Character reference images'], 'image'), I('characterInfo', ['角色资料', 'Character details'], 'text', false, ['描述角色外观，以及这次需要保持一致的地方', 'Describe the look and what must stay consistent this time']), VISUAL] },
  { id: 'product', name: t('skills.eCommerceProductImages'), instructions: 'You are a production e-commerce product photographer / art director. Deliver listing-ready image sets for Amazon, Taobao and A+.\n1) Lock the product: from productImage and productInfo, keep silhouette, materials, logo and color identical in every frame.\n2) Hero: clean white-background 1:1 main image, soft shadow, product centered.\n3) Set: add lifestyle context and a material detail close-up; for A+ style, plan a clear benefit sequence without rewriting claims as paragraphs.\n4) Apply the selected shot focus (white, lifestyle, detail, electronics, food, beauty).\n5) Refs: ALWAYS pass the product image shape id in refs (ref_modes content) on every generate_image call; describing it in the prompt does not send the image.',
    category: 'ecommerce', cover: cover('product'), quickStartCover: quickStartCover('product'), featured: feedCovers('product'), video: video('product'), presets: [P('white', '白底主图', 'White background hero', 'Focus on the white-background hero shot: pure white seamless background, soft shadow, product centered; listing-ready 1:1 main image.', washProduct541('white')), P('lifestyle', '生活场景', 'Lifestyle scene', 'Focus on the lifestyle scene: product in use in a realistic home setting, natural light; keep product identity locked to the hero.', washProduct541('lifestyle')), P('detail', '细节特写', 'Detail close-up', 'Focus on the detail close-up: macro view of material and craftsmanship, shallow depth of field; useful as A+ or PDP inset.', washProduct541('detail')), P('electronics', '数码电子', 'Electronics', 'Focus on the electronics hero: earbuds and their charging case on a clean studio backdrop, crisp reflections, precise edges.', washProduct541('electronics')), P('food', '美食', 'Food', 'Focus on the food hero: appetizing close shot, fresh ingredients as props, warm natural light, rich texture.', washProduct541('food')), P('beauty', '美妆个护', 'Beauty', 'Focus on the beauty hero: skincare or cosmetic product on soft pastel surfaces, gentle diffused light, clean premium mood.', washProduct541('beauty'))],
    inputs: [I('productImage', ['商品图片', 'Product images'], 'image', true), I('productInfo', ['商品资料', 'Product details'], 'text', false, ['补充商品名称、真实卖点和使用场景', 'Product name, real selling points and use cases']), VISUAL] },
  { id: 'motion', name: t('skills.motionPoster'), instructions: 'You are a production motion designer for UGC ads, product TVC stills-to-video and poster animation.\n1) Still first: if stillArt is missing, generate a strong 3:4 or 9:16 key still with generate_image and wait for it.\n2) Animate: drive animate_image from that image shape with subtle, readable motion (loop on); keep titles sharp.\n3) Preset focus: Poster Animation keeps text locked while the scene breathes; First-to-Last Frame Animation morphs cleanly between two planned frames.\n4) Ad intent: prefer product-hero or UGC-style energy over abstract noise; CTA text in quotes when present.\n5) Refs: pass the still shape id into animate_image; never invent motion on a missing frame.',
    category: 'ads', cover: cover('motion'), quickStartCover: quickStartCover('motion'), featured: feedCovers('motion'), video: video('motion'), /* #622: preset.video ← wash-v1 @5a8d22ed */ presets: [P('poster', '海报动画', 'Poster Animation', 'Template: poster animation for ads — lock the still, then subtle looping motion; show static vs animated pair; text stays sharp and readable.', wash569('motion', 0), wash575MotionVideo(WASH_575_MOTION_POSTER)), P('firstlast', '首帧到末帧动画', 'First-to-Last Frame Animation', 'Template: first-to-last frame animation for product TVC beats — plan first and last frames that share layout and transition smoothly.', wash569('motion', 1), wash575MotionVideo(WASH_575_MOTION_FIRSTLAST))],
    inputs: [I('stillArt', ['静态原稿', 'Static artwork'], 'image', true), I('motionNotes', ['动态要求', 'Motion requirements'], 'text', false, ['说明希望怎么动，哪些部分保持不动', 'How it should move and what should stay still']), VISUAL] },
  // #593 Phase1-S3 new 6 instructions+presets; #594 wash pins; dual-fit contain; #623 hover video @ 594/wash/videos.
  // #691/#687: multi-angle dialog parity with the reference card — Upload + Additional only (no presets).
  { id: 'multi-angle', name: t('skills.multiAngleImageGenerator'), instructions: 'You are a production multi-angle catalog photographer. Deliver a locked identity set, not random variants.\n1) Lock: read the uploaded subject image(s) (if none is uploaded, use the subject described in the Additional notes or ask for one; never invent a product unprompted); keep identity, materials, proportions and palette identical across every frame.\n2) Set: default front, 3/4, a pure 90° side profile (camera exactly perpendicular, no 3/4 turn) and one detail/macro on clean matching backgrounds unless the Additional notes say otherwise.\n3) Use: PDP and ads prefer neutral seamless; lifestyle only when the Additional notes ask; with no notes, default to neutral seamless studio light and a PDP-ready four-frame set.\n4) Consistency: same lens height and lighting family; no costume or finish drift between angles.\n5) Refs: pass the subject shape id in refs (ref_modes content) on every generate_image call.',
    category: 'ecommerce',
    cover: cover('multi-angle'), quickStartCover: quickStartCover('multi-angle'), quickStartCoverFit: 'contain',
    featured: feedCovers('multi-angle'), video: video594('multi-angle'), examples: ex594('multi-angle', [1, 2, 3, 4]),
    inputs: MULTI_ANGLE_INPUTS },
  { id: 'logo-material', name: t('skills.logoMaterialExplorer'), instructions: 'You are a production 3D material artist for logo finish studies. Explore materials only — never redesign the mark.\n1) Lock geometry: keep logo paths, proportions and negative space identical to logoImage.\n2) Materials: vary finish only (metal, glass, plastic, fabric, ceramic) per selected preset or materialNotes.\n3) Stage: neutral studio turntable or soft gradient; soft product lighting; no busy brand scenes.\n4) Scope: one material study per frame; do not invent a full VI kit or packaging system.\n5) Refs: pass the logo shape id in refs (ref_modes content) on every generate_image call.',
    category: 'branding',
    cover: cover('logo-material'), quickStartCover: quickStartCover('logo-material'), quickStartCoverFit: 'contain',
    featured: feedCovers('logo-material'), video: video594('logo-material'), examples: ex594('logo-material', [1, 2, 3, 4]),
    presets: [P('metal', '金属拉丝', 'Brushed metal', 'Style: brushed metal 3D logo material study on a neutral turntable, identical mark geometry, soft studio light, no redesign.'), P('glass', '透明玻璃', 'Clear glass', 'Style: clear glass 3D logo material study with soft refraction, identical mark geometry, soft gradient backdrop.'), P('fabric', '织物绣章', 'Fabric emblem', 'Style: woven fabric or embroidered emblem material study of the same logo, identical geometry, soft studio light.'), P('ceramic', '陶瓷釉面', 'Ceramic glaze', 'Style: glazed ceramic 3D logo material study, identical mark geometry, soft highlight, neutral seamless set.')],
    inputs: [I('logoImage', ['Logo 图片', 'Logo image'], 'image', true), I('materialNotes', ['材质偏好', 'Material preferences'], 'text', false, ['想试的材质、光泽或场景，可留空', 'Materials, finishes or scenes to try; leave blank if none']), VISUAL] },
  { id: 'meta-ads', name: t('skills.metaAdsCreative'), instructions: 'You are a production Meta paid-social creative director. Ship a ratio pack that shares one idea.\n1) Brief: pull product, audience, offer and CTA from campaignBrief; put every on-art phrase in quotes.\n2) Ratios: deliver 1:1 feed, 4:5 feed and 9:16 story/reel that share motif, palette and CTA.\n3) Treatment: prefer photo-led UGC or product-hero; avoid static website-banner layouts.\n4) Mobile: short high-contrast type; safe margins for UI chrome; one clear CTA.\n5) Refs: when adAssets are uploaded, pass each shape id in refs (ref_modes content) on every generate_image call.',
    category: 'ads',
    cover: cover('meta-ads'), quickStartCover: quickStartCover('meta-ads'), quickStartCoverFit: 'contain',
    featured: feedCovers('meta-ads'), video: video594('meta-ads'), examples: ex594('meta-ads', [1, 2, 3, 4]),
    presets: [P('feed1x1', '信息流 1:1', 'Feed 1:1', 'Style: Meta feed 1:1 paid creative, photo-led product hero, short high-contrast CTA in quotes, mobile-first.'), P('feed4x5', '信息流 4:5', 'Feed 4:5', 'Style: Meta feed 4:5 paid creative sharing the same campaign idea and CTA in quotes, taller crop, mobile-first.'), P('story9x16', '故事 9:16', 'Story 9:16', 'Style: Meta story/reel 9:16 creative, same campaign motif and CTA in quotes, safe margins for UI chrome.'), P('ugc', 'UGC 口播风', 'UGC talking-head', 'Style: UGC-style Meta creative, handheld energy, authentic product-in-hand moment, short CTA in quotes, not a website banner.')],
    inputs: [I('campaignBrief', ['投放简报', 'Campaign brief'], 'text', true, ['产品、受众、卖点与 CTA', 'Product, audience, offer and CTA']), I('adAssets', ['投放素材', 'Ad assets'], 'image'), VISUAL] },
  { id: 'mobile-ui', name: t('skills.mobileAppVisualDesign'), instructions: 'You are a production mobile product designer. Deliver coherent app UI screens, not marketing posters.\n1) System: one type scale, spacing rhythm and component language across the requested flows.\n2) Frames: phone-framed mockups at about 9:19.5; clear hierarchy and accessible contrast.\n3) Flows: cover 2–4 key screens (home, detail, checkout or onboarding) per brief.\n4) Scope: product UI chrome and content — not a landing-page poster or print layout.\n5) Refs: when uiRefs are uploaded, pass each shape id in refs (ref_modes content) on every generate_image call.',
    category: 'website',
    cover: cover('mobile-ui'), quickStartCover: quickStartCover('mobile-ui'), quickStartCoverFit: 'contain',
    featured: feedCovers('mobile-ui'), video: video594('mobile-ui'), examples: ex594('mobile-ui', [1, 2, 3, 4]),
    presets: [P('home', '首页信息架构', 'Home IA', 'Style: mobile app home screen mockup in a phone frame, clear IA, coherent type and components, product UI not a poster.'), P('detail', '详情页', 'Detail screen', 'Style: mobile app detail screen mockup, strong hierarchy, accessible contrast, same design system as home.'), P('checkout', '结算流程', 'Checkout flow', 'Style: mobile checkout or cart flow screen, trust-first layout, clear primary CTA, same component language.'), P('onboarding', '引导页', 'Onboarding', 'Style: mobile onboarding screen, short copy, one primary action, coherent with the app system, phone-framed.')],
    inputs: [I('appBrief', ['应用与页面资料', 'App & screen brief'], 'text', true, ['应用名称、目标用户与要做的页面', 'App name, audience and screens to design']), I('uiRefs', ['界面参考', 'UI references'], 'image'), VISUAL] },
  { id: 'web-product', name: t('skills.webProductVisualDesign'), instructions: 'You are a production web product visual designer. Ship landing or product-page systems, not printable posters.\n1) System: shared layout grid, illustration/photo treatment and UI chrome across modules.\n2) Ratios: desktop 16:9 hero plus an optional responsive crop when useful.\n3) Modules: hero, feature row and supporting UI that share one visual language.\n4) Copy: keep marketing lines short; put on-art phrases in quotes; focus on layout quality.\n5) Refs: when webRefs are uploaded, pass each shape id in refs (ref_modes content) on every generate_image call.',
    category: 'website',
    cover: cover('web-product'), quickStartCover: quickStartCover('web-product'), quickStartCoverFit: 'contain',
    featured: feedCovers('web-product'), video: video594('web-product'), examples: ex594('web-product', [1, 2, 3, 4]),
    presets: [P('hero', '落地页主视觉', 'Landing hero', 'Style: web product landing hero at 16:9, strong hierarchy, short headline in quotes, coherent UI chrome.'), P('features', '功能模块', 'Feature modules', 'Style: web product feature modules row, shared grid and illustration treatment, desktop product page language.'), P('pricing', '定价区', 'Pricing section', 'Style: web pricing section visual, clear cards, accessible contrast, same system as the hero.'), P('responsive', '响应式裁切', 'Responsive crop', 'Style: responsive crop of the same web product system for a narrower viewport, layout reflowed not letterboxed.')],
    inputs: [I('webBrief', ['产品与页面资料', 'Product & page brief'], 'text', true, ['产品名称、页面目标与关键模块', 'Product name, page goal and key modules']), I('webRefs', ['视觉参考', 'Visual references'], 'image'), VISUAL] },
  { id: 'marketing-campaign', name: t('skills.marketingCampaignGenerator'), instructions: 'You are a production campaign art director. One big idea, then keyed frames across platforms.\n1) Idea: lock brand/product, goal and lead slogan from campaignGoal; put slogans in quotes.\n2) System: shared motif, palette and typography across hero KV, social and display frames.\n3) Adapt: show how the system reflows across ratios without collapsing into a single poster or a Meta-only set.\n4) Deliverables: at least a hero key visual plus social and display adaptations that stay on-system.\n5) Refs: when campaignAssets are uploaded, pass each shape id in refs (ref_modes content) on every generate_image call.',
    category: 'ads',
    cover: cover('marketing-campaign'), quickStartCover: quickStartCover('marketing-campaign'), quickStartCoverFit: 'contain',
    featured: feedCovers('marketing-campaign'), video: video594('marketing-campaign'), examples: ex594('marketing-campaign', [1, 2, 3, 4]),
    presets: [P('kv', '主视觉 KV', 'Hero key visual', 'Style: campaign hero key visual, one big idea, slogan in quotes, strong motif and palette, platform-agnostic master.'), P('social', '社交延展', 'Social extension', 'Style: social extension frames of the same campaign system, adapted ratios, slogan in quotes, not a Meta-only pack.'), P('display', '展示广告', 'Display ads', 'Style: display ad adaptations of the same campaign motif and palette, short copy in quotes, clear hierarchy.'), P('ooh', '户外主画面', 'OOH master', 'Style: out-of-home campaign master of the same big idea, legible at distance, slogan in quotes, shared motif.')],
    inputs: [I('campaignGoal', ['战役目标', 'Campaign goal'], 'text', true, ['品牌/产品、目标与主口号', 'Brand/product, goal and lead slogan']), I('campaignAssets', ['品牌与参考素材', 'Brand & reference assets'], 'image'), VISUAL] },

  // #634/#636 B .ai NEW5 production + #637 S4 soft wash pins (bc-refs hardMax layouts).
  // B .ai NEW5 — left column data-driven: single-video | carousel | single-still (not one hard-coded chrome).
  // C deferred.art5 production fills kept below (examples:[] / featured:[] until a C wash tip).
  { id: 'flash-cut-video', name: t('skills.flashCutVideo'), instructions: 'You are a production flash-cut director. Pipeline: landscape screenshot → multi-style still candidates → user picks one → short flash-cut video. This is not a UGC/TVC/poster-animation motion job.\n1) Intake: require a landscape 16:9 screenshot; preserve UI chrome and readable on-screen text; never invent a different product UI.\n2) Stills first: generate several still style directions from the same screenshot (clean product, neon flash, soft narrative, or the user\'s styleNotes); pause for an explicit pick before animating.\n3) Flash-cut only: animate solely the chosen still into a short beat-driven flash-cut clip; no long talking-head UGC, no TVC narrative arc, no poster Ken-Burns substitute.\n4) Craft: product or UI hero energy, high-contrast cuts, safe margins; put every on-art phrase in quotes.\n5) Refs: pass the screenshot shape id in refs (ref_modes content) on every generate_image and animate/video call.',
    category: 'ads', cover: cover637('flash-cut-video'), video: video637('flash-cut-video'),
    examples: [video637('flash-cut-video')], featured: feat637('flash-cut-video', [1, 2, 3, 4, 5]),
    presets: [P('clean', '干净产品风', 'Clean product', 'Style: clean product flash-cut from the screenshot, high-contrast UI still then short punchy beats, readable chrome, no long UGC.'), P('neon', '霓虹快闪', 'Neon flash', 'Style: neon flash-cut energy from the same screenshot, saturated accents, staccato cuts, UI text stays legible.'), P('soft', '柔光叙事', 'Soft narrative', 'Style: soft narrative flash-cut, gentle motion and light bloom, screenshot UI remains sharp and readable.')],
    inputs: [I('screenshot', ['截图', 'Screenshot'], 'image', true), I('styleNotes', ['风格确认', 'Style notes'], 'text', false, ['选定的闪剪风格或节奏', 'Chosen flash-cut style or pacing']), VISUAL] },
  { id: 'style-transfer', name: t('skills.styleTransfer'), instructions: 'You are a production adaptive style-transfer director. Analyze a style reference, then transfer that look onto the user subject while locking identity. Not a logo-material study and not a full brand VI kit.\n1) Dual intake: require contentImage + styleImage; lock subject identity, silhouette, face/logo marks and key proportions from the content ref.\n2) Style read: extract palette, stroke, lighting, grain and medium cues from the style ref only — never from inventing a new brand system.\n3) Controllable transfer: apply the selected medium preset (illustration / photo / graphic); keep the subject recognizable; do not redesign the logo or ship a multi-asset VI.\n4) Guardrails: no identity drift, no swapping the product, no unrelated scene rewrite unless transferNotes asks for it.\n5) Refs: pass both shape ids in refs (content + style as appropriate) on every generate_image call.',
    category: 'branding', cover: cover637('style-transfer'),
    examples: ex637('style-transfer', [1, 2, 3, 4]), featured: feat637('style-transfer', [1, 2, 3, 4, 5]),
    presets: [P('illustration', '插画迁移', 'Illustration', 'Style: illustration-medium transfer onto the content subject, style-ref palette and stroke, identity and silhouette locked.'), P('photo', '摄影迁移', 'Photography', 'Style: photographic look transfer matching style-ref lighting and grain, subject identity locked, no logo redesign.'), P('graphic', '平面迁移', 'Graphic', 'Style: flat graphic / poster transfer with bold shapes from the style ref, subject readable, single-mark discipline.')],
    inputs: [I('contentImage', ['内容图', 'Content image'], 'image', true), I('styleImage', ['风格参考', 'Style reference'], 'image', true), I('transferNotes', ['迁移说明', 'Transfer notes'], 'text', false, ['要保留或避开的元素', 'What to keep or avoid']), VISUAL] },
  { id: 'person-swap', name: t('skills.personSwap'), instructions: 'You are a production e-commerce person-swap artist. Keep pose and scene; swap person and outfit from three bound refs. Not multi-angle catalog capture and not a character-sheet redesign.\n1) Triple intake: require scenePose (pose/scene base), faceRef, and outfitRef — all three must be present before rendering.\n2) Lock: camera, pose, hands, props and background stay from the base; only identity and wardrobe change.\n3) Deliver: PDP-ready coherent set (hero + useful side/detail crops) with fabric and face readable.\n4) Guardrails: no multi-angle identity drift, no new character bible, no background rewrite; this is swap, not redesign.\n5) Refs: pass all three shape ids in refs on every generate_image call.',
    category: 'ecommerce', cover: cover637('person-swap'),
    examples: ex637('person-swap', [1]), featured: feat637('person-swap', [1, 2, 3]),
    presets: [P('hero', '主图换人', 'Hero swap', 'Style: hero PDP person swap, pose and scene locked from base, new face and outfit from refs.'), P('side', '侧面换人', 'Side swap', 'Style: side-angle person swap on the same locked set, identity from face ref, outfit locked.'), P('detail', '细节换人', 'Detail swap', 'Style: detail crop after person swap, fabric and face readable, scene and pose unchanged.')],
    inputs: [I('scenePose', ['场景姿势底图', 'Scene / pose base'], 'image', true), I('faceRef', ['人脸参考', 'Face reference'], 'image', true), I('outfitRef', ['穿搭参考', 'Outfit reference'], 'image', true), VISUAL] },
  { id: 'commerce-strategist', name: t('skills.commerceStrategist'), instructions: 'You are a production commerce visual strategist. Turn selling points into a confirmed visual strategy board first, then keyed frames. Not a lone main-image generator and not a full marketing-campaign KV system.\n1) Brief: read sellPoints (category, benefits, info hierarchy); optional refAssets inform palette and product truth.\n2) Strategy board first: draft information architecture, shot list and style anchors; confirm with the user before heavy renders.\n3) Then frames: produce keyed frames that follow the board — never a random single hero that ignores the board.\n4) Category honesty: 3C / beauty / food presets keep material, light and claim hierarchy truthful to the category.\n5) Refs: when assets are uploaded, pass shape ids in refs on every generate_image call.',
    category: 'ecommerce', cover: cover637('commerce-strategist'), video: video637('commerce-strategist'),
    examples: [video637('commerce-strategist')], featured: feat637('commerce-strategist', [1, 2, 3, 4, 5]),
    presets: [P('3c', '3C 数码', '3C electronics', 'Style: 3C commerce strategy board then hero frames, crisp tech cues, clear benefit ladder, honest materials.'), P('beauty', '美妆', 'Beauty', 'Style: beauty commerce strategy board then soft premium frames, honest claims hierarchy, clean skin/texture light.'), P('food', '食品', 'Food', 'Style: food commerce strategy board then appetite frames, warm light, clear IA, no fake claims.')],
    inputs: [I('sellPoints', ['卖点与品类', 'Selling points & category'], 'text', true, ['品类、核心卖点与要强调的信息层级', 'Category, key benefits and info hierarchy']), I('refAssets', ['参考素材', 'Reference assets'], 'image'), VISUAL] },
  { id: 'lifestyle-scene', name: t('skills.lifestyleScene'), instructions: 'You are a production e-commerce lifestyle scene designer. Ship textless immersive scenes where the product lives in home or daily-wear context. Distinct from white-bg / A+ listing sets on the product skill.\n1) Textless: prefer no on-art claims, badges or poster copy; if words appear they must be in quotes and sparse.\n2) Immersion: blend the product into real living / casual contexts with natural light and believable scale.\n3) Division of labor: this is scene cinema, not listing grids or A+ modules — leave catalog sets to product.\n4) Identity: keep product shape, label and materials locked when productImage is provided.\n5) Refs: pass product shape ids in refs (ref_modes content) on every generate_image call.',
    category: 'ecommerce', cover: cover637('lifestyle-scene'),
    examples: ex637('lifestyle-scene', [1, 2]), featured: feat637('lifestyle-scene', [1, 2, 3]),
    presets: [P('home', '家居场景', 'Home scene', 'Style: textless home lifestyle scene, product naturally placed, soft daylight, no claim poster.'), P('wear', '日常穿搭', 'Daily wear', 'Style: textless daily-wear lifestyle scene, candid framing, product in use, never studio-staged.'), P('table', '桌面氛围', 'Tabletop mood', 'Style: textless tabletop lifestyle mood, shallow depth, product hero without copy.')],
    inputs: [I('productImage', ['商品图片', 'Product images'], 'image', true), I('sceneBrief', ['场景说明', 'Scene brief'], 'text', false, ['家居/穿搭/氛围偏好', 'Home / wear / mood preferences']), VISUAL] },
  // C deferred .art5 — #636 Phase2-S3 C production (instructions/inputs/presets). B wash landed via #637; C still examples:[].
  { id: 'naive-illustration', name: t('skills.naiveIllustration'), instructions: 'You are a production naive hand-drawn illustrator. Ship giant-object vs tiny-person contrast frames with cafe/worker wit. Not a social-media cover set and not a RedNote sticker pack.\n1) Modes: B/W line draft or soft flat-color object-play — follow the selected preset; keep the giant-vs-mini scale joke unmistakable.\n2) Subject: oversized everyday object (coffee cup, bag, phone, food) with a tiny worker/person interacting; friendly line, simple shapes, limited palette unless brief asks otherwise.\n3) Guardrails: never collapse into a generic social cover grid, fashion UGC set, or crayon-sketch children-book look; this is the scale-joke illustration lane.\n4) Copy: put every on-art phrase in quotes; prefer sparse witty labels over poster headlines.\n5) Refs: when refs are uploaded, pass shape ids in refs (ref_modes content) on every generate_image call.',
    category: 'social', cover: cover636('naive-illustration'),
    examples: ex636('naive-illustration', [1, 2, 3, 4]), featured: feat636('naive-illustration', [1, 2, 3, 4, 5]),
    presets: [P('line', '黑白线稿', 'B/W line', 'Style: naive B/W line illustration, giant object vs tiny person, witty cafe/worker energy, clean strokes.'), P('object', '实物互动', 'Object play', 'Style: naive soft flat-color illustration with interactive oversized object play, friendly limited palette.')],
    inputs: NEARMISS_INPUTS },
  { id: 'logo-abstract', name: t('skills.logoAbstract'), instructions: 'You are a production minimal geometric logo designer. Distill a photo into one scalable geometric mark. Not a 3D material study and not a full brand VI kit.\n1) Intake: require the reference photo; lock the subject traits called out in markNotes when present.\n2) Distill: reduce to a single geometric symbol on a plain ground — two-color preference, strict grid, silhouette that survives tiny sizes.\n3) Scope: one mark only; no stationery system, no packaging, no multi-asset VI board (leave those to brand); distinct from logo-material finish studies.\n4) Presentation: plain ground, optional tiny construction notes; put any on-art words in quotes.\n5) Refs: pass the photo shape id in refs (ref_modes content) on every generate_image call.',
    category: 'branding', cover: cover636('logo-abstract'),
    examples: ex636('logo-abstract', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]), featured: feat636('logo-abstract', [1, 2, 3, 4, 5]),
    presets: [P('circle', '圆形几何', 'Circle geometry', 'Style: minimal circular geometric logo mark distilled from the photo, two-color, scalable silhouette.'), P('angular', '折线几何', 'Angular geometry', 'Style: angular geometric logo mark from the photo, strict grid, plain ground, single-mark discipline.')],
    inputs: NEARMISS_INPUTS },
  { id: 'photo-split-poster', name: t('skills.photoSplitPoster'), instructions: 'You are a production photo-split abstract poster designer. Keep the exact layout: top half original photo, bottom half abstract geometry sampled from its colors. Not a generic flat poster without the photo half.\n1) Intake: require the photo; sample palette strictly from it.\n2) Layout lock: horizontal split — photo above, geometric abstract below; hard or soft edge per preset; never drop the photo half.\n3) Craft: sparse typography if any; every on-art phrase in quotes; prefer portrait/poster ratios suited to ads.\n4) Guardrails: do not morph into a full campaign KV system or a lifestyle scene without the split grammar.\n5) Refs: pass the photo shape id in refs (ref_modes content) on every generate_image call.',
    category: 'ads', cover: cover636('photo-split-poster'),
    examples: ex636('photo-split-poster', [1]), featured: feat636('photo-split-poster', [1, 2, 3]),
    presets: [P('hard', '硬切对半', 'Hard split', 'Style: hard horizontal split poster, photo above, geometric abstract below, palette sampled from the photo.'), P('soft', '柔边对半', 'Soft split', 'Style: soft-edge split poster, photo above, abstract geometry below, shared palette from the photo.')],
    inputs: NEARMISS_INPUTS },
  { id: 'ppt-visual', name: t('skills.pptVisual'), instructions: 'You are a production premium PPT / deck visual designer. Ship modular presentation pages with a shared style library — not print posters and not marketing campaign KVs.\n1) Brief: read deckBrief for topic, page types and style; optional refs set the look library.\n2) Page types: cover, section divider, comparison (and closing when asked) as coherent 16:9 deck frames with one type scale and module system.\n3) Website-chip intent: this lights the website category; keep product-deck language, not printable poster art.\n4) Copy: short on-slide lines in quotes; clear hierarchy; generous margins for projection.\n5) Refs: when refs are uploaded, pass shape ids in refs (ref_modes content) on every generate_image call.',
    category: 'website', cover: cover636('ppt-visual'),
    examples: ex636('ppt-visual', [1]), featured: feat636('ppt-visual', [1, 2, 3]),
    presets: [P('cover', '封面页', 'Cover slide', 'Style: premium deck cover slide 16:9, strong hierarchy, short title in quotes, shared module system.'), P('section', '章节页', 'Section slide', 'Style: section divider slide, modular system coherent with cover, 16:9 projection-safe.'), P('compare', '对比页', 'Comparison slide', 'Style: comparison module slide, clear columns, premium deck language, shared style library.')],
    inputs: NEARMISS_INPUTS },
  { id: 'promo-ecommerce', name: t('skills.promoEcommerce'), instructions: 'You are a production e-commerce promo key-visual designer. Ship big-sale KV plus reusable promo chrome (ribbons, frames, badges). Not a white-bg listing main image and not a full multi-platform marketing-campaign system.\n1) Intake: require productImage and promoBrief (sale theme, offer, dates); lock product identity from the ref.\n2) KV: bold promo hierarchy with product hero, clear claim ladder; put price/claim words in quotes; keep legal honesty.\n3) Chrome: deliver matching reusable promo components (corner badges, borders, ribbons) consistent with the KV.\n4) Division of labor: leave white-bg / A+ listing sets to product; leave brand-wide campaign systems to marketing-campaign.\n5) Refs: pass product shape ids in refs (ref_modes content) on every generate_image call.',
    category: 'ecommerce', cover: cover636('promo-ecommerce'),
    examples: ex636('promo-ecommerce', [1, 2, 3, 4]), featured: feat636('promo-ecommerce', [1, 2, 3, 4, 5]),
    presets: [P('kv', '大促主视觉', 'Promo KV', 'Style: ecommerce promo key visual, bold sale hierarchy, product hero locked from ref, claims in quotes.'), P('badge', '促销组件', 'Promo chrome', 'Style: matching promo badges, ribbons and frames for the same sale system, reusable chrome.')],
    inputs: NEARMISS_INPUTS },
  // D style4 (KEEP for full 15)
  { id: 'yingzao', name: t('skills.yingzao'), instructions: 'Yingzao local editorial poster: real heritage streets / local food travel photos into Chinese display-type edit posters.\n1) Never invent architecture without a photo basis.\n2) Pair the photo with careful Chinese display typography in quotes.\n3) Editorial poster mood; keep place honesty.\n4) Prefer 3:4 or 4:5 social crops.\n5) Refs: pass photo shape ids in refs on every generate_image call.',
    category: 'social', examples: [], featured: [],
    presets: [P('street', '街巷编辑', 'Street edit', 'Style: local street editorial poster from a real photo, Chinese display type in quotes.'), P('food', '在地食物', 'Local food', 'Style: local food travel editorial poster, honest photo base, display type in quotes.')],
    inputs: [I('placePhoto', ['在地照片', 'Place photo'], 'image', true), I('editNotes', ['编辑说明', 'Edit notes'], 'text', false, ['标题与语气', 'Title and tone']), VISUAL] },
  { id: 'crt-interface', name: t('skills.crtInterface'), instructions: 'CRT retro interface illustration: theme → early CRT computer UI look.\n1) Scanlines, phosphor glow, chunky widgets; multiple colorway presets.\n2) Keep the theme readable inside the faux UI.\n3) Not a flat modern dashboard.\n4) On-screen strings in quotes.\n5) Refs: when refs are uploaded, pass shape ids in refs on every generate_image call.',
    category: 'social', examples: [], featured: [],
    presets: [P('green', '绿色磷光', 'Green phosphor', 'Style: green phosphor CRT interface illustration of the theme, scanlines, chunky widgets.'), P('amber', '琥珀磷光', 'Amber phosphor', 'Style: amber CRT interface illustration, warm glow, early computer UI chrome.'), P('blue', '冷蓝终端', 'Cold blue terminal', 'Style: cold blue CRT terminal UI illustration, scanlines, readable theme labels in quotes.')],
    inputs: [I('theme', ['主题', 'Theme'], 'text', true, ['界面主题或产品名', 'UI theme or product name']), I('refs', ['参考', 'References'], 'image'), VISUAL] },
  { id: 'crayon-sketch', name: t('skills.crayonSketch'), instructions: 'Rough crayon / oil-pastel sketch: turn a realistic subject into children-book crayon energy.\n1) Distinct from naive giant-object cafe illustration.\n2) Visible crayon strokes, soft wax texture, playful proportion.\n3) Keep subject recognizable.\n4) Minimal text; any words in quotes.\n5) Refs: pass subject shape id in refs on every generate_image call.',
    category: 'social', examples: [], featured: [],
    presets: [P('wax', '蜡笔涂鸦', 'Crayon doodle', 'Style: rough crayon doodle of the subject, wax texture, playful child-book energy.'), P('pastel', '油画棒', 'Oil pastel', 'Style: oil-pastel sketch of the subject, thick strokes, soft blend, recognizable form.')],
    inputs: [I('subject', ['主体图', 'Subject'], 'image', true), I('notes', ['风格说明', 'Style notes'], 'text', false, ['可留空', 'Optional']), VISUAL] },
  { id: 'fabric-collage', name: t('skills.fabricCollage'), instructions: 'Fabric collage: mix ≥5 textile materials with real stitch and frayed-edge craft.\n1) Not a flat paper collage poster — emphasize cloth, thread and DIY handwork.\n2) Show mixed weaves, knits and trims in one composition.\n3) Keep tactile honesty; soft studio or craft-table light.\n4) Minimal text; words in quotes if any.\n5) Refs: pass refs in refs on every generate_image call.',
    category: 'social', examples: [], featured: [],
    presets: [P('craft', '手工桌面', 'Craft table', 'Style: fabric collage on a craft table, ≥5 textiles, visible stitches and frayed edges.'), P('wall', '布艺墙饰', 'Textile wall', 'Style: textile wall collage, mixed fabrics, handmade stitch character, tactile depth.')],
    inputs: [I('brief', ['主题说明', 'Theme brief'], 'text', true, ['拼贴主题与材质偏好', 'Collage theme and material prefs']), I('refs', ['参考', 'References'], 'image'), VISUAL] },
  // #640/#642/#643 Phase3 — 19 NEW skills; cover643 pins; NEARMISS_INPUTS (Upload+Additional); examples/featured empty until fuller gold; no competitor copy. Dropped-13 out.
  { id: 'taobao-product', name: t('skills.taobaoProduct'), instructions: 'You are a production Taobao listing visual designer. Ship a Chinese PDP set — not an Amazon white-bg catalog set.\n1) Brief: product, selling points and module list from productImage + sellPoints; keep product identity locked.\n2) Modules: main image, carousel frames, lifestyle scene and detail-page benefit blocks with Chinese claim hierarchy.\n3) Division: this is Taobao page system work; leave Amazon/A+ listing grids to the product skill.\n4) Copy: put every on-art Chinese phrase in quotes; mobile-legible.\n5) Refs: pass product shape ids in refs (ref_modes content) on every generate_image call.',
    category: 'ecommerce', cover: cover643('taobao-product'), examples: ex643('taobao-product', [1, 2, 3, 4, 5, 6, 7, 8]), featured: [],
    presets: [P('main', '主图', 'Main image', 'Style: Taobao 1:1 main image, clean product hero, Chinese claim space reserved, high thumb-stop contrast.'), P('scene', '场景图', 'Scene', 'Style: Taobao lifestyle scene with product in use, Chinese benefit callout in quotes.'), P('detail', '详情模块', 'Detail module', 'Style: Taobao detail-page benefit module, stacked claims in quotes, product truth locked.')],
    inputs: NEARMISS_INPUTS },
  { id: 'before-after', name: t('skills.beforeAfter'), instructions: 'You are a production before/after visual designer. Ship dual-state comparison frames — not a single hero still.\n1) Lock composition: same camera, crop and subject placement across before and after.\n2) States: clear before vs after (treatment, remodel, makeup or space) with readable split or side-by-side.\n3) Presets: beauty, home remodel, body/fitness as asked.\n4) Copy: short labels in quotes only when needed.\n5) Refs: pass refs in refs on every generate_image call.',
    category: 'ads', cover: cover643('before-after'), examples: ex643('before-after', [1, 2, 3, 4, 5, 6, 7, 8]), featured: [],
    presets: [P('beauty', '美妆对比', 'Beauty', 'Style: beauty before/after, same crop and lighting, clear dual-state split, readable faces.'), P('home', '家装对比', 'Home remodel', 'Style: interior remodel before/after, matched camera, dual-state layout.'), P('fitness', '身材对比', 'Body / fitness', 'Style: fitness before/after, matched pose and crop, dual-state comparison.')],
    inputs: NEARMISS_INPUTS },
  { id: 'anim-2d', name: t('skills.anim2d'), instructions: 'You are a production 2D animation converter. Pipeline: still or layered art → short 2D animated clip. Not UGC/TVC motion and not flash-cut screenshot video.\n1) Intake: require primary visual; optional layers or styleNotes.\n2) Confirm duration and ratio with the user before animating.\n3) Animate with readable 2D motion (loops OK); keep line and color honest to the still.\n4) Scope: short 2D piece only — no long narrative TVC, no flash-cut UI beats.\n5) Refs: pass shape ids in refs on every generate_image / animate call.',
    category: 'ads', cover: cover643('anim-2d'), examples: ex643('anim-2d', [1, 2, 3], '51ee77b3dd3979e6c249c0390b931a9a520da1c0'), featured: [],
    presets: [P('clean', '干净动效', 'Clean motion', 'Style: clean 2D animation from the still, short loop, readable motion, locked palette.'), P('punchy', '节奏动效', 'Punchy motion', 'Style: punchy 2D animation beats from the still, short runtime, high energy.')],
    inputs: NEARMISS_INPUTS },
  { id: 'creator-identity', name: t('skills.creatorIdentity'), instructions: 'You are a production creator identity designer for personal channels — not a full corporate VI kit.\n1) Brief: nickname, persona and channels from creatorInfo + refs.\n2) Kit: avatar, channel/cover set, palette and social templates that share one look.\n3) Presets: YouTube, RedNote/Xiaohongshu, podcast as asked.\n4) Scope: personal creator system; do not invent a multi-industry brand bible.\n5) Refs: pass refs in refs on every generate_image call.',
    category: 'branding', cover: cover643('creator-identity'), examples: ex643('creator-identity', [1], '3e2df6b2192a6600f3b32d394f8fd5ab820ca98b'), featured: [],
    presets: [P('youtube', 'YouTube套件', 'YouTube kit', 'Style: creator YouTube identity kit — avatar, banner-safe cover, palette chips, consistent persona.'), P('xhs', '小红书套件', 'RedNote kit', 'Style: creator RedNote identity kit — avatar, cover, palette, feed-ready frames.'), P('podcast', '播客套件', 'Podcast kit', 'Style: creator podcast identity kit — avatar, show cover, palette, simple lockups.')],
    inputs: NEARMISS_INPUTS },
  { id: 'product-website', name: t('skills.productWebsite'), instructions: 'You are a production product-website designer for hardware / consumer electronics. Ship landing modules with hero + specs — not a SaaS component library.\n1) Brief: product, specs and brand cues from siteBrief + refs.\n2) Modules: hero, spec grid and supporting sections that share one visual system.\n3) Division: hardware product site language; leave SaaS UI kits to web-product.\n4) Copy: short on-art lines in quotes.\n5) Refs: pass refs in refs on every generate_image call.',
    category: 'website', cover: cover643('product-website'), examples: ex643('product-website', [1, 2, 3]), featured: [],
    presets: [P('hero', '英雄首屏', 'Hero', 'Style: hardware product site hero, strong product shot, short headline in quotes, 16:9.'), P('specs', '规格模块', 'Specs module', 'Style: product specs module, clear grid, hardware truth, coherent with hero.')],
    inputs: NEARMISS_INPUTS },
  { id: 'studio-model', name: t('skills.studioModel'), instructions: 'You are a production studio model apparel photographer. Ship studio-lit lookbook stills — not street Fashion UGC and not lifestyle cinema.\n1) Brief: garment, model cues and shot list from garmentRef + brief.\n2) Lighting: controlled studio; full / half / detail as preset.\n3) Product in frame when asked; keep fabric and fit honest.\n4) Division: studio apparel catalog energy — not candid UGC, not home lifestyle scenes.\n5) Refs: pass shape ids in refs on every generate_image call.',
    category: 'ecommerce', cover: cover643('studio-model'), examples: ex643('studio-model', [1, 2], '9ca3c35db7868e9fe73fb98bf85058c8fa2e048e'), featured: [],
    presets: [P('full', '全身', 'Full body', 'Style: studio full-body apparel shot, controlled light, garment truth, clean backdrop.'), P('half', '半身', 'Half body', 'Style: studio half-body apparel shot, fabric readable, soft controlled light.'), P('detail', '特写', 'Detail', 'Style: studio apparel detail close-up, stitch and material honest, controlled light.')],
    inputs: NEARMISS_INPUTS },
  { id: 'youtube-channel-banner', name: t('skills.youtubeChannelBanner'), instructions: 'You are a production YouTube channel-art designer. Ship 2560×1440 channel banners with safe areas — not a single-video thumbnail and not a promo banner ad.\n1) Brief: channel name, niche and series identity from channelInfo + refs.\n2) Layout: 2560×1440 art; protect TV/desktop/mobile safe areas for title and face.\n3) Series: keep a repeatable channel look across refreshes.\n4) Division: channel art only — leave clickable 16:9 video thumbs to thumbnail.\n5) Refs: pass refs in refs on every generate_image call.',
    category: 'social', cover: cover643('youtube-channel-banner'), examples: ex643('youtube-channel-banner', [1, 2, 3, 4, 5, 6, 7, 8, 9], '5ff0d28d04a9447c649bd775430e990b2690184e'), featured: [],
    presets: [P('series', '系列识别', 'Series identity', 'Style: YouTube channel banner 2560×1440, series identity, safe-area protected title/face.'), P('face', '人像安全区', 'Face safe area', 'Style: YouTube channel banner with face in safe area, niche cue, high contrast.')],
    inputs: NEARMISS_INPUTS },
  { id: 'ai-model', name: t('skills.aiModel'), instructions: 'You are a production AI model identity designer. Lock a reusable virtual model (face/body/ethnicity cues) then dress them across outfits and scenes — not a one-shot person-swap and not a character sheet bible.\n1) Intake: modelSpec + outfit/scene refs; freeze identity across frames.\n2) Consistency: same face, body and skin language when wardrobe/scene changes.\n3) Deliver: multi-outfit / multi-scene set that reads as one model.\n4) Division: reusable identity — leave triple-ref pose swap to person-swap; leave turnaround sheets to character.\n5) Refs: pass shape ids in refs on every generate_image call.',
    category: 'ecommerce', cover: cover643('ai-model'), examples: [], featured: [],
    presets: [P('lock', '锁定身份', 'Lock identity', 'Style: establish reusable virtual model identity, clear face/body cues, neutral studio.'), P('outfit', '多着装', 'Multi outfit', 'Style: same AI model identity in a new outfit, identity locked, catalog-ready.'), P('scene', '多场景', 'Multi scene', 'Style: same AI model identity in a new scene, identity locked, coherent light.')],
    inputs: NEARMISS_INPUTS },
  { id: 'product-to-packaging', name: t('skills.productToPackaging'), instructions: 'You are a production product-to-packaging system designer. Start from a product photo and invent pack structure + hero art + shelf — distinct from brief-first packaging.\n1) Intake: require productImage; optional packNotes.\n2) Deliver: structure/dieline logic, front hero, and shelf row when asked (box/bottle/pouch presets).\n3) Identity: keep product silhouette and label cues honest to the upload.\n4) Cross-link: this starts from product truth; brief-only packaging stays on packaging.\n5) Refs: pass product shape id in refs on every generate_image call.',
    category: 'ecommerce', cover: cover643('product-to-packaging'), examples: ex643('product-to-packaging', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14], '6b1cfa37e4eafc72841e70a26909750c2ff44399'), featured: [],
    presets: [P('box', '盒装', 'Box', 'Style: product-to-box packaging system, structure + front hero from the product photo.'), P('bottle', '瓶装', 'Bottle', 'Style: product-to-bottle packaging, label hierarchy from the product photo.'), P('pouch', '袋装', 'Pouch', 'Style: product-to-pouch packaging, material and seal cues from the product photo.')],
    inputs: NEARMISS_INPUTS },
  { id: 'game-art', name: t('skills.gameArt'), instructions: 'You are a production game art and ops visual designer. Ship concept, key art and event/ops frames for game marketing.\n1) Brief: title, genre and deliverable type from gameBrief + refs.\n2) Presets: concept, KV/key art, event/ops poster as asked.\n3) Craft: readable silhouettes, strong hierarchy, platform-safe margins.\n4) Copy: short titles in quotes.\n5) Refs: pass refs in refs on every generate_image call.',
    category: 'ads', cover: cover643('game-art'), examples: ex643('game-art', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20], 'd325f4a0f7ddedcef4c47052bc725c30c681856b'), featured: [],
    presets: [P('concept', '概念图', 'Concept', 'Style: game concept art, strong silhouette, genre-true mood, production-ready.'), P('kv', 'Key Art', 'Key art', 'Style: game key art / KV, hero composition, title-safe area, marketing punch.'), P('event', '活动图', 'Event / ops', 'Style: game ops/event visual, clear offer hierarchy, short title in quotes.')],
    inputs: NEARMISS_INPUTS },
  { id: 'portrait-studio', name: t('skills.portraitStudio'), instructions: 'You are a production portrait-studio photographer. Ship single-subject portrait stills with controllable beauty and lens — not ecommerce apparel catalog.\n1) Brief: subject cues, beauty and location from portraitBrief + refs.\n2) Craft: studio or environmental light; focal-length feel as asked.\n3) Subject: single person primary; honest skin and styling.\n4) Division: portrait craft — leave apparel product-in-hand studio sets to studio-model.\n5) Refs: pass refs in refs on every generate_image call.',
    category: 'social', cover: cover643('portrait-studio'), examples: ex643('portrait-studio', [1, 2, 3, 4, 5, 6], 'd182b5cc030a87cc1911108b735df2cb2c3863fc'), featured: [],
    presets: [P('studio', '棚拍人像', 'Studio portrait', 'Style: studio portrait, controlled light, beauty-true, single subject.'), P('env', '环境人像', 'Environmental', 'Style: environmental portrait, natural or location light, single subject, lens character.')],
    inputs: NEARMISS_INPUTS },
  { id: 'premium-website', name: t('skills.premiumWebsite'), instructions: 'You are a production premium website art director. Ship luxury brand site direction and first-screen frames — not SaaS component docs and not hardware spec pages.\n1) Brief: brand, tone and pages from siteBrief + refs.\n2) Art direction: refined typography, photography treatment and hero modules.\n3) Division: premium brand site — leave product-spec hardware sites to product-website; leave SaaS UI kits to web-product.\n4) Copy: sparse elegant lines in quotes.\n5) Refs: pass refs in refs on every generate_image call.',
    category: 'website', cover: cover643('premium-website'), examples: ex643('premium-website', [1, 2, 3, 4, 5, 6, 7], '4ccecac30c1cdf3e79826de5614edc5514e150a4'), featured: [],
    presets: [P('hero', '高端首屏', 'Premium hero', 'Style: premium brand site hero, art-directed photography, sparse headline in quotes.'), P('system', '艺术方向板', 'Art direction board', 'Style: premium web art-direction board, type/palette/photo language, cohesive.')],
    inputs: NEARMISS_INPUTS },
  { id: 'animated-poster', name: t('skills.animatedPoster'), instructions: 'You are a production animated-poster designer. Still poster composition first, then a short looping motion poster — not a static print poster and not a long motion ad.\n1) Still first: lock a strong poster hierarchy; confirm specs.\n2) Animate: short loop; keep type sharp; subtle scene motion.\n3) Scope: motion poster only — leave long UGC/TVC to motion.\n4) Copy: on-art phrases in quotes.\n5) Refs: pass refs in refs on every generate_image / animate call.',
    category: 'ads', cover: cover643('animated-poster'), examples: ex643('animated-poster', [1, 2], '54cc1199ee8eeaaee36c69d04cdbad21f345c8fd'), featured: [],
    presets: [P('loop', '短循环', 'Short loop', 'Style: animated poster short loop, type locked, subtle motion, poster hierarchy.'), P('punch', '节奏海报', 'Punchy poster', 'Style: punchy animated poster, short beats, high contrast, readable title.')],
    inputs: NEARMISS_INPUTS },
  { id: 'pose-fission', name: t('skills.poseFission'), instructions: 'You are a production ecommerce pose-fission artist. Keep scene, character and lighting; explode poses — opposite of person-swap (which changes person/outfit and keeps pose).\n1) Intake: require baseImage; lock background, light and identity.\n2) Fission: generate multiple poses of the same character in the same scene.\n3) Guardrails: no identity swap, no background rewrite, no outfit redesign unless asked.\n4) Division: multi-pose same scene — leave triple-ref person/outfit swap to person-swap.\n5) Refs: pass base shape id in refs on every generate_image call.',
    category: 'ecommerce', cover: cover643('pose-fission'), examples: [], featured: [],
    presets: [P('stand', '站姿裂变', 'Standing set', 'Style: same-scene pose fission, standing variations, light and background locked.'), P('sit', '坐姿裂变', 'Seated set', 'Style: same-scene pose fission, seated variations, identity and light locked.'), P('gesture', '手势裂变', 'Gesture set', 'Style: same-scene pose fission, hand/gesture variations, background locked.')],
    inputs: NEARMISS_INPUTS },
  { id: 'live-promo-decor', name: t('skills.livePromoDecor'), instructions: 'You are a production live-commerce decor designer. Ship overlay packs (bg, stickers, price tags, badges) — not a big-promo KV hero.\n1) Brief: category, offer and overlay needs from liveBrief + refs.\n2) Pack: background, lower-thirds, price tags and corner badges that stack cleanly.\n3) Division: live decor kit — leave campaign KV heroes to promo-ecommerce.\n4) Copy: price/CTA text in quotes; high contrast on stream.\n5) Refs: pass refs in refs on every generate_image call.',
    category: 'ecommerce', cover: cover643('live-promo-decor'), examples: ex643('live-promo-decor', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], '497c6feeb559cc2c053a28fc9b45b3b11b595037'), featured: [],
    presets: [P('bg', '直播背景', 'Live background', 'Style: live-stream background decor, product-safe center, high contrast edges.'), P('price', '价签贴片', 'Price tag', 'Style: live price-tag overlay, bold numerals in quotes, stream-safe contrast.'), P('badge', '角标装饰', 'Corner badge', 'Style: live corner badge / sticker pack, stackable, readable on video.')],
    inputs: NEARMISS_INPUTS },
  { id: 'linkedin-banner', name: t('skills.linkedinBanner'), instructions: 'You are a production LinkedIn banner designer. Ship 1584×396 professional banners — not YouTube channel art.\n1) Brief: role, company and tone from profileBrief + refs.\n2) Layout: 1584×396; keep face/logo in safe area; B2B restraint.\n3) Division: LinkedIn personal/company banner only — leave 2560×1440 channel art to youtube-channel-banner.\n4) Copy: short professional lines in quotes.\n5) Refs: pass refs in refs on every generate_image call.',
    category: 'social', cover: cover643('linkedin-banner'), examples: ex643('linkedin-banner', [1]), featured: [],
    presets: [P('personal', '个人横幅', 'Personal', 'Style: LinkedIn personal banner 1584×396, face safe area, B2B tone.'), P('company', '公司横幅', 'Company', 'Style: LinkedIn company banner 1584×396, logo safe, professional restraint.')],
    inputs: NEARMISS_INPUTS },
  { id: 'logo-animation', name: t('skills.logoAnimation'), instructions: 'You are a production logo-animation designer. Animate a logo into a short brand intro or loop — not a static material study and not a geometric mark redesign.\n1) Intake: require logoImage; confirm intro vs loop.\n2) Motion: clean entrance or seamless loop; keep geometry identical to the mark.\n3) Division: motion logo — leave material stills to logo-material; leave abstract mark invention to logo-abstract.\n4) Finish: safe margins; no redesign of paths.\n5) Refs: pass logo shape id in refs on every generate_image / animate call.',
    category: 'branding', cover: cover643('logo-animation'), examples: ex643('logo-animation', [1, 2, 3, 4], '12d051fe4c9ce81405b4dd4e81094e21501ae9c4'), featured: [],
    presets: [P('intro', '入场动画', 'Intro', 'Style: logo intro animation, clean entrance, geometry locked to the mark.'), P('loop', '循环动画', 'Loop', 'Style: logo loop animation, seamless cycle, mark paths unchanged.')],
    inputs: NEARMISS_INPUTS },
  { id: 'restaurant-website', name: t('skills.restaurantWebsite'), instructions: 'You are a production restaurant website designer. Ship landing visuals for menu, atmosphere and reserve modules — not a generic SaaS product site.\n1) Brief: cuisine, tone and modules from restaurantBrief + refs.\n2) Modules: hero mood, menu board and reserve/CTA section sharing one look.\n3) Division: restaurant hospitality site — leave SaaS kits to web-product.\n4) Copy: dish/CTA lines in quotes.\n5) Refs: pass refs in refs on every generate_image call.',
    category: 'website', cover: cover643('restaurant-website'), examples: ex643('restaurant-website', [1, 2, 3, 4, 5, 6, 7], '9ca6d4ee7eb6488bb2c430affa86cfae75613485'), featured: [],
    presets: [P('mood', '氛围首屏', 'Mood hero', 'Style: restaurant site mood hero, hospitality photography, sparse headline in quotes.'), P('menu', '菜单模块', 'Menu module', 'Style: restaurant menu module visual, readable dishes, coherent with hero.')],
    inputs: NEARMISS_INPUTS },
  { id: 'clothing-swap', name: t('skills.clothingSwap'), instructions: 'You are a production AI clothing-swap artist. Keep the person; swap garments from a dual ref (person + clothing) — not a triple-ref person-swap.\n1) Intake: require an uploaded person ref + garment cue in Additional Details when needed.\n2) Lock: face, body and pose from the person; only wardrobe changes.\n3) Deliver: try-on stills with fabric truth and clean edges.\n4) Division: outfit swap on fixed person — leave scene+face+outfit triple swap to person-swap.\n5) Refs: pass both shape ids in refs on every generate_image call.',
    category: 'ecommerce', cover: cover643('clothing-swap'), examples: ex643('clothing-swap', [1, 2]), featured: [],
    presets: [P('casual', '日常换装', 'Casual', 'Style: AI clothing swap casual look, person locked, garment from ref, clean edges.'), P('formal', '正装换装', 'Formal', 'Style: AI clothing swap formal look, person locked, fabric honest.'), P('street', '街头换装', 'Street', 'Style: AI clothing swap streetwear look, person locked, outfit from ref.')],
    inputs: NEARMISS_INPUTS },
  { id: 'interior', name: t('skills.interiorArchitecturalVisualization'), instructions: 'Produce photoreal interior or architecture renders: eye-level wide shot, natural light, accurate materials, 16:9. Add a detail vignette at 4:3.',
    cover: cover('interior'), quickStartCover: quickStartCover('interior'), featured: feedCovers('interior'), video: video('interior'), examples: ex541('interior', [1, 2, 3, 4]),
    inputs: EFFECT_INPUTS },
])

export const skillAtom = atom<Skill | null>('skill', null)

const listFiles = (dir: string) => listUserFiles(`${ROOT}/${dir}`.replace(/\/$/, ''), true)
const read = (path: string) => readUserText(`${ROOT}/${path}`)
const write = (path: string, body: string) => writeUserText(`${ROOT}/${path}`, body)
const remove = (path: string) => deleteUserFile(`${ROOT}/${path}`)

// Description quoting mirrors #462 (PR #484, src/skills.ts) exactly so the two branches agree on rebase:
// whitespace (incl. newlines) collapses to one space, then the value is JSON-quoted (valid YAML), so colons and
// quotes survive the round trip and a newline can never end the frontmatter early.
export function toMarkdown(skill: Skill): string {
  const desc = skill.description?.replace(/\s+/g, ' ').trim()
  return `---\nname: ${skill.name}\n${desc ? `description: ${JSON.stringify(desc)}\n` : ''}---\n\n${skill.instructions}\n`
}

function unquote(v: string): string {
  if (v.startsWith('"')) { try { return String(JSON.parse(v)) } catch { /* fall through */ } }
  return v.replace(/^'(.*)'$/, '$1')
}

export function parseMarkdown(text: string): { name: string; description: string; instructions: string } {
  const m = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/.exec(text)
  const name = m ? /^name:\s*(.+)$/m.exec(m[1])?.[1].trim() ?? '' : ''
  const description = m ? unquote(/^description:\s*(.+)$/m.exec(m[1])?.[1].trim() ?? '') : ''
  return { name, description, instructions: (m ? m[2] : text).trim() }
}

async function readSkill(id: string, paths: string[]): Promise<Skill | null> {
  const md = await read(`${id}/SKILL.md`)
  if (md === null) return null
  const { name, description, instructions } = parseMarkdown(md)
  const files: Record<string, string> = {}
  for (const p of paths.filter((p) => p.startsWith('files/'))) files[p.slice(6)] = (await read(`${id}/${p}`)) ?? ''
  const images = paths.includes('images.json') ? JSON.parse((await read(`${id}/images.json`)) ?? '{}') as Record<string, string> : {}
  const learned = paths.includes('learned.json') ? JSON.parse((await read(`${id}/learned.json`)) ?? '[]') as string[] : undefined
  return { id, name: name || id, ...(description ? { description } : {}), instructions, files, images, custom: true, ...(learned ? { learned } : {}) }
}

export async function loadSkills(): Promise<Skill[]> {
  const byId = new Map<string, string[]>()
  for (const f of await listFiles('')) {
    const [id, ...rest] = f.split('/')
    byId.set(id, [...(byId.get(id) ?? []), rest.join('/')])
  }
  const custom = await Promise.all([...byId].filter(([, paths]) => paths.includes('SKILL.md')).map(([id, paths]) => readSkill(id, paths)))
  return [...custom.filter((s): s is Skill => !!s), ...BUILTIN_SKILLS]
}

export async function saveSkill(skill: Skill) {
  const paths = await listFiles(skill.id)
  const current = paths.includes('SKILL.md') ? await readSkill(skill.id, paths) : null
  if (current) await write(`${skill.id}/versions/${Date.now()}.json`, JSON.stringify(current))
  const files = skill.files ?? {}
  await write(`${skill.id}/SKILL.md`, toMarkdown(skill))
  await write(`${skill.id}/images.json`, JSON.stringify(skill.images ?? {}))
  if (skill.learned) await write(`${skill.id}/learned.json`, JSON.stringify(skill.learned))
  for (const [path, content] of Object.entries(files)) await write(`${skill.id}/files/${path}`, content)
  for (const p of paths.filter((p) => p.startsWith('files/') && !(p.slice(6) in files))) await remove(`${skill.id}/${p}`)
}

export async function deleteSkill(id: string) {
  for (const p of await listFiles(id)) await remove(`${id}/${p}`)
}

export async function listVersions(id: string): Promise<SkillVersion[]> {
  const names = (await listFiles(`${id}/versions`)).filter((f) => f.endsWith('.json')).sort().reverse()
  const out: SkillVersion[] = []
  for (const f of names) {
    const text = await read(`${id}/versions/${f}`)
    if (text) out.push({ time: Number(f.replace('.json', '')), skill: JSON.parse(text) as Skill })
  }
  return out
}

export const slug = (name: string) => name.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-').replace(/^-|-$/g, '') || uuid().slice(0, 8)

export async function uploadSkillImage(file: File, id: string): Promise<string> {
  return viewUrl(await uploadImage(file, `skill-${id}-${file.name}`))
}


/** One file of an imported skill: its path inside the folder / ZIP and its content. */
export interface SkillEntry { path: string; file: Blob }

/** #463 — size limit for one import (no earlier limit existed, so the product default of 20 MB applies). */
export const SKILL_IMPORT_MAX_BYTES = 20 * 1024 * 1024

/** #463 — the only three import errors the drop dialog shows. */
export type SkillImportErrorCode = 'noSkillMd' | 'unreadable' | 'tooLarge'
export class SkillImportError extends Error {
  constructor(readonly code: SkillImportErrorCode) {
    super(t(`skillsImport.error.${code}`))
    this.name = 'SkillImportError'
  }
}

/** Zip-slip / unsafe entry path: absolute, drive letter, backslash, `..`, or NUL. */
export function unsafeEntryPath(path: string): boolean {
  if (!path || path.includes('\\') || path.includes('\0')) return true
  if (path.startsWith('/') || /^[a-zA-Z]:/.test(path)) return true
  return path.split('/').some((part) => part === '..')
}

export interface ImportOptions {
  /** ZIP / drop dialog: enforce path safety + size limit. Folder import in the manage dialog keeps its old behaviour. */
  strict?: boolean
}

/** Shared by folder import and ZIP import (#463): finds the shallowest SKILL.md and imports its siblings.
 *  Everything is validated and read before the first write, so a failed import writes nothing. */
/** First id not taken by an existing skill folder: `id`, else `id-2`, `id-3`, … */
export async function freeSkillId(id: string): Promise<string> {
  const taken = new Set((await listFiles('')).map((f) => f.split('/')[0]))
  if (!taken.has(id)) return id
  let n = 2
  while (taken.has(`${id}-${n}`)) n++
  return `${id}-${n}`
}

export async function importEntries(all: SkillEntry[], fallbackName = '', opts: ImportOptions = {}): Promise<{ skill: Skill; skipped: string[] }> {
  if (opts.strict) {
    if (all.some((e) => unsafeEntryPath(e.path))) throw new SkillImportError('unreadable')
    if (all.reduce((n, e) => n + e.file.size, 0) > SKILL_IMPORT_MAX_BYTES) throw new SkillImportError('tooLarge')
  }
  const entries = all.filter((e) => e.path && !/(^|\/)(__MACOSX|\.DS_Store)(\/|$)/.test(e.path))
  const md = entries.filter((e) => /(^|\/)SKILL\.md$/i.test(e.path)).sort((a, b) => a.path.split('/').length - b.path.split('/').length)[0]
  if (!md) throw opts.strict ? new SkillImportError('noSkillMd') : new Error(t('skills.noSkillMdInFolder'))
  const root = md.path.replace(/SKILL\.md$/i, '')
  let parsed: { name: string; description: string; instructions: string }
  try { parsed = parseMarkdown(await md.file.text()) } catch { throw opts.strict ? new SkillImportError('unreadable') : new Error(t('skills.noSkillMdInFolder')) }
  const folder = root.replace(/\/$/, '').split('/').pop() || fallbackName
  let id = slug(folder || parsed.name)
  const extra: Record<string, string> = {}
  const imageEntries: [string, SkillEntry][] = []
  const skipped: string[] = []
  for (const e of entries) {
    if (e === md || !e.path.startsWith(root)) continue
    const path = e.path.slice(root.length)
    if (!path) continue
    if (TEXT_FILE.test(path)) extra[path] = await e.file.text()
    else if (IMAGE_FILE.test(path)) imageEntries.push([path, e])
    else skipped.push(path)
  }
  // #463: a duplicate name in the drop dialog becomes a new skill (`id-2`, `id-3`, …) with the same display name;
  // the existing skill is never touched. Folder import (non-strict) keeps main's direct overwrite.
  if (opts.strict) id = await freeSkillId(id)
  const images: Record<string, string> = {}
  for (const [path, e] of imageEntries) {
    const name = path.split('/').pop() ?? path
    images[path] = await uploadSkillImage(e.file instanceof File ? e.file : new File([e.file], name), id)
  }
  const skill: Skill = { id, name: parsed.name || folder, ...(parsed.description ? { description: parsed.description } : {}), instructions: parsed.instructions, files: extra, images, custom: true }
  await saveSkill(skill)
  return { skill, skipped }
}

export async function importFolder(list: FileList | File[]): Promise<{ skill: Skill; skipped: string[] }> {
  return importEntries(Array.from(list).map((f) => ({ path: f.webkitRelativePath || f.name, file: f })))
}

/** #463 — list the files of a skill ZIP (directories dropped). Pure: used by tests too. */
export function zipEntries(bytes: Uint8Array): SkillEntry[] {
  const out = unzipSync(bytes)
  return Object.entries(out).filter(([path]) => !path.endsWith('/')).map(([path, data]) => ({ path, file: new Blob([data as BlobPart]) }))
}

export const isZip = (f: File) => /\.zip$/i.test(f.name) || /zip/.test(f.type)

/** #463 import progress shown in the dialog: 上传中...N% while the file is read, then 解析中... while it is unpacked/saved. */
export type ImportProgress = { phase: 'upload'; pct: number } | { phase: 'extract' }

async function readWithProgress(file: File, onProgress?: (p: ImportProgress) => void): Promise<Uint8Array> {
  if (!onProgress || typeof file.stream !== 'function') return new Uint8Array(await file.arrayBuffer())
  const out = new Uint8Array(file.size)
  const reader = file.stream().getReader()
  let loaded = 0
  onProgress({ phase: 'upload', pct: 0 })
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    out.set(value, loaded)
    loaded += value.length
    onProgress({ phase: 'upload', pct: file.size ? Math.min(100, Math.round((loaded / file.size) * 100)) : 100 })
  }
  return out.subarray(0, loaded)
}

export async function importZip(file: File, onProgress?: (p: ImportProgress) => void): Promise<{ skill: Skill; skipped: string[] }> {
  if (file.size > SKILL_IMPORT_MAX_BYTES) throw new SkillImportError('tooLarge')
  if (!isZip(file)) throw new SkillImportError('unreadable')
  let entries: SkillEntry[]
  const bytes = await readWithProgress(file, onProgress).catch(() => { throw new SkillImportError('unreadable') })
  onProgress?.({ phase: 'extract' })
  try { entries = zipEntries(bytes) } catch { throw new SkillImportError('unreadable') }
  return importEntries(entries, file.name.replace(/\.zip$/i, ''), { strict: true })
}

/** #463 — after a successful import: open the NEW skill's page (a duplicate lands on its -2/-3 id).
 *  `skipped` is the one-off toast text, only when unsupported files were actually skipped: the second half of main's
 *  `skillsDialog.importedSkipped` copy (「不支持的文件已跳过：{0}」), no new copy. */
export function importLanding(skill: Pick<Skill, 'id'>, skipped: string[] = []): { id: string; skipped: string } {
  return { id: skill.id, skipped: skipped.length ? skippedNotice(skipped) : '' }
}

export function skippedNotice(skipped: string[]): string {
  const full = t('skillsDialog.importedSkipped', skipped.join(t('common.listSep')))
  const cut = full.search(/[。.]\s*/)
  return cut < 0 ? full : full.slice(cut + 1).trim()
}

/** #463 — what "Edit in chat" tells the agent, so it reads and saves the skill by id (names can repeat: x, x-2).
 *  Used by #484's `skillEditTurn` (src/skillEdit.ts). */
export function skillEditToolHint(skill: Pick<Skill, 'id' | 'name'>): string {
  return `Read it with the skill tool (action="read", id="${skill.id}"). When saving, use action="save" with id="${skill.id}" `
    + `(not the name "${skill.name}": several skills can share it), keeping everything not mentioned; pass description to change its description.`
}

/** The agent `skill` tool (#463). Skills are addressed by `id` when given: "Edit in chat" passes the id and a save with
 *  an id updates exactly that skill. A save by name updates the one custom skill with that name; when the name is
 *  ambiguous (duplicates from import) or new, a new skill is created and no existing one is touched. */
export async function skillTool(args: Record<string, unknown>): Promise<unknown> {
  const skills = await loadSkills()
  if (args.action === 'list') return { skills: skills.map((s) => ({ id: s.id, name: s.name, description: s.description ?? '', custom: !!s.custom })) }
  const id = args.id ? String(args.id) : ''
  if (args.action === 'save') {
    if (!args.name && !id) throw new Error('save needs a name or id')
    let existing: Skill | undefined
    if (id) {
      existing = skills.find((s) => s.custom && s.id === id)
      if (!existing) throw new Error(`no custom skill with id ${JSON.stringify(id)}`)
    } else {
      const named = skills.filter((s) => s.custom && s.name === args.name)
      existing = named.length === 1 ? named[0] : undefined
    }
    // instructions/description are optional on an update (keep the stored value); a new skill needs instructions.
    if (args.instructions == null && !existing) throw new Error('save needs instructions for a new skill')
    const name = args.name ? String(args.name) : existing!.name
    const instructions = args.instructions != null ? String(args.instructions) : existing!.instructions
    const description = args.description != null ? String(args.description).replace(/\s+/g, ' ').trim() : existing?.description
    const skill: Skill = { ...existing, id: existing?.id ?? await freeSkillId(slug(name)), name, instructions, custom: true }
    if (description) skill.description = description; else delete skill.description
    await saveSkill(skill)
    return { saved: name, id: skill.id, description: description ?? '' }
  }
  if (args.action !== 'read') throw new Error('action must be list, read or save')
  const skill = id ? skills.find((s) => s.id === id) : skills.find((s) => s.name === args.name)
  if (!skill) throw new Error(`unknown skill ${JSON.stringify(id || args.name)} — available: ${skills.map((s) => `${s.name} (${s.id})`).join(', ')}`)
  if (args.path) {
    const content = skill.files?.[String(args.path)]
    if (content == null) throw new Error(`skill ${skill.name} has no file ${args.path}; files: ${Object.keys(skill.files ?? {}).join(', ') || '(none)'}`)
    return { id: skill.id, name: skill.name, path: args.path, content }
  }
  return { id: skill.id, name: skill.name, description: skill.description ?? '', instructions: skill.instructions, files: Object.keys(skill.files ?? {}), images: Object.values(skill.images ?? {}) }
}

/** #460/#461 — Explore wall + conversational creator (form kept as fallback). */
const FAV_KEY = 'comfyart.skillFavourites'
/** #581 — local per-browser usage counts (id → n). Increment only on a real run start; never seed. */
const USAGE_KEY = 'comfyart.skillUsage'

/** #462: `edit` set = Edit in Chat for an existing personal skill (same Composer chip path). */
/** #491: `chip` = i18n key of the chip label; unset falls back to composer.skillCreator (zh 技能创建器), same key as both create entries. */
export const skillCreatorAtom = atom<{ on: boolean; chip?: string }>('skillCreator', { on: false })

/** #491 product: both create entries share one chip copy — zh 技能创建器 / en Skill Creator. */
export const HOME_CREATOR_CHIP_KEY = 'composer.skillCreator'
/** #491 entry B (Skills page 「创建」) uses the same key as home. */
export const CREATE_ENTRY_CHIP_KEY = HOME_CREATOR_CHIP_KEY

export function loadFavourites(): string[] {
  try {
    const raw = localStorage.getItem(FAV_KEY)
    const list = raw ? JSON.parse(raw) as unknown : []
    return Array.isArray(list) ? list.filter((x): x is string => typeof x === 'string') : []
  } catch {
    return []
  }
}

export function toggleFavourite(id: string): string[] {
  const set = new Set(loadFavourites())
  if (set.has(id)) set.delete(id)
  else set.add(id)
  const next = [...set]
  localStorage.setItem(FAV_KEY, JSON.stringify(next))
  return next
}

/** #581 — map of skill id → local run count. Empty on a fresh install. */
export function loadSkillUsage(): Record<string, number> {
  try {
    const raw = localStorage.getItem(USAGE_KEY)
    const obj = raw ? JSON.parse(raw) as unknown : {}
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return {}
    const out: Record<string, number> = {}
    for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
      if (typeof k === 'string' && typeof v === 'number' && Number.isFinite(v) && v > 0) out[k] = Math.floor(v)
    }
    return out
  } catch {
    return {}
  }
}

export function getSkillUsage(id: string): number {
  return loadSkillUsage()[id] ?? 0
}

/** #581 — bump when the user actually starts a run (dialog 「开始制作」 or direct newProject({ skill })). */
export function recordSkillUse(id: string): number {
  const map = loadSkillUsage()
  const next = (map[id] ?? 0) + 1
  map[id] = next
  localStorage.setItem(USAGE_KEY, JSON.stringify(map))
  return next
}

/** #581 — stable deep link (`?skill=<id>`) matching handoff.ts. */
/** #601 — examples filmstrip index label matching gold `01`…`10`. */
export function filmstripIndexLabel(oneBased: number): string {
  return String(oneBased).padStart(2, '0')
}

export function skillShareUrl(id: string, href = typeof location !== 'undefined' ? location.href : ''): string {
  const url = new URL(href || 'http://localhost/')
  for (const k of ['ask', 'mode', 'ref', 'tool', 'createSkill', 'editSkill', 'preset']) url.searchParams.delete(k)
  url.searchParams.set('skill', id)
  return url.toString()
}

/** Chip ids for Explore filters: 「为你推荐」 plus the categories (#494: read from each skill's `category`). */
export type SkillChipId = 'forYou' | SkillCategory
/** Display order of category chips; a category no skill uses is dropped by `skillChips` (#591: `website` appears once `mobile-ui`/`web-product` land). */
export const SKILL_CATEGORY_ORDER: SkillCategory[] = ['ecommerce', 'branding', 'social', 'website', 'ads']

/** #494 — chips shown on Explore: 「为你推荐」 + every category that has at least one of `skills`. */
export function skillChips(skills: Skill[]): SkillChipId[] {
  const used = new Set(skills.map((s) => s.category).filter(Boolean))
  return ['forYou', ...SKILL_CATEGORY_ORDER.filter((c) => used.has(c))]
}

export function matchesSkillChip(skill: Skill, chip: SkillChipId): boolean {
  return chip === 'forYou' || skill.category === chip
}

export function skillDescription(skill: Skill): string {
  if (skill.description?.trim()) return skill.description.trim()
  const key = `skills.desc.${skill.id}`
  const localized = t(key)
  if (localized !== key) return localized
  const line = skill.instructions.split('\n').find((l) => l.trim()) ?? ''
  return line.slice(0, 72) + (line.length > 72 ? '…' : '')
}

/** #494 product rule (23:20) — the ONE place that decides a card's image: `cover`, else the skill's own `images[0]`
 *  (old personal skills, no migration), else `null` → light grey background + Lucide icon (no image, no gradient). */
export function skillCover(skill: Skill): { src: string; own: 'bundled' | 'userdata' } | null {
  if (skill.cover) return { src: skill.cover, own: 'bundled' }
  const first = Object.values(skill.images ?? {})[0]
  return first ? { src: first, own: 'userdata' } : null
}

/** #529 — list/detail cover video URL when the skill data carries `video` (no video → no badge, no fake). */
/** #580 cut 2 — video skills whose quick-start tile is the video's first frame (design v2 / product confirmed). */
export const QUICK_START_VIDEO_FIRST: ReadonlySet<string> = new Set(['motion'])
/** #580 cut 2 — home quick-start row image: optional `quickStartCover` override; default = video skills' first frame,
 *  else the Skills-module `cover`. Fit is dual (#602): cover full-bleed or contain + letterbox via skillQuickStartCoverFit. */
export function skillQuickStartCover(skill: Skill): { src: string; own: 'bundled' | 'userdata' | 'video' } | null {
  if (skill.quickStartCover) return { src: skill.quickStartCover, own: 'bundled' }
  if (QUICK_START_VIDEO_FIRST.has(skill.id) && skill.video) return { src: skill.video, own: 'video' }
  return skillCover(skill)
}

/** #602 — resolve quick-start cover fit. Defaults to `cover` unless the skill marks `contain` (letterbox plate). */
export function skillQuickStartCoverFit(skill: Skill): 'cover' | 'contain' {
  return skill.quickStartCoverFit === 'contain' ? 'contain' : 'cover'
}

export function skillVideo(skill: Skill): string | null {
  return skill.video || null
}

/** #575 — Explore / home cover hover contract: muted loop on enter/focus; leave/blur → pause + seek 0 (still/first frame under). */
export function skillCoverVideoHover(video: HTMLVideoElement | null | undefined, phase: 'enter' | 'leave'): void {
  if (!video) return
  if (phase === 'enter') {
    void video.play().catch(() => {})
    return
  }
  video.pause()
  try { video.currentTime = 0 } catch { /* seek may throw before metadata */ }
}

/** #575 — preset template video when design pins one; else null (still path via presetImage). */
export function presetVideo(_skill: Skill, preset: SkillPreset): string | null {
  return preset.video || null
}

/** #494/#489/#581 — author line: built-ins show BRAND.name (logo); personal / imported skills say 个人. Card footer appends real usage separately. */
export function skillAuthor(skill: Skill): { kind: 'builtin' | 'personal'; label: string } {
  return skill.custom ? { kind: 'personal', label: t('home.skillsAuthorPersonal') } : { kind: 'builtin', label: BRAND.name }
}

/** #494-2 — a skill has its own input dialog only when its data carries `inputs[]`. Old imported / personal skills
 *  have none and keep main's behaviour (open a project with the skill chip) — no migration. */
export const hasSkillDialog = (skill: Skill) => !!skill.inputs?.length

export type SkillValues = Record<string, string>

/** #494-2 — initial dialog values, straight from each input's `default` (selects fall back to their first option). */
export function skillDefaults(skill: Skill): SkillValues {
  return Object.fromEntries((skill.inputs ?? []).map((f) => [f.key, f.default ?? (f.type === 'select' ? f.options?.[0]?.value ?? '' : '')]))
}

/** #494-2 — keys of required inputs that are still empty (the dialog disables 生成 until this is empty). */
export function missingInputs(skill: Skill, values: SkillValues): string[] {
  return (skill.inputs ?? []).filter((f) => f.required && !values[f.key]?.trim()).map((f) => f.key)
}

/** #494-2 — the chosen preset (unknown id → first preset; no presets → undefined). */
export function skillPreset(skill: Skill, presetId?: string | null): SkillPreset | undefined {
  return skill.presets?.find((p) => p.id === presetId) ?? skill.presets?.[0]
}

/** #494-2 product rule: the selected preset's `prompt` is appended AFTER the skill's instructions. */
export function withPreset(skill: Skill, presetId?: string | null): Skill {
  const p = presetId ? skill.presets?.find((x) => x.id === presetId) : undefined
  return p?.prompt ? { ...skill, instructions: `${skill.instructions.trimEnd()}\n\n${p.prompt}` } : skill
}

/** #541/#581 — design-spec meta under the description. Real data only: template count from presets[];
 *  usage from local `loadSkillUsage` (never seeded). No presets and no usage → null. */
export function skillMeta(skill: Skill): { templates: number; usage: number } | null {
  const templates = skill.presets?.length ?? 0
  const usage = getSkillUsage(skill.id)
  if (!templates && !usage) return null
  return { templates, usage }
}

/** #581 — modal meta copy: 「已使用 N 次 · N 个模板」 when usage>0; else template-count-only (or usage-only). */
export function skillMetaLabel(meta: { templates: number; usage: number }): string {
  if (meta.usage > 0 && meta.templates > 0) return t('skillRun.usageAndTemplates', meta.usage, meta.templates)
  if (meta.usage > 0) return t('skillRun.usageCount', meta.usage)
  return t('skillRun.templateCount', meta.templates)
}

/** #494-2 — the preset's own image, else the skill's list cover (one decision point, like `skillCover`). */
export function presetImage(skill: Skill, preset: SkillPreset): string | null {
  return preset.image ?? skillCover(skill)?.src ?? null
}

/** #580 — home 「Skill 案例」 tiles, data-driven from the skill list (no demo rows).
 *  Example-type skills (`examples`) contribute their 「效果示例」 images; template-type skills their presets' own images.
 *  `featured` (preset id) moves that template to the front of the skill's queue.
 *  Round-robin: one image per skill per round, in list order; no repeated image, and never two adjacent tiles
 *  from the same skill (a tile that would be is dropped, which only happens once a single skill is left). */
export interface SkillFeaturedCase { skill: Skill; preset: SkillPreset | null; image: string; key: string }
export function skillFeaturedCases(skills: Skill[]): SkillFeaturedCase[] {
  const queues = skills.map((skill) => {
    const q: SkillFeaturedCase[] = []
    if (skill.featured?.length) {
      skill.featured.forEach((image, i) => { if (image) q.push({ skill, preset: null, image, key: `${skill.id}:feed${i}` }) })
    } else if (skill.examples?.length) {
      skill.examples.forEach((image, i) => {
        if (image && !isSkillMediaVideo(image)) q.push({ skill, preset: null, image, key: `${skill.id}:ex${i}` })
      })
    } else {
      const presets = [...(skill.presets ?? [])]
      const first = presets.findIndex((p) => p.id === skill.featuredPreset)
      if (first > 0) presets.unshift(...presets.splice(first, 1))
      for (const preset of presets) if (preset.image) q.push({ skill, preset, image: preset.image, key: `${skill.id}:${preset.id}` })
    }
    return q
  }).filter((q) => q.length)
  const out: SkillFeaturedCase[] = []
  const seen = new Set<string>()
  for (let round = 0; queues.some((q) => q.length > round); round++) {
    for (const q of queues) {
      const c = q[round]
      if (!c || seen.has(c.image)) continue
      if (out.length && out[out.length - 1]!.skill.id === c.skill.id) continue
      seen.add(c.image)
      out.push(c)
    }
  }
  return out
}

/** #494-2 — turn the dialog into the handoff: the text the user "sends" (label: value per filled text/select field,
 *  in data order), image fields as refs, and the skill + preset ids. Read by src/home/handoff.ts. */
export function skillRunParams(skill: Skill, values: SkillValues, presetId?: string | null): Record<string, string | string[]> {
  const lines: string[] = []
  const refs: string[] = []
  for (const f of skill.inputs ?? []) {
    const v = values[f.key]?.trim()
    if (!v) continue
    if (f.type === 'image') { refs.push(v); continue }
    const shown = f.type === 'select' ? loc(f.options?.find((o) => o.value === v)?.label ?? { zh: v }) : v
    lines.push(`${loc(f.label)}: ${shown}`)
  }
  const preset = presetId ? skill.presets?.find((p) => p.id === presetId) : undefined
  return { skill: skill.id, mode: 'agent', ask: lines.join('\n') || skill.name, ...(preset ? { preset: preset.id } : {}), ...(refs.length ? { ref: refs } : {}) }
}
