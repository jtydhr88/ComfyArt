import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import type { AgentMode } from '../agent'
import { botEnabledAtom, loadProviders, loadSettings, providerLabel } from '../bot'
import { thumbUrl, uploadImage, viewUrl } from '../comfy'
import { t } from '../i18n'
import { errorText } from '../jobs'
import { newProject, openView, startProject } from '../projects'
import { HOME_SKILL_ROW, FEATURED_DEFAULTS, FEED_SPECIAL_ASPECT, HOME_TABS, HOME_TAB_PLACEHOLDER, HOME_ASSET_CHIPS, featuredAspect, packFeaturedColumns, readFeaturedMetrics, withSpecialCards, type FeedSpecialId, type HomeTab, type HomeAssetChip } from './featuredLayout'
import { Assets } from './Assets'
import { CHIP_LABEL } from './Skills'
import { toolCover } from './toolCovers'
import { showMemoryToast } from '../memory'
import { BUILTIN_SKILLS, hasSkillDialog,
  recordSkillUse, importLanding, loadSkills, matchesSkillChip, skillChips, skillCoverVideoHover, skillFeaturedCases, skillQuickStartCover, skillQuickStartCoverFit, skillVideo, FEED_SPECIAL_COLLAGE, type Skill, type SkillChipId } from '../skills'
import { SkillChip, chipBackspace } from '../ui/SkillChip'
import { SkillImportDialog } from '../ui/SkillImportDialog'
import { SkillRunDialog } from '../ui/SkillRunDialog'
import { openSkillEditor } from '../ui/SkillsDialog'
import { Icons } from '../ui/icons'
import { NoKeyNotice } from '../ui/NoKeyNotice'
import { keyMissing, keySettingsOpenAtom, keyStatusAtom, refreshKeyStatus } from '../wavespeedKey'
import { isEnter } from '../ui/keys'
import { Popover } from '../ui/Popover'
import { AgentExtras, AgentItems, shortLabel, useCurrentAgent } from '../ui/AgentPicker'
import { AgentLogo } from '../ui/agentLogos'
import { ComposerSlot, useSlot } from '../ui/ComposerSlot'
import { MODE_OPTIONS, modeOf } from '../ui/modeOptions'
import { DirectPills } from '../ui/DirectPills'
import { ModelPrefs } from '../ui/ModelPrefs'
import { loadModels } from '../models'

const ROTATE_MS = 4000
const EXAMPLES = [t('home.example1'), t('home.example2'), t('home.example3'), t('home.example4')]
/** #610 soft P1 — category pills L→R 1:1 gold order; click → inline starter card (not prompt-fill). */
type QuickId = 'ecommerce' | 'social' | 'brand' | 'creative' | 'website'
type StarterSuggest = { skillId: string; labelKey: string }
const QUICK_TESTID: Record<QuickId, string> = {
  ecommerce: 'e_commerce',
  social: 'social_media',
  brand: 'branding',
  creative: 'ads_creative',
  website: 'website',
}
/** Phase1 skill suggestions (3 per pill). Soft thirds reuse family when map has only 2. */
const QUICK: { id: QuickId; icon: keyof typeof Icons; label: string; suggests: StarterSuggest[] }[] = [
  { id: 'ecommerce', icon: 'assets', label: t('home.quickEcommerce'), suggests: [
    { skillId: 'product', labelKey: 'home.starter.product' },
    { skillId: 'packaging', labelKey: 'home.starter.packaging' },
    { skillId: 'multi-angle', labelKey: 'home.starter.multiAngle' },
  ] },
  { id: 'social', icon: 'grid', label: t('home.quickSocial'), suggests: [
    { skillId: 'social', labelKey: 'home.starter.social' },
    { skillId: 'thumbnail', labelKey: 'home.starter.thumbnail' },
    { skillId: 'social', labelKey: 'home.starter.socialAlt' },
  ] },
  { id: 'brand', icon: 'palette', label: t('home.quickBrand'), suggests: [
    { skillId: 'brand', labelKey: 'home.starter.brand' },
    { skillId: 'logo-material', labelKey: 'home.starter.logoMaterial' },
    { skillId: 'brand', labelKey: 'home.starter.brandAlt' },
  ] },
  { id: 'creative', icon: 'effects', label: t('home.quickCreative'), suggests: [
    { skillId: 'poster', labelKey: 'home.starter.poster' },
    { skillId: 'banner', labelKey: 'home.starter.banner' },
    { skillId: 'meta-ads', labelKey: 'home.starter.metaAds' },
  ] },
  { id: 'website', icon: 'page', label: t('home.quickWebsite'), suggests: [
    { skillId: 'mobile-ui', labelKey: 'home.starter.mobileUi' },
    { skillId: 'web-product', labelKey: 'home.starter.webProduct' },
    { skillId: 'web-product', labelKey: 'home.starter.webProductAlt' },
  ] },
]

/** #537 / #496 / #540: home 「实用工具」— covers = design wash on review-assets (commit-pinned). */
type ToolCard = { id: string; icon?: keyof typeof Icons; label: string; accept: string; cover: string }
const HOME_TOOL_CARDS: ToolCard[] = [
  { id: 'cutout', icon: 'cutout', label: t('common.removeBackground'), accept: 'image/*', cover: toolCover('main-5', 'cutout') },
  { id: 'extend', icon: 'extend', label: t('common.extendVideo'), accept: 'video/*', cover: toolCover('main-5', 'extend') },
  { id: 'upscale', icon: 'upscale', label: t('common.upscale'), accept: 'image/*', cover: toolCover('main-5', 'upscale') },
  { id: 'inpaint', icon: 'effects', label: t('home.toolPreciseEdit'), accept: 'image/*', cover: toolCover('main-5', 'inpaint') },
  { id: 'mockup', icon: 'box', label: t('mockup.title'), accept: 'image/*', cover: toolCover('main-5', 'mockup') },
]
/** #540: reference design「更多」10 (Loomic order) + unique 4. The menu renders icon rows only (Jingmeng ruling);
 *  `cover` is backup data, used only if a tool is pinned (置顶) into the main 16:9 row. */
