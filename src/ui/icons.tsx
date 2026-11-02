import { useId, createElement, type ReactElement, type ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  ALargeSmall,
  Bell,
  Bookmark,
  Box,
  Check,
  ChevronDown,
  ChevronRight,
  CirclePlus,
  Code,
  Crop,
  Cuboid,
  Download,
  Ellipsis,
  Eraser,
  Expand,
  ExternalLink,
  Eye,
  EyeOff,
  FileCode,
  FilePenLine,
  FileSearch,
  FileText,
  Files,
  FlipHorizontal2,
  FlipVertical2,
  Folder,
  Frame,
  Globe,
  Grid2x2,
  Hand,
  Heart,
  HelpCircle,
  History,
  Home,
  Image,
  ImagePlus,
  Info,
  Keyboard,
  Lasso,
  Layers,
  Link,
  List,
  ListChecks,
  Lock,
  Map,
  Maximize2,
  MessageCircle,
  MessageSquare,
  Mic,
  Minus,
  Moon,
  MousePointer2,
  Music,
  PanelLeft,
  PanelRight,
  Paperclip,
  Pause,
  Pencil,
  PenLine,
  Pin,
  Play,
  Plus,
  Redo2,
  RefreshCw,
  Replace,
  RotateCcw,
  Scissors,
  ScrollText,
  Search,
  Send,
  Share2,
  Settings,
  SlidersHorizontal,
  Sparkles,
  Square,
  SquareCode,
  SquarePlus,
  Star,
  Sun,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  Type,
  Undo2,
  Unlock,
  Upload,
  User,
  Video,
  Volume2,
  VolumeX,
  WandSparkles,
  Workflow,
  X,
} from 'lucide-react'

/**
 * #608 — Lucide (`lucide-react`, ISC) for sidebar nav + utility tools + canvas toolbar.
 * strokeWidth ~1.75 ≈ thin line icons; keep .ca-icon size tokens from the design system.
 * Do NOT copy third-party proprietary SVG assets. No competitor brand strings in src/.
 */
export const LUCIDE_STROKE = 1.75

function L(Icon: LucideIcon, strokeWidth: number = LUCIDE_STROKE, extra?: Record<string, unknown>): ReactElement {
  return createElement(Icon, { strokeWidth, 'aria-hidden': true, size: 24, ...extra })
}

function Svg({ children, fill, strokeWidth = 1.6 }: { children: ReactNode; fill?: boolean; strokeWidth?: number }) {
  return fill ? (
    <svg viewBox="0 0 24 24" fill="currentColor">{children}</svg>
  ) : (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  )
}

/** Loomi mark, mono: currentColor on a 24 canvas; mask id from useId so several copies never collide. */
export function LoomiMono() {
  const id = `loomi-${useId().replace(/:/g, '')}`
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" data-loomi="mono" aria-hidden="true">
      <mask id={id}>
        <g transform="translate(1.2 1.2) scale(.216)">
          <path fill="#fff" d="M50 4 C56 4, 64 8, 68 16 C74 10, 84 10, 90 18 C96 26, 96 36, 90 42 C98 48, 100 58, 96 66 C92 74, 84 78, 76 76 C72 84, 62 92, 50 92 C38 92, 28 84, 24 76 C16 78, 8 74, 4 66 C0 58, 2 48, 10 42 C4 36, 4 26, 10 18 C16 10, 26 10, 32 16 C36 8, 44 4, 50 4 Z" />
          <path fill="#000" d="M31 46 L35.5 34 L40 46 L51 50.5 L40 55 L35.5 67 L31 55 L20 50.5 Z" />
          <path d="M56 42 Q65 54, 74 42" fill="none" stroke="#000" strokeWidth="5" strokeLinecap="round" />
        </g>
      </mask>
      <rect width="24" height="24" mask={`url(#${id})`} />
    </svg>
  )
}