/** #540: the ONE place mapping 更多 tool id → 18px filled icon (design spec #540 comment 6545206549).
 *  Paths inlined from Remix Icon v4.9.1 (`*-fill`) — Apache License 2.0,
 *  Copyright (c) Remix Design (github.com/Remix-Design/RemixIcon). Not reference design SVGs; no dependency added. */
const rx = (d: string) => <svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d={d} /></svg>
const MORE_TOOL_ICON = {
  quick: rx('M15.2238 15.5079L13.0111 20.1581C12.8687 20.4573 12.5107 20.5844 12.2115 20.442C12.1448 20.4103 12.0845 20.3665 12.0337 20.3129L8.49229 16.5741C8.39749 16.474 8.27113 16.4096 8.13445 16.3918L3.02816 15.7243C2.69958 15.6814 2.46804 15.3802 2.51099 15.0516C2.52056 14.9784 2.54359 14.9075 2.5789 14.8426L5.04031 10.3192C5.1062 10.1981 5.12839 10.058 5.10314 9.92253L4.16 4.85991C4.09931 4.53414 4.3142 4.22086 4.63997 4.16017C4.7126 4.14664 4.78711 4.14664 4.85974 4.16017L9.92237 5.10331C10.0579 5.12855 10.198 5.10637 10.319 5.04048L14.8424 2.57907C15.1335 2.42068 15.4979 2.52825 15.6562 2.81931C15.6916 2.88421 15.7146 2.95507 15.7241 3.02833L16.3916 8.13462C16.4095 8.2713 16.4739 8.39766 16.5739 8.49245L20.3127 12.0338C20.5533 12.2617 20.5636 12.6415 20.3357 12.8821C20.2849 12.9357 20.2246 12.9795 20.1579 13.0112L15.5078 15.224C15.3833 15.2832 15.283 15.3835 15.2238 15.5079ZM16.0206 17.435L17.4348 16.0208L21.6775 20.2634L20.2633 21.6776L16.0206 17.435Z'), // ri-magic-fill
  erase: rx('M13.9999 18.9966H20.9999V20.9966H11.9999L8.00229 20.9991L1.51457 14.5113C1.12405 14.1208 1.12405 13.4877 1.51457 13.0971L12.1212 2.49053C12.5117 2.1 13.1449 2.1 13.5354 2.49053L21.3136 10.2687C21.7041 10.6592 21.7041 11.2924 21.3136 11.6829L13.9999 18.9966ZM15.6567 14.5113L19.1922 10.9758L12.8283 4.61185L9.29275 8.14738L15.6567 14.5113Z'), // ri-eraser-fill
  crop: rx('M19 17H22V19H19V22H17V19H6C5.44772 19 5 18.5523 5 18V7H2V5H5V2H7V5H18C18.5523 5 19 5.44772 19 6V17Z'), // ri-crop-fill
  expand: rx('M21 3H13.5L16.5429 6.04289L13.2929 9.29289L14.7071 10.7071L17.9571 7.45711L21 10.5V3ZM3 21H10.5L7.45711 17.9571L10.7071 14.7071L9.29289 13.2929L6.04289 16.5429L3 13.5V21Z'), // ri-expand-diagonal-fill
  adjust: rx('M6.17071 18C6.58254 16.8348 7.69378 16 9 16C10.3062 16 11.4175 16.8348 11.8293 18H22V20H11.8293C11.4175 21.1652 10.3062 22 9 22C7.69378 22 6.58254 21.1652 6.17071 20H2V18H6.17071ZM12.1707 11C12.5825 9.83481 13.6938 9 15 9C16.3062 9 17.4175 9.83481 17.8293 11H22V13H17.8293C17.4175 14.1652 16.3062 15 15 15C13.6938 15 12.5825 14.1652 12.1707 13H2V11H12.1707ZM6.17071 4C6.58254 2.83481 7.69378 2 9 2C10.3062 2 11.4175 2.83481 11.8293 4H22V6H11.8293C11.4175 7.16519 10.3062 8 9 8C7.69378 8 6.58254 7.16519 6.17071 6H2V4H6.17071Z'), // ri-equalizer-fill
  text: rx('M17 8H7V10H11V17H13V10H17V8ZM4 3H20C20.5523 3 21 3.44772 21 4V20C21 20.5523 20.5523 21 20 21H4C3.44772 21 3 20.5523 3 20V4C3 3.44772 3.44772 3 4 3Z'), // ri-t-box-fill
  angles: rx('M9 3H15L17 5H21C21.5523 5 22 5.44772 22 6V20C22 20.5523 21.5523 21 21 21H3C2.44772 21 2 20.5523 2 20V6C2 5.44772 2.44772 5 3 5H7L9 3ZM14.6839 18.3677L13.7892 16.5785C13.2509 16.8482 12.6432 17 12 17C9.79086 17 8 15.2091 8 13H10L7.83875 8.67749C6.70523 9.76898 6 11.3021 6 13C6 16.3137 8.68629 19 12 19C12.9647 19 13.8763 18.7723 14.6839 18.3677ZM9.31613 7.63226L10.2108 9.42151C10.7491 9.15179 11.3568 9 12 9C14.2091 9 16 10.7909 16 13H14L16.1613 17.3225C17.2948 16.231 18 14.6979 18 13C18 9.68629 15.3137 7 12 7C11.0353 7 10.1237 7.22769 9.31613 7.63226Z'), // ri-camera-switch-fill
  vectorize: rx('M4.92898 21.4819L10.775 15.6359C11.4423 15.8141 12.1837 15.6414 12.7071 15.118C13.4882 14.3369 13.4882 13.0706 12.7071 12.2896C11.9261 11.5085 10.6598 11.5085 9.87872 12.2896C9.35526 12.813 9.18263 13.5544 9.36081 14.2217L3.51476 20.0677L2.4541 19.0071C5.28253 15.7072 6.34319 12.0539 7.7574 5.9256L14.1214 5.21849L19.7783 10.8754L19.0711 17.2393C12.9429 18.6535 9.28947 19.7142 5.98964 22.5426L4.92898 21.4819ZM16.5962 2.03651L22.9428 8.38312C23.1381 8.57838 23.1381 8.89496 22.9428 9.09022C22.8679 9.16513 22.7712 9.21431 22.6665 9.23067L21.1924 9.46113L15.5356 3.80428L15.7477 2.31935C15.7868 2.04599 16.04 1.85604 16.3134 1.89509C16.4205 1.91039 16.5197 1.96001 16.5962 2.03651Z'), // ri-pen-nib-fill
  move: rx('M18 11V8L22 12L18 16V13H13V18H16L12 22L8 18H11V13H6V16L2 12L6 8V11H11V6H8L12 2L16 6H13V11H18Z'), // ri-drag-move-2-fill
  transform: rx('M14 4H16C18.7614 4 21 6.23858 21 9V13H19V9C19 7.34315 17.6569 6 16 6H14V9L9 5L14 1V4ZM15 11V21C15 21.5523 14.5523 22 14 22H4C3.44772 22 3 21.5523 3 21V11C3 10.4477 3.44772 10 4 10H14C14.5523 10 15 10.4477 15 11Z'), // ri-anticlockwise-2-fill
  to3d: rx('M20.5021 5.92225 12 1 3.49793 5.92225 12 10.8445 20.5021 5.92225ZM2.5 7.6555V17.5L11 22.4211V12.5765L2.5 7.6555ZM13 22.4211 21.5 17.5V7.6555L13 12.5765V22.4211Z'), // ri-box-3-fill
  lipsync: rx('M4.92893 19.0711C3.11929 17.2614 2 14.7614 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12C22 17.5228 17.5228 22 12 22H2L4.92893 19.0711ZM11 6V18H13V6H11ZM7 9V15H9V9H7ZM15 9V15H17V9H15Z'), // ri-chat-voice-fill
  motion: rx('M9.82986 8.78986L7.99998 9.45588V13H5.99998V8.05H6.015L11.2834 6.13247C11.5274 6.03855 11.7922 5.99162 12.0648 6.0008C13.1762 6.02813 14.1522 6.75668 14.4917 7.82036C14.678 8.40431 14.848 8.79836 15.0015 9.0025C15.9138 10.2155 17.3653 11 19 11V13C16.8253 13 14.8823 12.0083 13.5984 10.4526L13.017 13.7497L15 15.67V23H13V17.0142L10.9507 15.0271L10.003 19.3253L3.10938 18.1098L3.45667 16.1401L8.38071 17.0084L9.82986 8.78986ZM13.5 5.5C12.3954 5.5 11.5 4.60457 11.5 3.5C11.5 2.39543 12.3954 1.5 13.5 1.5C14.6046 1.5 15.5 2.39543 15.5 3.5C15.5 4.60457 14.6046 5.5 13.5 5.5Z'), // ri-run-fill
  audio: rx('M20 3V17C20 19.2091 18.2091 21 16 21C13.7909 21 12 19.2091 12 17C12 14.7909 13.7909 13 16 13C16.7286 13 17.4117 13.1948 18 13.5351V6H9V17C9 19.2091 7.20914 21 5 21C2.79086 21 1 19.2091 1 17C1 14.7909 2.79086 13 5 13C5.72857 13 6.41165 13.1948 7 13.5351V3H20Z'), // ri-music-2-fill
} satisfies Record<string, ReactNode>
/** Remix ri-arrow-down-s-fill (Apache-2.0) — 14px filled chevron on the 更多工具 trigger. */
const MORE_TOOLS_CARET = rx('M12 16L6 10H18L12 16Z')
const MORE_HOME_TOOLS: ToolCard[] = [
  { id: 'quick', label: t('common.quickEdit'), accept: 'image/*', cover: toolCover('more-10', 'quick') },
  { id: 'erase', label: t('common.eraser'), accept: 'image/*', cover: toolCover('more-10', 'erase') },
  { id: 'crop', label: t('imageToolbar.crop'), accept: 'image/*', cover: toolCover('more-10', 'crop') },
  { id: 'expand', label: t('common.expand'), accept: 'image/*', cover: toolCover('more-10', 'expand') },
  { id: 'adjust', label: t('common.adjust'), accept: 'image/*', cover: toolCover('more-10', 'adjust') },
  { id: 'text', label: t('common.editText'), accept: 'image/*', cover: toolCover('more-10', 'text') },
  { id: 'angles', label: t('common.multiAngle'), accept: 'image/*', cover: toolCover('more-10', 'angles') },
  { id: 'vectorize', label: t('imageToolbar.vectorize'), accept: 'image/*', cover: toolCover('more-10', 'vectorize') },
  { id: 'move', label: t('common.moveObject'), accept: 'image/*', cover: toolCover('more-10', 'move') },
  { id: 'transform', label: t('imageToolbar.flipAndRotate'), accept: 'image/*', cover: toolCover('more-10', 'transform') },
  { id: 'to3d', label: t('imageToolbar.imageTo3d'), accept: 'image/*', cover: toolCover('unique-4', 'to3d') },
  { id: 'lipsync', label: t('genPanel.lipSync'), accept: 'image/*', cover: toolCover('unique-4', 'lipsync') },
  { id: 'motion', label: t('genPanel.motionControl'), accept: 'image/*', cover: toolCover('unique-4', 'motion') },
  { id: 'audio', label: t('audio.generateAudio'), accept: 'audio/*', cover: toolCover('unique-4', 'audio') },
]


/** #575 — home quick-start card: still (or video first-frame) + muted hover loop when `skill.video` is set.
 *  Dual-fit / object-fit left to #602/#594 — this only adds playback overlay. */
function HomeSkillCard({ skill, onTry }: { skill: Skill; onTry: () => void }) {
  const cover = skillQuickStartCover(skill)
  const src = cover && (cover.own === 'userdata' ? thumbUrl(cover.src, 512) : cover.src)
  const videoSrc = skillVideo(skill)
  const videoRef = useRef<HTMLVideoElement>(null)
  const play = () => skillCoverVideoHover(videoRef.current, 'enter')
  const stop = () => skillCoverVideoHover(videoRef.current, 'leave')
  return (
    <button type="button" className="ca-skillcard" data-testid="home-skill-card" data-skill={skill.id}
      data-has-video={videoSrc ? '1' : undefined}
      onClick={onTry}
      onMouseEnter={videoSrc ? play : undefined}
      onMouseLeave={videoSrc ? stop : undefined}
      onFocus={videoSrc ? play : undefined}
      onBlur={videoSrc ? stop : undefined}
    >
      <span className="ca-skillcard__cover" data-testid="home-skill-cover" data-fit={skillQuickStartCoverFit(skill)}>
        {src && cover?.own === 'video'
          ? <video src={`${src}#t=0.001`} muted playsInline preload="metadata" data-testid="home-skill-cover-frame" />
          : src ? <img src={src} alt="" draggable={false} /> : <span className="ca-icon">{Icons.skill}</span>}
        {videoSrc && (
          <video
            ref={videoRef}
            className="ca-skillcard__video"
            src={videoSrc}
            muted
            loop
            playsInline
            preload="metadata"
            data-testid="home-skill-card-video"
            aria-hidden="true"
          />
        )}
      </span>
      <span className="ca-skillcard__name"><span className="ca-skillcard__label">{skill.name}</span></span>
    </button>
  )
}