export const Icons = {
  // #437/#442: in-house generation mark (not a Lucide stock icon)
  sparkleImage: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M13 4H7a3 3 0 0 0-3 3v10a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3v-6" />
      <path d="m4.5 16.5 4-4a1.5 1.5 0 0 1 2.1 0l4.9 4.9" />
      <path d="m13.5 15.4 1.4-1.4a1.5 1.5 0 0 1 2.1 0l2.9 2.9" />
      <path data-solid="star" fill="currentColor" stroke="none" d="M18 1.6c.35 2 1.35 3.05 3.4 3.4-2.05.35-3.05 1.4-3.4 3.4-.35-2-1.35-3.05-3.4-3.4 2.05-.35 3.05-1.4 3.4-3.4Z" />
    </svg>
  ),
  // #437: in-house 56×56 search-results art
  searchFolder: (
    <svg viewBox="0 0 56 56" width="56" height="56" aria-hidden="true">
      <path d="M8 16a4 4 0 0 1 4-4h10l4 4h18a4 4 0 0 1 4 4v24H8Z" fill="#d4d4d8" />
      <rect x="15" y="14" width="24" height="26" rx="2" fill="#fafafa" stroke="rgba(0,0,0,.08)" strokeWidth=".5" transform="rotate(-6 27 27)" />
      <rect x="18" y="16" width="24" height="26" rx="2" fill="#fff" stroke="rgba(0,0,0,.08)" strokeWidth=".5" />
      <path d="M22 22h14M22 26h14M22 30h9" stroke="#d4d4d8" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M6 26a3 3 0 0 1 3-3h38a3 3 0 0 1 3 3l-2 18a3 3 0 0 1-3 3H11a3 3 0 0 1-3-3Z" fill="#fff" stroke="rgba(0,0,0,.1)" strokeWidth=".5" />
    </svg>
  ),

  sun: L(Sun),
  moon: L(Moon),
  image: L(Image),
  video: L(Video),
  genVideo: L(Video),
  doodle: L(Pencil),
  trim: L(Scissors),
  extend: L(Maximize2),
  comment: L(MessageCircle),
  lasso: L(Lasso),
  list: L(List),
  qr: <Svg><path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h2v2h-2zM18 18h2v2h-2zM14 18h2M18 14h2" /></Svg>,
  /** corner-brackets / mockup frame — Lucide Box */
  box: L(Box),
  close: L(X),
  trash: L(Trash2),
  bookmark: L(Bookmark, 2),
  bookmarkFilled: L(Bookmark, 2, { fill: 'currentColor' }),
  share: L(Share2, 2),
  user: L(User, 2),
  workflow: L(Workflow, 2),
  heart: L(Heart, 2),
  eye: L(Eye),
  eyeOff: L(EyeOff),
  lock: L(Lock),
  unlock: L(Unlock),
  palette: L(WandSparkles),
  files: L(Files),
  map: L(Map),
  plus: L(Plus),
  squarePlus: L(SquarePlus),
  home: L(Home),
  settings: L(Settings),
  /** #608 sidebar WaveSpeed history → external */
  exit: L(ExternalLink),
  folder: L(Folder),
  page: L(SquarePlus),
  panel: L(PanelLeft),
  wave: <Svg><path d="M4 10v4M8 7v10M12 4v16M16 7v10M20 10v4" /></Svg>,
  mic: L(Mic),
  music: L(Music),
  cube: L(Cuboid),
  sound: L(Volume2),
  soundOff: L(VolumeX),
  panelRight: L(PanelRight),
  panelLeft: L(PanelLeft),
  agent: <LoomiMono />,
  /** #325/#326 think — Lucide-ish brain/spark; keep custom thought-process glyph */
  think: <Svg strokeWidth={2}><path d="M12 18V5" /><path d="M15 13a4.17 4.17 0 01-3-4 4.17 4.17 0 01-3 4" /><path d="M17.707 6.294A3 3 0 1012 5a3 3 0 10-5.707 1.294" /><path d="M17.996 5.125a4 4 0 012.526 5.77" /><path d="M18 18a4 4 0 002-7.465" /><path d="M19.967 17.482a4 4 0 11-7.967.517 4 4 0 11-7.967-.517" /><path d="M6 18a4 4 0 01-2-7.465" /><path d="M6.004 5.125a4 4 0 00-2.526 5.77" /></Svg>,
  memoryHead: <Svg strokeWidth={1.5}><path d="M7 22v-4.4a8 8 0 1 1 12.4-7.4l1.9 3.4a1 1 0 0 1-.9 1.4H19v2a2.5 2.5 0 0 1-2.5 2.5H15V22a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1Z" /><path d="M12.6 6.2 10 10.6h3.2L11 14.8" /></Svg>,
  memoryChev: L(ChevronRight, 1.5),
  keyReturn: <Svg strokeWidth={1.5}><path d="M19 7v5a4 4 0 0 1-4 4H7" /><path d="m10 12-3 4 3 4" /></Svg>,
  history: L(History, 2),
  circlePlus: L(CirclePlus, 2),
  messageSquare: L(MessageSquare, 2),
  scrollText: L(ScrollText, 2),
  globe: L(Globe, 2),
  imageLine: L(Image, 2),
  videoLine: L(Video, 2),
  fileSearch: L(FileSearch, 2),
  squareCode: L(SquareCode, 2),
  fileCode: L(FileCode, 2),
  filePenLine: L(FilePenLine, 2),
  listChecks: L(ListChecks, 2),
  code: L(Code, 2),
  eyeView: L(Eye, 2),
  sparkles: L(Sparkles, 2),
  skill: L(FileText),
  uploadArrow: L(Upload),
  upload: L(Paperclip),
  next: L(ChevronRight),
  expandPanel: L(Expand),
  search: L(Search),
  assets: L(Layers),
  grid: L(Grid2x2),
  merge: <Svg><rect x="4" y="4" width="11" height="11" rx="2" /><path d="M9 20h9a2 2 0 0 0 2-2V9" /></Svg>,
  alignLeft: <Svg><path d="M4.5 4v16M8 8h11M8 16h6" /></Svg>,
  alignCenterH: <Svg><path d="M12 4v16M6 8h12M8.5 16h7" /></Svg>,
  alignRight: <Svg><path d="M19.5 4v16M5 8h11M10 16h6" /></Svg>,
  alignTop: <Svg><path d="M4 4.5h16M8 8v11M16 8v6" /></Svg>,
  alignCenterV: <Svg><path d="M4 12h16M8 6v12M16 8.5v7" /></Svg>,
  alignBottom: <Svg><path d="M4 19.5h16M8 5v11M16 10v6" /></Svg>,
  distributeH: <Svg><path d="M4.5 4v16M19.5 4v16" /><rect x="9.5" y="8" width="5" height="8" rx="1" /></Svg>,
  distributeV: <Svg><path d="M4 4.5h16M4 19.5h16" /><rect x="8" y="9.5" width="8" height="5" rx="1" /></Svg>,
  rect: L(Square),
  ellipse: <Svg><ellipse cx="12" cy="12" rx="8.5" ry="7" /></Svg>,
  polygon: <Svg><path d="m12 3.5 8.5 6.2-3.2 10H6.7l-3.2-10z" /></Svg>,
  unite: <Svg><path d="M4 4h10v6h6v10H10v-6H4z" /></Svg>,
  subtract: <Svg><path d="M4 4h10v6h-4v4H4z" /><path d="M10 10h10v10H10z" strokeDasharray="2 2" /></Svg>,
  intersect: <Svg><path d="M4 4h10v10H4zM10 10h10v10H10z" strokeDasharray="2 2" /><path d="M10 10h4v4h-4z" fill="currentColor" /></Svg>,
  exclude: <Svg><path d="M4 4h10v6h-4v4H4zM20 20H10v-6h4v-4h6z" fill="currentColor" stroke="none" /><path d="M4 4h10v10H4zM10 10h10v10H10z" /></Svg>,
  pen: L(PenLine),
  star: L(Star),
  textTool: L(Type),
  frame: L(Frame),
  hand: L(Hand),
  radius: <Svg><path d="M4.5 19.5V11a6.5 6.5 0 0 1 6.5-6.5h8.5" /></Svg>,
  link: L(Link),
  keyboard: L(Keyboard),
  stroke: <Svg><circle cx="12" cy="12" r="7.5" /><circle cx="12" cy="12" r="4" /></Svg>,
  spacing: <Svg><path d="M5 7h14M5 12h14M5 17h9" /></Svg>,
  replace: L(Replace),
  minus: L(Minus),
  rotate: L(RotateCcw),
  adjust: L(SlidersHorizontal),
  effects: L(WandSparkles),
  restore: L(History),
  preview: L(Maximize2),
  export: L(Upload),
  play: L(Play, LUCIDE_STROKE, { fill: 'currentColor' }),
  pause: L(Pause, LUCIDE_STROKE, { fill: 'currentColor' }),
  stop: L(Square, LUCIDE_STROKE, { fill: 'currentColor' }),
  bell: L(Bell),
  memory: <Svg><path d="M12 4.5a5.5 5.5 0 0 0-5.5 5.5c0 2 1 3.4 2.3 4.4.5.4.7 1 .7 1.6v1.5h5v-1.5c0-.6.2-1.2.7-1.6 1.3-1 2.3-2.4 2.3-4.4A5.5 5.5 0 0 0 12 4.5zM9.5 20h5" /></Svg>,
  pinOutline: L(Pin),
  pinSolid: L(Pin, LUCIDE_STROKE, { fill: 'currentColor' }),
  resetCcw: L(RotateCcw),
  pin: L(Pin),
  select: L(MousePointer2),
  genImage: L(ImagePlus),
  chevron: L(ChevronDown),
  check: L(Check),
  question: L(HelpCircle),
  send: L(Send),
  download: L(Download),
  more: L(Ellipsis),
  crop: L(Crop),
  flipH: L(FlipHorizontal2),
  flipV: L(FlipVertical2),
  /** #439 quick-edit brand glyph — keep in-house (uses --ca-float) */
  quick: <Svg fill><circle cx="12" cy="12" r="10" /><path fill="var(--ca-float)" d="M10.2 15.6h3.6v-1.3h-2.2V9.8h-1.4zM16.3 8.6a2.6 2.6 0 1 0 0 5.2 2.6 2.6 0 0 0 0-5.2m0 1.3a1.3 1.3 0 1 1 0 2.6 1.3 1.3 0 0 1 0-2.6M5.4 12.2h3.2v-1.3H5.4z" /></Svg>,
  upscale: <Svg><rect x="3" y="5.5" width="18" height="13" rx="3" /><path d="M7.5 9.5v5M7.5 12h3M10.5 9.5v5M13.5 9.5v5h1.5a2.5 2.5 0 0 0 0-5z" /></Svg>,
  cutout: <Svg><path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2" /><circle cx="12" cy="10" r="2.5" /><path d="M7.5 17a4.5 4.5 0 0 1 9 0" /></Svg>,
  erase: L(Eraser),
  layers: L(Layers),
  text: L(ALargeSmall),
  angles: L(Cuboid),
  animate: L(Video),
  expand: L(Expand),
  undo: L(Undo2),
  reset: L(RefreshCw),
  redo: L(Redo2),
  refs: L(Image),
  thumbsUp: L(ThumbsUp),
  thumbsDown: L(ThumbsDown),
  // #439 memory dialog group titles: in-house outline icons (stroke 1.5 @24)
  memPalette: <Svg strokeWidth={1.5}><path d="M12 3a9 9 0 1 0 0 18c1 0 1.7-.8 1.7-1.7 0-.5-.2-.9-.5-1.2-.3-.3-.5-.7-.5-1.2 0-.9.8-1.7 1.7-1.7H16a5 5 0 0 0 5-5C21 6.2 17 3 12 3z" /><circle cx="7.5" cy="11.5" r="1.1" /><circle cx="9.5" cy="7.5" r="1.1" /><circle cx="14.5" cy="7.5" r="1.1" /></Svg>,
  memBook: <Svg strokeWidth={1.5}><path d="M2.5 5.5C5 4.5 8.5 4.5 12 6.5v13c-3.5-2-7-2-9.5-1z" /><path d="M21.5 5.5c-2.5-1-6-1-9.5 1v13c3.5-2 7-2 9.5-1z" /></Svg>,
  memWrench: <Svg strokeWidth={1.5}><path d="M20.8 6.3a5.2 5.2 0 0 1-6.9 6.1l-7.2 7.2a2.1 2.1 0 0 1-3-3l7.2-7.2a5.2 5.2 0 0 1 6.1-6.9l-3.2 3.2.4 2.6 2.6.4 3.2-3.2c.1.3.1.5.1.8z" /></Svg>,
  memAssets: <Svg strokeWidth={1.5}><path d="M7 3.5l3.5 6h-7z" /><circle cx="16.5" cy="7" r="3" /><rect x="9" y="13.5" width="6" height="6" rx=".6" transform="rotate(15 12 16.5)" /></Svg>,
  info: L(Info),
}