export function Home() {
  const [text, setText] = useState('')
  const [refs, setRefs] = useState<string[]>([])
  const [mode, setMode] = useState<AgentMode>('agent')
  const [agent, setAgent] = useState<boolean | null>(null)
  const [modeMenu, setModeMenu] = useState(false)
  const [example, setExample] = useState(0)
  const [skills, setSkills] = useState<Skill[]>([])
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [drop, setDrop] = useState(false)
  const [composing, setComposing] = useState(false)
  const [sending, setSending] = useState(false)
  // #491: home + menu (+ → 技能 → 创建技能); #542: 创建技能 jumps straight to the canvas (same handoff as the Skills page 创建)
  const [plus, setPlus] = useState<null | 'plus' | 'skills'>(null)
  const [more, setMore] = useState(false)  // #491 design: 创建技能 dropdown anchored under the panel's square-plus; panel stays open
  const [picked, setPicked] = useState<Skill | null>(null)  // #491: skill chip from the + → 技能 panel; only send leaves home
  const [importing, setImporting] = useState(false)
  // #494-3 / #533: home 精选 + 用 Skill 快速开始 open the same SkillRunDialog as the Skills page
  const [running, setRunning] = useState<{ id: string; preset: string | null } | null>(null)
  const [moreTools, setMoreTools] = useState(false)  // #537: 「更多工具」
  const [featuredWidth, setFeaturedWidth] = useState(1200)  // #537: masonry columns
  const featuredRoot = useRef<HTMLElement>(null)
  const [featuredMetrics, setFeaturedMetrics] = useState(FEATURED_DEFAULTS)
  // #580 cut 2: feed tabs + category chips (from skills.ts categories) + natural image ratios + floating input
  const [tab, setTab] = useState<HomeTab>('explore')
  const [chip, setChip] = useState<SkillChipId>('forYou')
  const [assetChip, setAssetChip] = useState<HomeAssetChip>('brandKit')
  const [ratios, setRatios] = useState<Record<string, number>>({})
  const [floating, setFloating] = useState(false)
  // #602 — floating composer collapses to a send-forward pill until focus/click expands it
  const [boxExpanded, setBoxExpanded] = useState(true)
  // #610: category pill → inline starter card (Close restores pills; composer stays empty)
  const [starter, setStarter] = useState<QuickId | null>(null)
  const boxSlot = useRef<HTMLDivElement>(null)
  const toolFile = useRef<HTMLInputElement>(null)
  const pendingTool = useRef<string>('')
  const current = useCurrentAgent()  // #278: same agent the canvas mode button shows
  const hasContent = !!text.trim() || refs.length > 0  // #276: an image with no text counts as content
  const { showSend, setVoice } = useSlot(hasContent, composing)
  // #604 hotfix / product lock: compact float pill trailing = ↑ send (not voice), matching expanded send affordance
  const compact = floating && !boxExpanded
  const slotSend = showSend || compact
  const input = useRef<HTMLTextAreaElement>(null)
  const file = useRef<HTMLInputElement>(null)

  useEffect(() => {
    input.current?.focus()
    void refreshKeyStatus()
    void loadModels().catch((e) => setError(errorText(e)))  // #287: same model list / saved picks as the canvas
    // #315: load settings with providers so AgentExtras Model matches canvas (shared bot-model-*)
    void Promise.all([loadProviders(), loadSettings()]).then(() => {
      const on = !!botEnabledAtom.get()
      setAgent(on)
      if (!on) setMode('image')
    }, () => { setAgent(false); setMode('image') })
    void loadSkills().then(setSkills)
    const timer = window.setInterval(() => setExample((i) => (i + 1) % EXAMPLES.length), ROTATE_MS)
    return () => clearInterval(timer)
  }, [])

  // #278: keep the draft until the new project is created; on failure it stays and an error shows
  const send = async () => {
    if (!hasContent || uploading || sending) return
    // #305: guide once; keep the ask in the box when Key is missing
    let key = keyStatusAtom.get()
    if (!key) key = await refreshKeyStatus()
    if (keyMissing(key)) { keySettingsOpenAtom.set(true); return }
    setSending(true)
    setError('')
    try {
      if (picked) await startProject({ skill: picked.id, ask: text.trim(), mode, ref: refs })
      else await startProject({ ask: text.trim(), mode, ref: refs })  // #287: model / settings live in the shared saved store
      setText('')
      setRefs([])
      setPicked(null)
    } catch (e) {
      setError(errorText(e))
    } finally {
      setSending(false)
    }
  }
  const upload = async (files: FileList | null) => {
    setUploading(true)
    try {
      for (const f of Array.from(files ?? []).filter((x) => x.type.startsWith('image/'))) {
        const src = viewUrl(await uploadImage(f, f.name))
        setRefs((r) => (r.includes(src) ? r : [...r, src]))
      }
    } catch (e) {
      setError(errorText(e))
    } finally {
      setUploading(false)
    }
  }
  /** #537: pick file → upload → new project with tool=; cancel leaves home (no project). Never auto-runs. */
  const pickTool = (tool: ToolCard) => {
    pendingTool.current = tool.id
    const el = toolFile.current
    if (!el) return
    el.value = ''
    el.accept = tool.accept
    el.click()
  }
  const launchTool = async (f: File | undefined) => {
    const tool = pendingTool.current
    pendingTool.current = ''
    if (!f || !tool) return
    setUploading(true)
    setMoreTools(false)
    setError('')
    try {
      newProject({ ref: viewUrl(await uploadImage(f, f.name)), tool })
    } catch (e) {
      setError(errorText(e))
      setUploading(false)
    }
  }
  const modeInfo = modeOf(mode)
  /** #494-3 — Skills-page rule: dialog when inputs[] exist; else main's direct start. Featured passes a preset id. */
  const trySkill = (s: Skill, preset: string | null = null) => {
    if (hasSkillDialog(s)) { setRunning({ id: s.id, preset }); return }
    recordSkillUse(s.id)
    newProject({ skill: s.id })
  }
  const chips = useMemo(() => skillChips(skills), [skills])
  const shown = useMemo(() => skills.filter((s) => matchesSkillChip(s, chip)), [skills, chip])
  const featured = useMemo(() => skillFeaturedCases(shown), [shown])
  // #537: masonry waterfall via Loomic column math; cards from our skill presets only (no third-party feed data)
  // #580 cut 2: card height = the image's natural ratio once loaded (estimate before); two special cards embedded.
  const featuredItems = useMemo(
    () => featured.map(({ skill: s, preset: p, image, key }, order) => ({
        kind: 'case' as const,
        id: key,
        order,
        group: s.id as string | undefined,
        skill: s,
        preset: p,
        image,
        aspect: ratios[key] ?? featuredAspect(key),
      })),
    [featured, ratios],
  )
  const onCaseLoad = (key: string, img: HTMLImageElement) => {
    if (!img.naturalWidth || !img.naturalHeight) return
    const r = img.naturalWidth / img.naturalHeight
    setRatios((m) => (Math.abs((m[key] ?? 0) - r) < 0.001 ? m : { ...m, [key]: r }))
  }
  const comingSoon = () => showMemoryToast(t('home.comingSoon'), 'info')
  // #580 cut 2: the composer floats at the bottom once its slot scrolls out of view (slot keeps the layout height)
  useEffect(() => {
    const el = boxSlot.current
    if (!el || typeof IntersectionObserver === 'undefined') return
    const io = new IntersectionObserver(([e]) => {
      const next = !!e && !e.isIntersecting && e.boundingClientRect.top < 0
      setFloating(next)
      // #602: enter float → compact unless the input already holds focus; leave float → always expanded
      if (next) setBoxExpanded(document.activeElement === input.current)
      else setBoxExpanded(true)
    })
    io.observe(el)
    return () => io.disconnect()
  }, [])
  const featuredColumns = useMemo(
    () => withSpecialCards(
      packFeaturedColumns(featuredItems, featuredWidth, featuredMetrics.gap, featuredMetrics.colWidth),
      (id: FeedSpecialId) => ({ kind: 'special' as const, id: `special:${id}`, special: id, aspect: FEED_SPECIAL_ASPECT }),
    ),
    [featuredItems, featuredWidth, featuredMetrics],
  )
  useEffect(() => {
    const el = featuredRoot.current
    if (!el) return
    const update = () => {
      const w = el.getBoundingClientRect().width
      if (w > 0) setFeaturedWidth(w)
      const m = readFeaturedMetrics(el)
      setFeaturedMetrics((p) => (p.gap === m.gap && p.colWidth === m.colWidth ? p : m))
    }
    update()
    const ro = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(update)
    ro?.observe(el)
    return () => ro?.disconnect()
  }, [featuredItems.length, tab])
  const runSkill = running ? skills.find((s) => s.id === running.id) : undefined

  return (
    <div className="ca-landing">
      <h1 className="ca-landing__title">{t('home.whatToDesign')}</h1>
      {agent && <NoKeyNotice className="ca-landing__notice" />}
      <div ref={boxSlot} className="ca-landing__boxslot" data-testid="home-box-slot" style={floating ? { minHeight: boxSlot.current?.offsetHeight } : undefined}>
      <div
        data-floating={floating || undefined}
        data-compact={(floating && !boxExpanded) || undefined}
        data-testid="home-box"
        className="ca-landing__box"
        data-drop={drop || undefined}
        onDragOver={(e) => { if (e.dataTransfer.types.includes('Files')) { e.preventDefault(); setDrop(true) } }}
        onDragLeave={() => setDrop(false)}
        onDrop={(e) => { e.preventDefault(); setDrop(false); void upload(e.dataTransfer.files) }}
        onClick={() => { if (floating && !boxExpanded) { setBoxExpanded(true); input.current?.focus() } }}
        onFocusCapture={() => { if (floating) setBoxExpanded(true) }}
        onBlurCapture={(e) => {
          if (!floating) return
          const next = e.relatedTarget as Node | null
          if (next && e.currentTarget.contains(next)) return
          setBoxExpanded(false)
        }}
        onKeyDown={(e) => {
          if (e.key === 'Escape' && floating && boxExpanded) {
            e.stopPropagation()
            setBoxExpanded(false)
            input.current?.blur()
          }
        }}
      >
        {picked && (
          <div className="ca-landing__refs">
            <SkillChip name={picked.name} testId="home-skill-chip" />
          </div>
        )}
        {refs.length > 0 && (
          <div className="ca-landing__refs">
            {refs.map((src) => (
              <span key={src} className="ca-landing__ref">
                <img src={thumbUrl(src, 128)} alt="" />
                <button type="button" title={t('common.remove')} onClick={() => setRefs(refs.filter((x) => x !== src))}>{Icons.close}</button>
              </span>
            ))}
          </div>
        )}
        <textarea
          ref={input}
          className="ca-landing__input"
          value={text}
          placeholder={EXAMPLES[example]}
          onChange={(e) => setText(e.target.value)}
          onCompositionStart={() => setComposing(true)}
          onCompositionEnd={() => setComposing(false)}
          onKeyDown={(e) => {
            if (picked && chipBackspace(e)) { e.preventDefault(); setPicked(null); return }
            if (e.key === 'Tab' && !text) { e.preventDefault(); setText(EXAMPLES[example]) }
            if (isEnter(e) && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send() }
          }}
        />
        <div className="ca-landing__foot">
          <Popover
            open={plus !== null}
            onOpenChange={(o) => { setPlus(o ? 'plus' : null); if (!o) setMore(false) }}
            side="bottom"
            align="start"
            within=".ca-landing__box"
            viewportCap
            contentKey={plus ?? ''}
            trigger={({ open, toggle }) => (
              <button type="button" className="ca-bar__btn ca-bar__btn--icon ca-landing__add" data-testid="home-plus" title={t('home.plusMenu')} data-open={open || undefined} onClick={toggle}><span className="ca-icon">{Icons.plus}</span></button>
            )}
          >
            {plus === 'plus' && (
              <div className="ca-menu" data-testid="home-plus-menu">
                <button type="button" className="ca-menu__item" onClick={() => { setPlus(null); file.current?.click() }}>
                  <span className="ca-icon">{Icons.upload}</span><span className="ca-menu__grow">{t('home.addImage')}</span>
                </button>
                <button type="button" className="ca-menu__item" data-testid="home-plus-skills" onClick={() => setPlus('skills')}>
                  <span className="ca-icon">{Icons.skill}</span><span className="ca-menu__grow">{t('home.skillsMenu')}</span><span className="ca-icon">{Icons.next}</span>
                </button>
              </div>
            )}
            {plus === 'skills' && (
              <div className="ca-menu ca-skills" data-testid="home-skills-menu">
                <div className="ca-menu__head">
                  <span className="ca-menu__grow">{t('home.skillsMenu')}</span>
                  <Popover
                    open={more}
                    onOpenChange={setMore}
                    side="bottom"
                    align="end"
                    within=".ca-skills"
                    contentKey="skillsMore"
                    trigger={({ open, toggle }) => (
                      <button type="button" className="ca-bar__btn ca-bar__btn--icon" data-testid="home-skills-more" title={t('home.skillsMenuMore')} data-open={open || undefined} onClick={toggle}>
                        <span className="ca-icon">{Icons.squarePlus}</span>
                      </button>
                    )}
                  >
                    <div className="ca-menu" data-testid="home-skills-more-menu">
                      {/* #542: jumps on click (no send) — the canvas lands exactly like the Skills page 创建 */}
                      <button type="button" className="ca-menu__item" data-testid="home-create-skill" onClick={() => { setMore(false); setPlus(null); newProject({ createSkill: '1' }) }}>
                        <span className="ca-icon">{Icons.circlePlus}</span><span className="ca-menu__grow">{t('home.createSkill')}</span>
                      </button>
                      <button type="button" className="ca-menu__item" disabled>
                        <span className="ca-icon">{Icons.messageSquare}</span><span className="ca-menu__grow">{t('home.createSkillFromChat')}</span>
                      </button>
                      <button type="button" className="ca-menu__item" data-testid="home-import-skill" onClick={() => { setMore(false); setPlus(null); setImporting(true) }}>
                        <span className="ca-icon">{Icons.uploadArrow}</span><span className="ca-menu__grow">{t('home.importSkill')}</span>
                      </button>
                    </div>
                  </Popover>
                </div>
                {skills.map((s) => (
                  <button key={s.id} type="button" className="ca-menu__item" title={s.name} data-testid="home-skill-row" onClick={() => { setPlus(null); setPicked(s); input.current?.focus() }}>
                    <span className="ca-menu__grow ca-skills__name">{s.name}</span>
                    {s.custom && <span className="ca-menu__key">{t('composer.personal')}</span>}
                  </button>
                ))}
              </div>
            )}
          </Popover>
          <Popover
            open={modeMenu}
            onOpenChange={(o) => { setModeMenu(o); if (o) void Promise.all([loadProviders(), loadSettings()]).catch((e) => setError(errorText(e))) }}
            side="bottom"
            align="start"
            within=".ca-landing__box"
            viewportCap
            trigger={({ open, toggle }) => (
              <button type="button" className="ca-landing__mode" title={mode === 'agent' && current ? providerLabel(current) : modeInfo[1]} data-agent={mode === 'agent' && current ? current.id : undefined} data-open={open || undefined} onClick={toggle}>
                {/* Ashley: same as canvas — agent pill = shortLabel (ComfyArt); image/video = mode name */}
                {mode === 'agent' && current ? <><AgentLogo id={current.id} /><span className="ca-landing__modetext">{shortLabel(current)}</span></> : <><span className="ca-icon">{Icons[modeInfo[2]]}</span><span className="ca-landing__modetext">{modeInfo[1]}</span></>}<span className="ca-icon">{Icons.chevron}</span>
              </button>
            )}
          >
            {/* #306: Home open menu = canvas AgentItems + Image/Video (no lone 「Agent」 mode row) */}
            <div className="ca-menu ca-agentpick">
              {agent && (
                <>
                  <AgentItems onError={setError} current={mode === 'agent'} close={() => setModeMenu(false)} onChosen={() => setMode('agent')} />
                  <div className="ca-menu__sep" />
                </>
              )}
              {MODE_OPTIONS.filter(([m]) => m !== 'agent').map(([m, label, icon]) => (
                <button key={m} type="button" className="ca-menu__item" onClick={() => { setMode(m); setModeMenu(false) }}>
                  <span className="ca-icon">{Icons[icon]}</span><span className="ca-menu__grow">{label}</span>
                  {m === mode && <span className="ca-icon">{Icons.check}</span>}
                </button>
              ))}
              {mode === 'agent' && agent && <><div className="ca-menu__sep" /><AgentExtras onError={setError} close={() => setModeMenu(false)} /></>}
            </div>
          </Popover>
          <div className="ca-landing__spacer" />
          {/* #287: same right group as the canvas (#272): model → settings → voice/send; agent mode shows only prefs (no Ref: home has no canvas) */}
          {mode !== 'agent' && <DirectPills video={mode === 'video'} within=".ca-landing__box" spacer={false} onError={setError} side="bottom" />}
          {mode === 'agent' && agent && <ModelPrefs onError={setError} within=".ca-landing__box" side="bottom" />}
          <ComposerSlot showSend={slotSend} setVoice={setVoice} canSend={(hasContent || compact) && !uploading && !sending} onSend={() => void send()} onError={setError}
            onText={(v) => setText((cur) => `${cur}${cur ? ' ' : ''}${v}`)} />
        </div>
        <input ref={file} type="file" accept="image/*" multiple hidden onChange={(e) => { void upload(e.target.files); e.target.value = '' }} />
      </div>
      </div>
      {importing && (
        <SkillImportDialog
          onClose={() => setImporting(false)}
          onImported={(skill, skipped) => {
            // #491: same landing as the Skills page import (#487)
            setImporting(false)
            const landing = importLanding(skill, skipped)
            openSkillEditor(landing.id)
            if (landing.skipped) showMemoryToast(landing.skipped, 'info')
            void loadSkills().then(setSkills)
          }}
        />
      )}
      {error && <div className="ca-landing__error" onClick={() => setError('')}>{error}</div>}
      <div className="ca-landing__quick" data-testid="home-quick-row">
        {starter ? (
          <div className="ca-landing__starter" data-testid="ca-home-starter">
            <div className="ca-landing__starter-bar">
              <div className="ca-landing__starter-icons" role="group" aria-label={t('home.starterCategories')}>
                {QUICK.map((q) => (
                  <button
                    key={q.id}
                    type="button"
                    className="ca-landing__starter-icon"
                    data-testid={`home-v3-starter-icon-${QUICK_TESTID[q.id]}`}
                    aria-label={q.label}
                    aria-pressed={starter === q.id}
                    data-on={starter === q.id || undefined}
                    onClick={() => setStarter(q.id)}
                  >
                    <span className="ca-icon" aria-hidden>{Icons[q.icon]}</span>
                  </button>
                ))}
              </div>
              <button
                type="button"
                className="ca-landing__starter-back"
                data-testid="home-v3-starter-back"
                aria-label={t('common.close')}
                onClick={() => setStarter(null)}
              >
                <span className="ca-icon" aria-hidden>{Icons.close}</span>
              </button>
            </div>
            <div className="ca-landing__starter-suggests" data-testid="home-starter-suggests">
              {(QUICK.find((q) => q.id === starter) ?? QUICK[0]).suggests.map((s, i) => {
                const skill = skills.find((x) => x.id === s.skillId) ?? BUILTIN_SKILLS.find((x) => x.id === s.skillId)
                const name = skill?.name ?? s.skillId
                return (
                  <button
                    key={`${s.skillId}-${s.labelKey}-${i}`}
                    type="button"
                    className="ca-landing__starter-suggest"
                    data-testid={`home-starter-suggest-${s.skillId}`}
                    data-skill={s.skillId}
                    disabled={!skill}
                    onClick={() => { if (skill) trySkill(skill) }}
                  >
                    <span className="ca-icon" aria-hidden>{Icons.sparkles}</span>
                    <span className="ca-landing__starter-suggest-text">{t(s.labelKey, name)}</span>
                  </button>
                )
              })}
            </div>
          </div>
        ) : (
          <>
            <span className="ca-landing__hint">{t('home.letAgentHelp')}</span>
            {QUICK.map((q) => (
              <button
                key={q.id}
                type="button"
                className="ca-landing__chip"
                data-testid={`home-v3-hero-chip-${QUICK_TESTID[q.id]}`}
                data-quick={q.id}
                onClick={() => setStarter(q.id)}
              >
                <span className="ca-icon" aria-hidden>{Icons[q.icon]}</span>{q.label}
              </button>
            ))}
          </>
        )}
      </div>

      <section className="ca-landing__section ca-landing__tools" data-testid="home-tools">
        <div className="ca-landing__head">
          <h2>{t('home.tools')}</h2>
          <Popover
            open={moreTools}
            onOpenChange={setMoreTools}
            side="bottom"
            align="end"
            trigger={({ open, toggle }) => (
              <button type="button" className="ca-landing__link ca-landing__moretools" data-testid="home-more-tools" data-open={open || undefined} onClick={toggle}>
                <span className="ca-landing__moretools-label">{t('home.moreTools')}</span><span className="ca-icon" aria-hidden>{MORE_TOOLS_CARET}</span>
              </button>
            )}
          >
            <div className="ca-menu ca-menu--tools" data-testid="home-more-tools-menu">
              {MORE_HOME_TOOLS.map((tool) => (
                <button key={tool.id} type="button" className="ca-menu__item" data-testid={`home-more-tool-${tool.id}`} disabled={uploading} onClick={() => pickTool(tool)}>
                  <span className="ca-icon" aria-hidden>{MORE_TOOL_ICON[tool.id as keyof typeof MORE_TOOL_ICON]}</span><span className="ca-menu__grow ca-menu__label">{tool.label}</span>
                </button>
              ))}
            </div>
          </Popover>
        </div>
        <div className="ca-toolgrid" data-testid="home-tool-grid">
          {HOME_TOOL_CARDS.map((tool) => (
            <button
              key={tool.id}
              type="button"
              className="ca-toolcard"
              data-testid={`home-tool-card-${tool.id}`}
              data-tool={tool.id}
              disabled={uploading}
              onClick={() => pickTool(tool)}
            >
              <span className="ca-toolcard__cover" data-tool={tool.id}>
                <img src={tool.cover} alt="" draggable={false} />
              </span>
              <span className="ca-toolcard__name">{tool.label}</span>
            </button>
          ))}
        </div>
        <input ref={toolFile} type="file" hidden onChange={(e) => { void launchTool(e.target.files?.[0]); e.target.value = '' }} />
      </section>

      <nav className="ca-hometabs" data-testid="home-tabs" role="tablist">
        {HOME_TABS.map((id) => (
          <button key={id} type="button" role="tab" className="ca-hometabs__tab" data-testid={`home-tab-${id}`} aria-selected={tab === id} data-active={tab === id || undefined} onClick={() => setTab(id)}>
            {t(`home.tab.${id}`)}
          </button>
        ))}
      </nav>
      {tab === 'explore' && chips.length > 1 && (
        <div className="ca-skills__chips ca-homechips" data-testid="home-chips">
          {chips.map((c) => (
            <button key={c} type="button" className="ca-skills__chip" data-testid={`home-chip-${c}`} data-on={chip === c || undefined} aria-pressed={chip === c} onClick={() => setChip(c)}>
              {t(CHIP_LABEL[c])}
            </button>
          ))}
        </div>
      )}
      {tab === 'assets' && (
        <div className="ca-skills__chips ca-homechips" data-testid="home-asset-chips">
          {HOME_ASSET_CHIPS.map((c) => (
            <button key={c} type="button" className="ca-skills__chip" data-testid={`home-asset-chip-${c}`} data-on={assetChip === c || undefined} aria-pressed={assetChip === c} onClick={() => setAssetChip(c)}>
              {t(`home.assetChip.${c}`)}
            </button>
          ))}
        </div>
      )}
      {tab === 'assets' && <div className="ca-hometab-assets" data-testid="home-tab-panel-assets"><Assets /></div>}
      {HOME_TAB_PLACEHOLDER.has(tab) && (
        <div className="ca-hometab-soon" data-testid={`home-tab-panel-${tab}`}>
          {tab === 'inspiration' ? <span className="ca-featured__special-collage ca-hometab-soon__collage" aria-hidden /> : <span className="ca-icon" aria-hidden>{Icons.imageLine}</span>}
          <span className="ca-hometab-soon__title">{t(`home.tabPanel.${tab}.title`)}</span>
          <span className="ca-hometab-soon__text">{t(`home.tabPanel.${tab}.text`)}</span>
          <button type="button" className="ca-hometab-soon__btn" data-variant={tab === 'pinterest' ? 'outline' : undefined} data-testid={`home-tab-action-${tab}`} onClick={comingSoon}>{t(`home.tabPanel.${tab}.action`)}</button>
        </div>
      )}

      {tab === 'explore' && <>
      <section className="ca-landing__section" data-testid="home-start-skill">
        <div className="ca-landing__head">
          <h2><button type="button" className="ca-landing__headlink" data-testid="home-start-skill-head" onClick={() => openView('skills')}>{t('home.startFromSkill')}<span className="ca-landing__chev" aria-hidden>›</span></button></h2>
          <button type="button" className="ca-landing__link" onClick={() => openView('skills')}>{t('home.viewAll')}</button>
        </div>
        {/* skills-cut1: one row of HOME_SKILL_ROW cover cards (cover + title ›), real skills only; click keeps trySkill */}
        <div className="ca-skillgrid" data-testid="home-skill-grid">
          {shown.slice(0, HOME_SKILL_ROW).map((s) => (
            <HomeSkillCard key={s.id} skill={s} onTry={() => trySkill(s)} />
          ))}
        </div>
      </section>

      {featuredItems.length > 0 && (
        <section ref={featuredRoot} className="ca-landing__section ca-landing__featured" data-testid="home-featured">
          <div className="ca-landing__head">
            <h2>{t('home.featured')}</h2>
          </div>
          <div className="ca-featured ca-featured--waterfall" data-testid="home-featured-grid">
            {featuredColumns.map((col, ci) => (
              <div key={`col-${ci}`} className="ca-featured__col" data-testid="home-featured-col">
                {col.map((item) => item.kind === 'special' ? (
                  <div key={item.id} className="ca-featured__card ca-featured__special" data-testid="home-feed-special" data-special={item.special}>
                    <span className="ca-featured__special-body" style={{ aspectRatio: item.aspect }}>
                      {/* #588 collage from review-assets (commit-pinned) */}
                      <span className="ca-featured__special-collage" data-testid="home-feed-special-collage" aria-hidden>{FEED_SPECIAL_COLLAGE[item.special] && <img src={FEED_SPECIAL_COLLAGE[item.special]} alt="" loading="lazy" draggable={false} />}</span>
                      <span className="ca-featured__special-title">{t(`home.special.${item.special}`)}</span>
                      <span className="ca-featured__special-text">{t(`home.special.${item.special}Text`)}</span>
                      {item.special === 'connector' && (
                        <input className="ca-featured__special-input" data-testid="home-feed-special-input" placeholder={t('home.special.connectorPlaceholder')} onKeyDown={(e) => { if (e.key === 'Enter') comingSoon() }} />
                      )}
                      <button type="button" className="ca-featured__special-btn" data-testid={`home-feed-special-${item.special}`} onClick={comingSoon}>{t(`home.special.${item.special}Action`)}</button>
                    </span>
                  </div>
                ) : (({ id, order, skill: s, preset: p, image, aspect }) => (
                  <button
                    key={id}
                    type="button"
                    className="ca-featured__card"
                    data-testid="home-featured-card"
                    data-skill={s.id}
                    data-preset={p?.id}
                    data-order={order}
                    onClick={() => trySkill(s, p?.id ?? null)}
                  >
                    <span className="ca-featured__cover" style={{ aspectRatio: aspect }}>
                      <img src={image} alt={s.name} loading="lazy" onLoad={(e) => onCaseLoad(id, e.currentTarget)} />
                      <span className="ca-featured__badge" data-testid="home-featured-kind" aria-hidden><span className="ca-icon">{/\.(mp4|webm|mov)(\?|$)/i.test(image) ? Icons.videoLine : Icons.imageLine}</span></span>
                      <span className="ca-featured__go">{t('skillRun.start')}</span>
                    </span>
                    <span className="ca-featured__name"><span className="ca-featured__title">{s.name}</span><span className="ca-featured__tag">{t('home.skillCase')}</span></span>
                  </button>
                ))(item))}
              </div>
            ))}
          </div>
        </section>
      )}
      </>}

      {runSkill && (
        <SkillRunDialog skill={runSkill} presetId={running?.preset} onClose={() => setRunning(null)} />
      )}
    </div>
  )
}
