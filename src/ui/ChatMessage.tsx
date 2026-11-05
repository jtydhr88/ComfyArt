import { useEffect, useState, type ReactNode } from 'react'
import type { Editor } from 'tldraw'

import { answerAsk, continueRun, outputsOf, toolLabel, toolName, type AskAnswers, type AskQuestion, type BotBlock, type BotMessage } from '../bot'
import { setAgentPlanConfirmed } from '../comfy'
import { draftAtom } from '../agent'
import { errorText } from '../jobs'
import { confirmAtom } from './Confirm'
import OVER_QUOTE from '../../bot/over_quote.json'
import { schedulesOpenAtom } from '../schedules'
import { Icons } from './icons'
import { SkillChip } from './SkillChip'
import { Markdown } from './Markdown'
import { Thumb } from './TaskDetails'
import { CopyButton } from './CopyButton'
import { lang, t } from '../i18n'
import { openMemoryDialog } from './MemoryDialog'
import { stepState } from './stepState'
import { readLocal, writeLocal } from '../localPrefs'
import { attachSkill, loadSkills, skillCreatorAtom } from '../skills'
import { openSkillEditor } from './SkillsDialog'

const GEN_TOOLS = new Set(['generate_image', 'generate_video', 'edit_image', 'animate_image', 'upscale_image', 'remove_background', 'expand_image', 'split_layers', 'change_angle', 'replace_text', 'edit_region', 'erase_region', 'move_object', 'style_transfer', 'extend_video', 'upscale_video', 'remove_video_background', 'generate_music', 'generate_sound_effect', 'text_to_speech', 'image_to_3d', 'edit_elements', 'create_mockup', 'create_slides'])

/** #326/#348/#420 process-timeline kinds (multi-step process rail). */
type ProcessKind =
  | 'thought' | 'outputting' | 'skill' | 'skill_created' | 'skill_file_read' | 'search' | 'search_pages'
  | 'image' | 'video'
  | 'ref_analysis'
  | 'code' | 'code_generated' | 'code_updated' | 'design_validated' | 'preview_artifact'
  | 'memory_retrieved' | 'memory_updating' | 'memory_updated'
  | 'tool'

const VIDEO_TOOLS = new Set(['generate_video', 'animate_image', 'extend_video', 'upscale_video', 'remove_video_background'])
const SEARCH_TOOLS = new Set(['WebSearch', 'web_search', 'google_web_search', 'WebFetch', 'web_fetch', 'websearch'])
const IMAGE_PROCESS_TOOLS = new Set([
  'generate_image', 'edit_image', 'upscale_image', 'remove_background', 'expand_image', 'split_layers',
  'change_angle', 'replace_text', 'edit_region', 'erase_region', 'move_object', 'style_transfer',
  'edit_elements', 'create_mockup', 'create_slides', 'wait_generation', 'image_to_3d', 'vectorize_image',
])
const CODE_GENERATED_TOOLS = new Set(['Write', 'write_file', 'create_file', 'WriteFile', 'code_generated'])
const CODE_UPDATED_TOOLS = new Set(['Edit', 'str_replace', 'apply_patch', 'NotebookEdit', 'code_updated'])
const DESIGN_VALIDATED_TOOLS = new Set(['validate_workflow', 'design_validated', 'validate_design'])
const PREVIEW_ARTIFACT_TOOLS = new Set(['preview_artifact', 'place_html'])
const CODE_HEADER_TOOLS = new Set(['writing_code', 'write_code', 'WritingCode', 'code'])
const CODE_SUB_KINDS = new Set<ProcessKind>(['code_generated', 'code_updated', 'design_validated', 'preview_artifact'])

const PROCESS_ICONS: Record<ProcessKind, ReactNode> = {
  thought: Icons.think,
  outputting: Icons.think,
  // #627: stacked docs (live CN step-rail); was scrollText
  skill: Icons.files,
  // #650 follow-up: 「Skill Created」 row after a successful skill save
  skill_created: Icons.files,
  skill_file_read: Icons.fileSearch,
  search: Icons.globe,
  search_pages: Icons.globe,
  image: Icons.sparkleImage,
  video: Icons.videoLine,
  // #627: ref card; chevron sits on the label like memory_updated
  ref_analysis: Icons.refAnalysis,
  code: Icons.squareCode,
  code_generated: Icons.fileCode,
  code_updated: Icons.filePenLine,
  design_validated: Icons.listChecks,
  preview_artifact: Icons.sparkles,
  // #435/#437: memory rows share the in-house memoryHead icon
  memory_retrieved: Icons.memoryHead,
  memory_updating: Icons.memoryHead,
  memory_updated: Icons.memoryHead,
  tool: Icons.agent,
}

function skillActionIsFileRead(input?: Record<string, any>): boolean {
  const action = String(input?.action ?? '').toLowerCase()
  // #462: read without a path loads the whole skill (技能加载完成); read with a path reads one of its files
  return (action === 'read' && !!input?.path) || action === 'file' || action === 'read_file' || action === 'file_read'
}

function processModelName(input?: Record<string, any>): string | undefined {
  const m = input?.model ?? input?.model_name ?? input?.modelName
  return typeof m === 'string' && m.trim() ? m.trim() : undefined
}

function processAspectRatio(input?: Record<string, any>): string | undefined {
  const raw = input?.aspect_ratio ?? input?.aspectRatio ?? input?.ratio ?? input?.params?.aspect_ratio
  if (typeof raw === 'string' && raw.trim()) {
    const s = raw.trim().replace(':', ' / ')
    if (/^\d+(\.\d+)?\s*\/\s*\d+(\.\d+)?$/.test(s)) return s
  }
  const w = Number(input?.width ?? input?.w)
  const h = Number(input?.height ?? input?.h)
  if (w > 0 && h > 0) return `${w} / ${h}`
  return undefined
}

/** #437: the source favicon; on error (offline / blocked) it unmounts, leaving only the globe icon. */
function Favicon({ src }: { src: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) return null
  return <img className="ca-process__favicon" src={src} alt="" aria-hidden="true" data-testid="search-favicon" onError={() => setFailed(true)} />
}

/** #437: favicon of the search source (first result's site), else the engine's own mark. */
function searchFavicon(result?: BotBlock): string {
  const host = (result?.text ?? '').match(/https?:\/\/([^/"\s\\]+)/)?.[1] ?? 'www.google.com'
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=32`
}

function searchResultCount(use: BotBlock, result?: BotBlock): number | undefined {
  const raw = use.input?.num_results ?? use.input?.count ?? use.input?.n ?? result?.detail?.count ?? result?.detail?.num_results
  if (typeof raw === 'number' && raw > 0) return raw
  if (typeof raw === 'string' && /^\d+$/.test(raw) && Number(raw) > 0) return Number(raw)
  const text = result?.text ?? ''
  const urls = text.match(/https?:\/\//g)
  if (urls && urls.length > 0) return urls.length
  return undefined
}

function processKindOf(b: BotBlock, opts?: { result?: BotBlock; live?: boolean }): ProcessKind | null {
  if (b.type === 'thinking') return 'thought'
  if (b.type === 'memory_updated') return 'memory_updated'
  if (b.type !== 'tool_use') return null
  const n = toolName(b.name)
  if ((n === 'skill' || n === 'Skill') && skillCreatedOf(b, opts?.result)) return 'skill_created'
  if (n === 'skill' || n === 'Skill') return skillActionIsFileRead(b.input) ? 'skill_file_read' : 'skill'
  if (SEARCH_TOOLS.has(n) || (/search|fetch/i.test(n) && /web/i.test(n))) {
    if (!opts?.live) {
      const nPages = searchResultCount(b, opts?.result)
      if (nPages != null) return 'search_pages'
    }
    return 'search'
  }
  if (CODE_HEADER_TOOLS.has(n) || /^writing[_-]?code$/i.test(n)) return 'code'
  if (CODE_GENERATED_TOOLS.has(n)) return 'code_generated'
  if (CODE_UPDATED_TOOLS.has(n)) return 'code_updated'
  if (DESIGN_VALIDATED_TOOLS.has(n)) return 'design_validated'
  if (PREVIEW_ARTIFACT_TOOLS.has(n)) return 'preview_artifact'
  if (VIDEO_TOOLS.has(n)) return 'video'
  if (IMAGE_PROCESS_TOOLS.has(n)) return 'image'
  // Other generation-ish tools still join the rail with a generic icon
  if (GEN_TOOLS.has(n)) return n.includes('video') || n.includes('animate') ? 'video' : 'image'
  // #420: canvas tools (get_canvas / create_frame / add_text / …) and any other
  // previously off-rail tool_use stay on the process spine — never flush into ca-chat__tool Step.
  return 'tool'
}

/** #650 follow-up: a finished `skill` save (action="save") returns { saved, id, description } → the reference-design
 *  creation-complete card (Skill ready / Skill Created rows + card with Preview / Try this skill). */
export type CreatedSkill = { id: string; name: string; description: string }
export function skillCreatedOf(b: BotBlock, result?: BotBlock): CreatedSkill | null {
  if (b.type !== 'tool_use' || (b.input as { action?: string } | undefined)?.action !== 'save' || !result || stepState(result) !== 'done') return null
  try {
    const r = JSON.parse(result.text ?? '') as { saved?: string; id?: string; description?: string }
    return r.id && r.saved ? { id: r.id, name: r.saved, description: r.description ?? '' } : null
  } catch { return null }
}

export function SkillCreatedCard({ skill }: { skill: CreatedSkill }) {
  const tryIt = () => void loadSkills().then((all) => {
    const s = all.find((x) => x.id === skill.id)
    if (!s) return
    skillCreatorAtom.set({ on: false })
    attachSkill(s)  // #673: a hidden skill shows the notice instead of a chip
  })
  return (
    <div className="ca-chat__skillcard" data-testid="skill-created-card" data-skill={skill.id}>
      <span className="ca-chat__skillcard-thumb" aria-hidden><span className="ca-icon">{Icons.files}</span></span>
      <span className="ca-chat__skillcard-meta">
        <span className="ca-chat__skillcard-name" data-testid="skill-created-name">{skill.name}</span>
        {skill.description && <span className="ca-chat__skillcard-desc" data-testid="skill-created-desc">{skill.description}</span>}
      </span>
      <button type="button" className="ca-chat__skillcard-btn" data-testid="skill-created-preview" onClick={() => openSkillEditor(skill.id)}>{t('chatMessage.skillPreview')}</button>
      <button type="button" className="ca-chat__skillcard-btn" data-variant="primary" data-testid="skill-created-try" onClick={tryIt}>{t('chatMessage.tryThisSkill')}</button>
    </div>
  )
}

/**
 * #437: a reasoning turn in progress reads 思考中 (one key, chatMessage.thinking) until the reference is
 * measured on a memory-writing, tool-calling turn. Set to false to drop it: the row then reads 输出中….
 */
export const SHOW_THINKING_ROW = true

function liveThoughtLabel(): string {
  return SHOW_THINKING_ROW ? t('chatMessage.thinking') : t('chatMessage.outputting')
}

function processLabel(
  kind: ProcessKind,
  live: boolean,
  opts?: { fallback?: string; model?: string; pages?: number },
): string {
  if (kind === 'thought') return live ? liveThoughtLabel() : t('chatMessage.thought')
  // #627: post-image rail = 参考素材分析结束 / Reference analysis done (not a second 思考完成)
  if (kind === 'ref_analysis') return live ? t('chatMessage.referenceAnalysisLive') : t('chatMessage.referenceAnalysisDone')
  if (kind === 'outputting') return live ? t('chatMessage.outputting') : t('chatMessage.thought')
  if (kind === 'skill') return t('chatMessage.skillReady')
  if (kind === 'skill_created') return t('chatMessage.skillCreated')
  if (kind === 'skill_file_read') return live ? t('chatMessage.skillFileReadLive') : t('chatMessage.skillFileRead')
  if (kind === 'search') return live ? t('chatMessage.searchingWeb') : t('chatMessage.webSearchDone')
  // #437: the done search row keeps the page count (1 web page / N web pages); the card below it carries 联网搜索结果
  if (kind === 'search_pages') return t((opts?.pages ?? 0) === 1 ? 'chatMessage.webPage' : 'chatMessage.webPages', opts?.pages ?? 0)
  // #437: the generation row reads the model name itself (no 已生成图片/已生成视频 copy, #432 folded in)
  if (kind === 'image' || kind === 'video') {
    if (opts?.model) return opts.model
    if (live) return t(kind === 'image' ? 'chatMessage.generatingImages' : 'chatMessage.generatingVideo')
    return opts?.fallback || t('chatMessage.inProgress')
  }
  if (kind === 'code') return live ? t('chatMessage.writingCodeLive') : t('chatMessage.writingCode')
  if (kind === 'code_generated') return t('chatMessage.codeGenerated')
  if (kind === 'code_updated') return t('chatMessage.codeUpdated')
  if (kind === 'design_validated') return t('chatMessage.designValidated')
  if (kind === 'preview_artifact') return t('chatMessage.previewArtifact')
  if (kind === 'memory_retrieved') return t('chatMessage.memoryRetrieved')
  if (kind === 'memory_updating') return t('chatMessage.memoryUpdating')
  if (kind === 'memory_updated') return t('chatMessage.memoryUpdated')
  return opts?.fallback || t('chatMessage.inProgress')
}

export function textOf(m: BotMessage): string {
  return m.blocks.filter((b) => b.type === 'text').map((b) => b.text ?? '').join('').trim()
}

function summary(b: BotBlock): string {
  const input = b.input ?? {}
  const name = toolName(b.name)
  if (name === 'memory') return [input.action, input.text ?? input.new].filter(Boolean).join(t('chatMessage.colon'))
  if (name === 'skill') return [input.action, input.name].filter(Boolean).join(' ')
  return String(input.prompt ?? input.text ?? input.name ?? input.title ?? '').slice(0, 80)
}

function Step({ editor, use, result, thumbs = true }: { editor: Editor; use: BotBlock; result?: BotBlock; thumbs?: boolean }) {
  const [open, setOpen] = useState(false)
  const outputs = result && thumbs ? outputsOf([result]) : []
  const kind = stepState(result)
  const state = kind === 'running' ? t('chatMessage.inProgress') : kind === 'cancelled' ? t('chatMessage.cancelled') : kind === 'error' ? t('chatMessage.failed') : result?.duration_ms != null ? `${(result.duration_ms / 1000).toFixed(1)}s` : ''
  return (
    <div className="ca-chat__tool" data-error={kind === 'error' || undefined} data-cancelled={kind === 'cancelled' || undefined}>
      <button type="button" className="ca-chat__step" onClick={() => setOpen(!open)}>
        <span className="ca-icon">{GEN_TOOLS.has(toolName(use.name)) ? Icons.genImage : kind === 'error' ? Icons.close : kind === 'done' ? Icons.check : Icons.agent}</span>
        <span>{toolLabel(use.name)}</span>
        <span className="ca-chat__arg">{summary(use)}</span>
        <span className="ca-chat__status">{state}</span>
      </button>
      {open && (
        <div className="ca-chat__io">
          <pre>{JSON.stringify(use.input ?? {}, null, 2)}</pre>
          {result?.text && <pre>{result.text}</pre>}
        </div>
      )}
      {outputs.length > 0 && <div className="ca-chat__thumbs">{outputs.map((s) => <Thumb key={s} editor={editor} src={s} />)}</div>}
    </div>
  )
}

/** #232: an LLM timeout / 429 / 5xx retry, drawn as an ordinary tool row; 429 counts down to the retry. */
function Retry({ b: block, live }: { b: BotBlock; live: boolean }) {
  const b = block as BotBlock & { kind?: string; attempt?: number; max?: number; until?: number; http_status?: number }
  const [now, setNow] = useState(() => Date.now())
  const left = Math.ceil(((b.until ?? 0) - now) / 1000)
  const waiting = live && left > 0
  useEffect(() => {
    if (!waiting) return
    const id = setInterval(() => setNow(Date.now()), 250)
    return () => clearInterval(id)
  }, [waiting])
  const reason = b.kind === '429' ? t('chatMessage.retryRateLimited', b.attempt ?? 1, b.max ?? 2) : b.kind === 'timeout' ? t('chatMessage.retryTimeout', b.attempt ?? 1, b.max ?? 2) : t('chatMessage.retryServer', b.http_status || '5xx', b.attempt ?? 1, b.max ?? 2)
  return (
    <div className="ca-chat__tool" data-retry={b.kind}>
      <div className="ca-chat__step" style={{ cursor: 'default' }}>
        <span className="ca-icon">{Icons.agent}</span>
        <span>{t('chatMessage.retry')}</span>
        <span className="ca-chat__arg">{reason}</span>
        <span className="ca-chat__status">{waiting ? t('chatMessage.retryIn', left) : live ? t('chatMessage.inProgress') : t('chatMessage.retried')}</span>
      </div>
    </div>
  )
}

/** #391 stop card (locked copy): one sentence + buttons; 「详情」 fold with actual usage only (no caps, no bars). */
/** #419: paid jobs this turn had already sent when the user stopped (they still finish and are charged). */
export function stoppedSubmitted(m: BotMessage): number {
  return m.blocks.reduce((n, b) => (b.type === 'run_stop' ? Math.max(n, b.submitted ?? 0) : n), 0)
}

export function RunStop({ b, latest }: { b: BotBlock; latest: boolean }) {
  const [busy, setBusy] = useState(false)
  const [closed, setClosed] = useState(false)
  const [error, setError] = useState('')
  const reason = b.stop?.reason ?? 'error'
  // #492: normal-complete (reason=done) stop card is never shown — product AC #492; backend still emits.
  // Filter here so ChatMessage path, reloaded chats, and the #393 RunStop harness all stay empty.
  if (reason === 'done') return null
  const lk = lang === 'zh' ? 'zh' : 'en'
  const copy = b.copy?.[lk]
  const title = copy?.title ?? t(`runStop.reason.${reason}`)
  const body = copy?.body ?? ''
  const details = b.details?.[lk] ?? []
  const go = () => {
    if (!b.run_id) return
    setBusy(true)
    continueRun(b.run_id, lang).catch((e) => { setError(errorText(e)); setBusy(false) })
  }
  return (
    <div className="ca-run" data-reason={reason} data-key={b.copy?.key} data-tone={b.copy?.tone}>
      <div className="ca-run__head">
        <span className="ca-icon">{Icons.agent}</span>
        <span className="ca-run__title">{title}</span>
      </div>
      {body && <div className="ca-run__body">{body}</div>}
      {copy?.reason && copy.reason !== body && <div className="ca-run__body" data-run-reason="">{copy.reason}</div>}
      {details.length > 0 && (
        <details className="ca-run__details">
          <summary>{t('runStop.details')}</summary>
          {details.map((line) => <div key={line}>{line}</div>)}
        </details>
      )}
      {error && <div className="ca-chat__hint">{error}</div>}
      {b.can_continue && latest && !closed && copy?.primary && (
        <div className="ca-panel__foot">
          {copy.secondary && <button type="button" className="ca-panel__secondary" disabled={busy} onClick={() => setClosed(true)}>{copy.secondary}</button>}
          {/* #709: when the card offers 继续生成, it is THE primary action; the locked primary steps back */}
          <button type="button" className="ca-panel__primary" data-action={b.copy?.action} disabled={busy} onClick={go}>{copy.primary}</button>
        </div>
      )}
    </div>
  )
}

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

type QState = { selected: string[]; other: string }

function askQuestions(b: BotBlock): AskQuestion[] {
  if (b.questions?.length) return b.questions
  return [{
    id: '_',
    prompt: b.prompt ?? '',
    options: b.options ?? [],
    min_selections: b.min_selections,
    max_selections: b.max_selections,
    allow_other: b.allow_other,
    defaults: b.defaults,
    page: b.page ?? 1,
  }]
}

function askPageCount(b: BotBlock, questions: AskQuestion[]): number {
  if (b.page_count && b.page_count > 0) return b.page_count
  return Math.max(1, ...questions.map((q) => q.page ?? 1))
}

function qDefaults(q: AskQuestion): string[] {
  const max = q.max_selections ?? (q.options?.length ? 1 : 0)
  if (q.defaults?.length) return q.defaults.slice(0, max)
  const rec = (q.options ?? []).filter((o) => o.recommended).map((o) => o.id)
  return rec.slice(0, max)
}

function initQStates(questions: AskQuestion[]): Record<string, QState> {
  const out: Record<string, QState> = {}
  for (const q of questions) {
    out[q.id] = { selected: qDefaults(q), other: '' }
  }
  return out
}

function qAnswerLabels(q: AskQuestion, selected: string[], other?: string): string {
  const options = q.options ?? []
  const labels = selected.map((id) => options.find((o) => o.id === id)?.label ?? id)
  return [...labels, other].filter(Boolean).join(t('common.listSep'))
}

function askAnswerLabels(b: BotBlock): string {
  const questions = askQuestions(b)
  if (b.answers && questions.length) {
    return questions.map((q) => {
      const a = b.answers![q.id]
      if (!a) return ''
      return qAnswerLabels(q, a.selected ?? [], a.other_text)
    }).filter(Boolean).join(t('common.listSep')) || ''
  }
  const options = b.options ?? []
  const labels = (b.selected ?? []).map((id) => options.find((o) => o.id === id)?.label ?? id)
  return [...labels, b.other_text].filter(Boolean).join(t('common.listSep'))
}

function qFilled(q: AskQuestion, st: QState): boolean {
  const textOnly = !(q.options?.length) && !!q.allow_other
  if (textOnly) return st.other.trim().length > 0
  if (st.selected.length > 0) return true
  return !!(q.allow_other && st.other.trim().length > 0)
}

function toAnswers(questions: AskQuestion[], states: Record<string, QState>): AskAnswers {
  const answers: AskAnswers = {}
  for (const q of questions) {
    const st = states[q.id] ?? { selected: [], other: '' }
    const entry: { selected: string[]; other_text?: string } = { selected: st.selected }
    if (q.allow_other && st.other.trim()) {
      entry.other_text = st.other.trim()
    }
    answers[q.id] = entry
  }
  return answers
}

/** Historical chip asks (no kind) keep the memo path. */
function AskMemo({ b }: { b: BotBlock }) {
  const labels = askAnswerLabels(b)
  return (
    <div className="ca-chat__memo">
      <span className="ca-icon">{Icons.check}</span>
      {b.prompt} → {b.status === 'answered' ? labels : b.status === 'expired' ? t('chatMessage.timedOut') : t('chatMessage.canceled')}
    </div>
  )
}

/** #766: empty selection + no other text = Skip (right user bubble with skip copy only). */
function isAskSkipped(b: BotBlock): boolean {
  const questions = askQuestions(b)
  if (b.answers) {
    return questions.every((q) => {
      const a = b.answers![q.id]
      return !a || (!(a.selected?.length) && !(a.other_text?.trim()))
    })
  }
  return !(b.selected?.length) && !(b.other_text?.trim())
}

/** #766: answered ask → right user bubble (same shell as the prompt); never the old left grey 问/答 bar. */
function QuestionAnswered({ b }: { b: BotBlock }) {
  if (b.status !== 'answered') {
    return (
      <div className="ca-chat__memo">
        <span className="ca-icon">{Icons.check}</span>
        {b.prompt} → {b.status === 'expired' ? t('chatMessage.timedOut') : t('chatMessage.canceled')}
      </div>
    )
  }
  if (isAskSkipped(b)) {
    return (
      <div className="ca-chat__user" data-testid="ask-answer-bubble" data-ask="skip">
        <div className="ca-chat__bubble ca-chat__bubble--ask">{t('chatMessage.skipThisQuestion')}</div>
      </div>
    )
  }
  const questions = askQuestions(b)
  const lines: string[] = []
  const multi = questions.length > 1 || !!(b.answers && Object.keys(b.answers).length > 1)
  if (multi) {
    for (const q of questions) {
      const a = b.answers?.[q.id]
      const answer = a ? qAnswerLabels(q, a.selected ?? [], a.other_text) : askAnswerLabels(b)
      if (!answer) continue
      lines.push(`${t('chatMessage.qaAsk')}: ${q.prompt}`)
      lines.push(`${t('chatMessage.qaAnswer')}: ${answer}`)
    }
  } else {
    const prompt = questions[0]?.prompt || b.prompt || ''
    const answer = askAnswerLabels(b)
    lines.push(`${t('chatMessage.qaAsk')}: ${prompt}`)
    lines.push(`${t('chatMessage.qaAnswer')}: ${answer}`)
  }
  return (
    <div className="ca-chat__user" data-testid="ask-answer-bubble" data-ask="answer">
      <div className="ca-chat__bubble ca-chat__bubble--ask">{lines.join('\n')}</div>
    </div>
  )
}

function QuestionBlock({ q, st, onChange }: { q: AskQuestion; st: QState; onChange: (next: QState) => void }) {
  const options = q.options ?? []
  const multi = (q.max_selections ?? 1) > 1
  const allowOther = !!q.allow_other
  const textOnly = !options.length && allowOther
  // #763: D is always the inline `Other (type your answer)...` row on choice cards
  const recommended = new Set([...(q.defaults ?? []), ...options.filter((o) => o.recommended).map((o) => o.id)])
  const otherLetter = LETTERS[options.length] ?? 'A'

  const toggle = (id: string) => {
    // Product lock: pick A–D keeps other text; only moves soft-select (do NOT clear other)
    if (!multi) onChange({ ...st, selected: [id] })
    else {
      const selected = st.selected.includes(id)
        ? st.selected.filter((x) => x !== id)
        : [...st.selected, id].slice(-(q.max_selections ?? 1))
      onChange({ ...st, selected })
    }
  }
  const onOther = (value: string) => {
    // Single-select: typing/filling other clears A–D soft-select; multi: other coexists
    if (!multi && value.trim()) onChange({ ...st, selected: [], other: value })
    else onChange({ ...st, other: value })
  }
  const stealOther = () => {
    // Refocus nonempty other steals soft-select back (deselects A–D); text stays
    if (!multi && st.other.trim() && st.selected.length) onChange({ ...st, selected: [] })
  }
  // Soft-select on other only when it is the active answer (single: no A–D selected; multi: when filled)
  const otherOn = !!st.other.trim() && (multi || st.selected.length === 0)

  return (
    <div className="ca-q__block">
      <div className="ca-q__prompt">{q.prompt}{multi && <span className="ca-q__hint">{t('chatMessage.multipleChoice')}</span>}</div>
      <div className="ca-q__opts">
        {textOnly ? (
          <div className="ca-q__opt" data-text="" data-on={st.other.trim() ? true : undefined}>
            <span className="ca-q__letter">A</span>
            <input
              type="text"
              className="ca-q__input"
              value={st.other}
              placeholder={q.placeholder || t('chatMessage.writeYourIdea')}
              onChange={(e) => onOther(e.target.value)}
              onKeyDown={(e) => e.stopPropagation()}
            />
          </div>
        ) : (
          <>
            {options.map((o, i) => (
              <button key={o.id} type="button" className="ca-q__opt" title={o.description} data-on={st.selected.includes(o.id) || undefined} onClick={() => toggle(o.id)}>
                <span className="ca-q__letter">{LETTERS[i] ?? String(i + 1)}</span>
                <span className="ca-q__text">{o.label}</span>
                {recommended.has(o.id) && <span className="ca-q__rec">{t('chatMessage.recommended')}</span>}
              </button>
            ))}
            {(
              <div className="ca-q__opt" data-other="" data-text="" data-on={otherOn || undefined} data-off={!allowOther || undefined}>
                <span className="ca-q__letter">{otherLetter}</span>
                <input
                  type="text"
                  className="ca-q__input"
                  value={st.other}
                  placeholder={q.placeholder || t('chatMessage.other')}
                  disabled={!allowOther}
                  onChange={(e) => onOther(e.target.value)}
                  onFocus={stealOther}
                  onKeyDown={(e) => e.stopPropagation()}
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

/** #328/#330: reference-style Question card — multi-q + in-card paging. */
function QuestionCard({ b }: { b: BotBlock }) {
  const questions = askQuestions(b)
  const pageCount = askPageCount(b, questions)
  const allowSkip = b.allow_skip !== false
  const [page, setPage] = useState(1)
  const [furthest, setFurthest] = useState(1)
  const [states, setStates] = useState<Record<string, QState>>(() => initQStates(questions))
  const [error, setError] = useState('')
  if (b.status !== 'pending') return <QuestionAnswered b={b} />

  const onPage = questions.filter((q) => (q.page ?? 1) === page)
  const pageOk = onPage.every((q) => qFilled(q, states[q.id] ?? { selected: [], other: '' }))
  const allOk = questions.every((q) => qFilled(q, states[q.id] ?? { selected: [], other: '' }))
  const isLast = page >= pageCount
  const showPager = pageCount > 1

  const setQ = (id: string, next: QState) => setStates((s) => ({ ...s, [id]: next }))
  const go = (n: number) => {
    const next = Math.max(1, Math.min(pageCount, n))
    setPage(next)
    setFurthest((f) => Math.max(f, next))
  }
  const resolve = (answers: AskAnswers) => {
    const qs = questions
    const flatSel = qs.length === 1 ? (answers[qs[0].id]?.selected ?? []) : []
    const flatOther = qs.length === 1 ? (answers[qs[0].id]?.other_text ?? '') : ''
    void answerAsk(b.ask_id!, flatSel, flatOther, answers).catch((e) => setError(errorText(e)))
  }
  const onSkip = () => resolve(Object.fromEntries(questions.map((q) => [q.id, { selected: [] as string[] }])))
  const onNext = () => { if (!pageOk) return; go(page + 1) }
  const onSubmit = () => { if (!allOk) return; resolve(toAnswers(questions, states)) }

  return (
    <div className="ca-q">
      <div className="ca-q__head">
        <div className="ca-q__label"><span className="ca-icon">{Icons.question}</span>{t('chatMessage.question')}</div>
        {showPager && (
          <div className="ca-q__page">
            <button type="button" className="ca-q__chev" disabled={page <= 1} aria-label={t('chatMessage.prevPage')} onClick={() => go(page - 1)}>
              <span className="ca-icon ca-q__chev-icon ca-q__chev-icon--left">{Icons.next}</span>
            </button>
            <span>{t('chatMessage.pageOf', page, pageCount)}</span>
            <button type="button" className="ca-q__chev" disabled={page >= pageCount || (page >= furthest && !pageOk)} aria-label={t('chatMessage.nextPage')} onClick={() => { if (page < furthest || pageOk) go(page + 1) }}>
              <span className="ca-icon ca-q__chev-icon">{Icons.next}</span>
            </button>
          </div>
        )}
      </div>
      <div className="ca-q__body">
        {onPage.map((q) => (
          <QuestionBlock key={q.id} q={q} st={states[q.id] ?? { selected: [], other: '' }} onChange={(next) => setQ(q.id, next)} />
        ))}
      </div>
      {error && <div className="ca-chat__hint">{error}</div>}
      <div className="ca-q__foot">
        {allowSkip && <button type="button" className="ca-q__skip" onClick={onSkip}>{t('chatMessage.skip')}</button>}
        {isLast ? (
          <button type="button" className="ca-q__submit" disabled={!allOk} onClick={onSubmit}>{t('chatMessage.submit')} <span className="ca-q__key">↵</span></button>
        ) : (
          <button type="button" className="ca-q__submit" disabled={!pageOk} onClick={onNext}>{t('chatMessage.next')} <span className="ca-q__key">→</span></button>
        )}
      </div>
    </div>
  )
}

/** run_approval keeps the chip one-click Ask UI. */
function Ask({ b }: { b: BotBlock }) {
  const [picked, setPicked] = useState<string[]>([])
  const [other, setOther] = useState('')
  const [error, setError] = useState('')
  const multi = (b.max_selections ?? 1) > 1
  const options = b.options ?? []
  if (b.status !== 'pending') return <AskMemo b={b} />
  const toggle = (id: string) => setPicked(multi ? (picked.includes(id) ? picked.filter((x) => x !== id) : [...picked, id]) : [id])
  const submit = (selected: string[]) => void answerAsk(b.ask_id!, selected, other.trim()).catch((e) => setError(errorText(e)))
  return (
    <div className="ca-ask">
      <div className="ca-ask__title">{b.prompt}{multi && <span className="ca-menu__key">{t('chatMessage.multipleChoice')}</span>}</div>
      <div className="ca-panel__chips">
        {options.map((o) => (
          <button key={o.id} type="button" className="ca-panel__chip" title={o.description} data-on={picked.includes(o.id) || undefined} onClick={() => (b.kind === 'run_approval' ? submit([o.id]) : toggle(o.id))}>{o.label}</button>
        ))}
      </div>
      {b.allow_other && <input className="ca-panel__input" value={other} placeholder={t('chatMessage.orWriteYourOwn')} onChange={(e) => setOther(e.target.value)} onKeyDown={(e) => e.stopPropagation()} />}
      {error && <div className="ca-chat__hint">{error}</div>}
      {b.kind !== 'run_approval' && (
        <div className="ca-panel__foot">
          <button type="button" className="ca-panel__primary" disabled={!picked.length && !other.trim()} onClick={() => submit(picked)}>{t('chatMessage.submit')}</button>
        </div>
      )}
    </div>
  )
}

/** #763: a question is open, or just ended (answered/skipped) and real reply text has not started yet —
 * no 输出中… / Outputting… shell (rail row, bordered status, or footer label) while in this state. */
export function askQuiet(m: BotMessage) {
  let at = -1
  m.blocks.forEach((b, i) => { if (b.type === 'ask') at = i })
  if (at < 0) return false
  return !m.blocks.slice(at + 1).some((b) => b.type === 'text' && (b.text ?? '').trim() !== '')
}

/** #763: a pending question card docks directly above the composer (not inline in the timeline). */
export function isDockedQuestion(b: BotBlock) {
  return b.type === 'ask' && b.status === 'pending' && b.kind !== 'plan_quote' && b.kind !== 'run_approval' && b.kind !== OVER_QUOTE.kind
}

export function renderAsk(b: BotBlock, key: string | number) {
  if (b.kind === 'plan_quote') return <PlanQuote key={key} b={b} />
  if (b.kind === 'run_approval') return <Ask key={key} b={b} />
  if (b.kind === OVER_QUOTE.kind) return <OverQuote key={key} b={b} />
  // New question cards (kind=question) and in-flight pending without kind use QuestionCard.
  // Historical answered chips without kind keep the memo path.
  if (b.status !== 'pending' && b.kind !== 'question') return <AskMemo key={key} b={b} />
  return <QuestionCard key={key} b={b} />
}

/** #393: over-quote confirm. A dedicated card (never QuestionCard): the same cost-confirm card as a plan quote,
 * built from the shared bot/over_quote.json schema. 确认 answers [confirm], 先到这里 / dismiss answers [decline]. */
export function OverQuote({ b }: { b: BotBlock }) {
  const [error, setError] = useState('')
  const askId = b.ask_id
  const pending = b.status === 'pending'
  const copy = OVER_QUOTE.copy[lang === 'zh' ? 'zh' : 'en']
  const credits = (b as BotBlock & { credits?: number }).credits
  const body = credits != null ? copy.body.replace('{credits}', String(credits)) : (b.prompt ?? '')
  useEffect(() => {
    if (!pending || !askId) return
    let live = true
    const answer = (id: string) => void answerAsk(askId, [id], '').catch((e) => { if (live) setError(errorText(e)) })
    confirmAtom.set({
      title: t('jobs.confirmTitle'),
      desc: body,
      ok: copy.confirm,
      cancelLabel: copy.decline,
      // #393: no ✕, the backdrop does nothing; Esc = 先到这里 (cancel → decline)
      closable: false,
      backdropClose: false,
      className: 'ca-overquote',
      run: () => { if (live) answer(OVER_QUOTE.confirm) },
      cancel: () => { if (live) answer(OVER_QUOTE.decline) },
    })
    return () => {
      live = false
      const cur = confirmAtom.get()
      if (cur && cur.desc === body) confirmAtom.set(null)
    }
  }, [pending, askId]) // eslint-disable-line react-hooks/exhaustive-deps -- reopen only when this ask starts or resolves
  if (pending) return error ? <div className="ca-chat__hint">{error}</div> : null
  const ok = b.status === 'answered' && (b.selected ?? []).includes(OVER_QUOTE.confirm)
  return (
    <div className="ca-chat__memo" data-kind={OVER_QUOTE.kind}>
      <span className="ca-icon">{ok ? Icons.check : Icons.close}</span>
      {body} → {ok ? copy.confirm : b.status === 'expired' ? t('chatMessage.timedOut') : copy.decline}
    </div>
  )
}

/** #235: the plan total uses the same cost-confirm card as a single job. No second card, no new styles. */
function PlanQuote({ b }: { b: BotBlock }) {
  const [error, setError] = useState('')
  const askId = b.ask_id
  const pending = b.status === 'pending'
  const startLabel = (b.options ?? []).find((o) => o.id === 'start')?.label ?? ''
  useEffect(() => {
    if (!pending || !askId) return
    let live = true
    const open = () => confirmAtom.set({
      title: t('jobs.confirmTitle'),
      desc: b.prompt ?? '',
      ok: startLabel,
      lines: b.lines ?? [],
      totalLabel: b.total_label,
      total: b.total,
      run: () => {
        if (!live) return
        setAgentPlanConfirmed(true)
        void answerAsk(askId, ['start'], '').catch((e) => {
          if (!live) return
          setAgentPlanConfirmed(false)
          setError(errorText(e))
          open()
        })
      },
      cancel: () => {
        if (!live) return
        setAgentPlanConfirmed(false)
        void answerAsk(askId, ['cancel'], '').catch((e) => { if (live) setError(errorText(e)) })
      },
    })
    open()
    return () => {
      live = false
      const cur = confirmAtom.get()
      if (cur && cur.desc === (b.prompt ?? '')) confirmAtom.set(null)
    }
  }, [pending, askId]) // eslint-disable-line react-hooks/exhaustive-deps -- reopen only when this ask starts or resolves
  if (pending) return error ? <div className="ca-chat__hint">{error}</div> : null
  const started = b.status === 'answered' && (b.selected ?? []).includes('start')
  return (
    <div className="ca-chat__memo">
      <span className="ca-icon">{started ? Icons.check : Icons.close}</span>
      {b.prompt} → {started ? startLabel : b.status === 'expired' ? t('chatMessage.timedOut') : t('chatMessage.canceled')}
    </div>
  )
}

function Task({ editor, b }: { editor: Editor; b: BotBlock }) {
  return (
    <div className="ca-chat__task">
      <div className="ca-chat__step">
        <span className="ca-icon">{b.detail?.tool === 'generate_image' ? Icons.genImage : Icons.genVideo}</span>
        <span>{b.label}</span>
        <span className="ca-chat__status">{b.error ? t('chatMessage.generationFailed') : b.srcs ? '' : t('chatMessage.generating')}</span>
      </div>
      {b.srcs && <div className="ca-chat__thumbs">{b.srcs.map((s) => <Thumb key={s} editor={editor} src={s} />)}</div>}
    </div>
  )
}

function Plan({ b, live }: { b: BotBlock; live: boolean }) {
  const steps: { text?: string; status?: string }[] = Array.isArray(b.input?.steps) ? b.input.steps : []
  const done = steps.filter((s) => s.status === 'done').length
  return (
    <div className="ca-plan" data-live={live || undefined}>
      <div className="ca-plan__head"><span>{t('bot.plan')}</span><span className="ca-chat__status">{done}/{steps.length}</span></div>
      {steps.map((s, i) => (
        <div key={i} className="ca-plan__step" data-status={s.status}>
          <span className="ca-plan__mark">{s.status === 'done' && Icons.check}</span>
          <span>{s.text}</span>
        </div>
      ))}
    </div>
  )
}

type ProcessStep = {
  key: string
  kind: ProcessKind
  label: string
  live: boolean
  /** #421: generation (or linked wait) failed — row reads as failed, not done. */
  error?: boolean
  /** #437: the search source's real favicon, shown before the page count. */
  favicon?: string
  text?: string
  /** CSS aspect-ratio when known from tool/job; chat hero defaults via tokens otherwise. */
  aspectRatio?: string
  /** #382: memory ids for the memory_updated row. */
  memoryIds?: string[]
  /** #423: texts written this turn — shown as 「已保存 N 条」 detail under the row. */
  memoryTexts?: string[]
}

/** #437: canonical visual order for consecutive memory rows (retrieved → updating → updated). */
const MEM_STEP_ORDER: Record<string, number> = {
  memory_retrieved: 0,
  memory_updating: 1,
  memory_updated: 2,
}
function orderMemorySteps(steps: ProcessStep[]): ProcessStep[] {
  const out: ProcessStep[] = []
  let i = 0
  while (i < steps.length) {
    if (!steps[i].kind.startsWith('memory_')) {
      out.push(steps[i++])
      continue
    }
    const run: ProcessStep[] = []
    while (i < steps.length && steps[i].kind.startsWith('memory_')) run.push(steps[i++])
    run.sort((a, b) => (MEM_STEP_ORDER[a.kind] ?? 9) - (MEM_STEP_ORDER[b.kind] ?? 9))
    out.push(...run)
  }
  return out
}

/** #326/#420: multi-step process rail (solid spine · status card outside; canvas tools stay on rail). */
function ProcessTimeline({ steps: rawSteps }: { steps: ProcessStep[] }) {
  const steps = orderMemorySteps(rawSteps)
  const [openKey, setOpenKey] = useState<string | null>(null)
  const live = steps.find((s) => s.live)
  // #356/#358: flat grey media hero under live image/video only (sibling — not a new kind);
  // left edge = icon column (reference), not indented to label column
  const mediaHero = live && (live.kind === 'image' || live.kind === 'video') ? live : undefined
  return (
    <div className="ca-process" data-live={live ? true : undefined}>
      <div className="ca-process__steps">
        {steps.map((s) => {
          const isMemory = s.kind === 'memory_updated'
          const isRefAnalysis = s.kind === 'ref_analysis'
          const memKind = s.kind === 'memory_retrieved' || s.kind === 'memory_updating' || s.kind === 'memory_updated'
          const shine = s.live && !memKind
          // #382 fix: memory row uses the same row structure as the thought row (one rowbtn, same classes)
          // #627: ref_analysis expands like thought; chevron on the label matches live CN step-rail
          const canOpen = ((s.kind === 'thought' || isRefAnalysis) && !!sanitizeThoughtText(s.text ?? '')) || isMemory
          const open = openKey === s.key
          const row = (
            <>
              <span className={`ca-process__icon ca-process__icon--${s.kind}`} data-kind={s.kind}>
                <span className="ca-icon">{PROCESS_ICONS[s.kind]}</span>
              </span>
              {/* #413: a live thought on the rail shows its latest line inline, like the lone Thought tip */}
              {s.live && s.kind === 'thought' && !open && sanitizeThoughtText(s.text ?? '') ? (
                <span className="ca-process__inline">
                  <span className="ca-process__label ca-process__label--active">{s.label}</span>
                  <span className="ca-chat__arg ca-process__arg" data-testid="live-thought-inline">{sanitizeThoughtText(s.text ?? '').split('\n').at(-1)}</span>
                </span>
              ) : (
                <span className={shine ? 'ca-process__label ca-process__label--active' : 'ca-process__label'}>
                  {s.favicon && <Favicon src={s.favicon} />}
                  {s.label}
                  {isMemory && <span className="ca-process__memchev ca-icon" data-testid="memory-updated-chev">{Icons.memoryChev}</span>}
                  {isRefAnalysis && <span className="ca-process__memchev ca-icon" data-testid="ref-analysis-chev">{Icons.memoryChev}</span>}
                </span>
              )}
            </>
          )
          const onMemory = () => {
            // #436: open the same memory dialog; do not highlight the just-written entry
            openMemoryDialog()
          }
          const card = s.kind === 'search_pages' && (
            <div key={`${s.key}-card`} className="ca-process__card" data-testid="web-search-card">
              <span className="ca-process__cardtitle">{t('chatMessage.webSearchDone')}</span>
              <span className="ca-process__cardart">{Icons.searchFolder}</span>
            </div>
          )
          // #442 v6: a display:contents group so the card is a sibling of its 24px row, at the icon x
          // #423: always-visible 「已保存 N 条」 + entry list under the memory row; click still opens dialog (#436)
          const memTexts = isMemory ? (s.memoryTexts ?? []).filter(Boolean) : []
          const memDetail = memTexts.length > 0 && (
            <div className="ca-process__memdetail" data-testid="memory-saved-detail">
              <div className="ca-process__memcount">{t('chatMessage.memorySavedCount', memTexts.length)}</div>
              <ul className="ca-process__memlist">
                {memTexts.map((tx, i) => <li key={i}>{tx}</li>)}
              </ul>
            </div>
          )
          return (
            <div key={s.key} className="ca-process__group">
            <div className="ca-process__row" data-live={s.live || undefined} data-kind={s.kind} data-error={s.error || undefined} data-testid={isMemory ? 'memory-updated-row' : s.kind === 'memory_retrieved' ? 'memory-retrieved-row' : s.kind === 'memory_updating' ? 'memory-updating-row' : s.error ? 'process-row-failed' : undefined}>
              {canOpen ? (
                <button
                  type="button"
                  className="ca-process__rowbtn"
                  onClick={isMemory ? onMemory : () => setOpenKey(open ? null : s.key)}
                  aria-expanded={isMemory ? undefined : open}
                  data-testid={isMemory ? 'memory-updated-open' : undefined}
                >
                  {row}
                </button>
              ) : row}
              {/* #442: each step group owns its rail segment (icon column centre, below its icon); none beside the model row */}
              {s.kind !== 'image' && <span className="ca-process__spine" data-testid="process-rail" aria-hidden="true" />}
            </div>
            {card}
            {memDetail}
            </div>
          )
        })}
      </div>
      {/* #356/#358: image/video live → title then hero; no bordered status between.
          #437: memory_* live is process-row only — never a ca-process__status bubble (would hijack 输出中…). */}
      {live && !mediaHero && live.kind !== 'thought' && !live.kind.startsWith('memory_') && <div className="ca-process__status">{live.label}</div>}
      {mediaHero && (
        <div
          className="ca-media-hero"
          data-kind={mediaHero.kind}
          aria-hidden="true"
          style={mediaHero.aspectRatio ? { aspectRatio: mediaHero.aspectRatio } : undefined}
        />
      )}
      {steps.map((s) => {
        const detail = sanitizeThoughtText(s.text ?? '')
        return openKey === s.key && detail ? (
          <div key={`d-${s.key}`} className="ca-process__detail">{detail}</div>
        ) : null
      })}
    </div>
  )
}


/** #766 HOLD: visible Thought chrome must never show the ask_user tool name.
 * Drop whole lines that mention it (case-insensitive) so we do not leave broken
 * sentences like "Let me call  with one multiple-choice question." */
export function sanitizeThoughtText(text: string): string {
  return text
    .split('\n')
    .filter((line) => !/ask_user/i.test(line))
    .join('\n')
    .trim()
}

function Thought({ text, live }: { text: string; live: boolean }) {
  const [open, setOpen] = useState(false)
  const visible = sanitizeThoughtText(text)
  const tip = visible.split('\n').at(-1) ?? ''
  return (
    <div className="ca-chat__tool ca-chat__thought" data-live={live || undefined} data-open={open || undefined}>
      <button type="button" className="ca-chat__step" onClick={() => setOpen(!open)}>
        <span className="ca-chat__thinkicon"><span className="ca-icon">{Icons.think}</span></span>
        <span className="ca-chat__thinklabel">{live ? liveThoughtLabel() : t('chatMessage.thought')}</span>
        {!open && tip ? <span className="ca-chat__arg">{tip}</span> : null}
        <span className="ca-chat__chev ca-icon">{Icons.chevron}</span>
      </button>
      {open && visible ? <div className="ca-chat__io ca-chat__thoughttext">{visible}</div> : null}
    </div>
  )
}

type Pair = { use: BotBlock; result?: BotBlock; i: number }

function StepGroup({ editor, steps, stopped }: { editor: Editor; steps: Pair[]; stopped?: boolean }) {
  const [open, setOpen] = useState(false)
  const failed = steps.filter((s) => s.result?.status === 'error').length
  return (
    <div className="ca-chat__tool" data-open={open || undefined}>
      <button type="button" className="ca-chat__step" onClick={() => setOpen(!open)}>
        <span className="ca-icon">{failed || stopped ? Icons.close : Icons.check}</span>
        <span>{t('chatMessage.usedTools', steps.length)}</span>
        <span className="ca-chat__arg">{[...new Set(steps.map((s) => toolLabel(s.use.name)))].join(t('common.listSep'))}</span>
        <span className="ca-chat__chev ca-icon">{Icons.chevron}</span>
      </button>
      {open && <div className="ca-chat__group">{steps.map((s) => <Step key={s.i} editor={editor} use={s.use} result={s.result} thumbs={false} />)}</div>}
    </div>
  )
}


/** Image/video gen tools that mark a Done turn for #360 feedback. */
const MEDIA_DONE_TOOLS = new Set([...IMAGE_PROCESS_TOOLS, ...VIDEO_TOOLS])

function isMediaDoneMessage(m: BotMessage): boolean {
  return m.blocks.some((b) => {
    if (b.type === 'tool_use') return MEDIA_DONE_TOOLS.has(toolName(b.name))
    if (b.type === 'task') {
      const tool = String((b as any).detail?.tool ?? (b as any).tool ?? '')
      return MEDIA_DONE_TOOLS.has(tool) || tool.includes('image') || tool.includes('video') || tool.includes('animate')
    }
    return false
  })
}

type MsgFeedback = 'up' | 'down' | null

function readMsgFeedback(messageId: string): MsgFeedback {
  const v = readLocal(`comfyart.msgFeedback.${messageId}`)
  return v === 'up' || v === 'down' ? v : null
}

/** #360: quiet outline 👍/👎 under Done summary — never suggestion chips. */
function DoneFeedback({ messageId }: { messageId: string }) {
  const [value, setValue] = useState<MsgFeedback>(() => readMsgFeedback(messageId))
  const pick = (v: 'up' | 'down') => {
    const next: MsgFeedback = value === v ? null : v
    setValue(next)
    writeLocal(`comfyart.msgFeedback.${messageId}`, next ?? '')
  }
  return (
    <div className="ca-chat__feedback" data-value={value || undefined} data-testid="chat-done-feedback">
      <button
        type="button"
        className="ca-chat__fb"
        data-on={value === 'up' || undefined}
        aria-label={t('chatMessage.thumbsUp')}
        aria-pressed={value === 'up'}
        onClick={() => pick('up')}
      >
        <span className="ca-icon">{Icons.thumbsUp}</span>
      </button>
      <button
        type="button"
        className="ca-chat__fb"
        data-on={value === 'down' || undefined}
        aria-label={t('chatMessage.thumbsDown')}
        aria-pressed={value === 'down'}
        onClick={() => pick('down')}
      >
        <span className="ca-icon">{Icons.thumbsDown}</span>
      </button>
    </div>
  )
}

export function AssistantBlocks({ editor, m, dockAsks }: { editor: Editor; m: BotMessage; dockAsks?: boolean }) {
  const results = new Map(m.blocks.filter((b) => b.type === 'tool_result' && b.id).map((b) => [b.id, b]))
  const resultOf = (b: BotBlock, i: number) => (b.id ? results.get(b.id) : m.blocks[i + 1]?.type === 'tool_result' ? m.blocks[i + 1] : undefined)
  const isPlan = (b: BotBlock) => b.type === 'tool_use' && toolName(b.name) === 'update_plan'
  const plan = m.blocks.filter(isPlan).at(-1)
  const done = m.status !== 'streaming'
  const quiet = askQuiet(m) // #763: no 输出中… shell while a question is open / just answered or skipped
  const outputs = done ? outputsOf(m.blocks.filter((b) => b.type !== 'task')) : []
  const items: ReactNode[] = []
  let run: Pair[] = []
  let proc: ProcessStep[] = []
  const flush = (stopped = false) => {
    if (run.length > 1) items.push(<StepGroup key={`g${run[0].i}`} editor={editor} steps={run} stopped={stopped} />)
    else if (run.length) items.push(<Step key={run[0].i} editor={editor} use={run[0].use} result={run[0].result} thumbs={false} />)
    run = []
  }
  let genAt = -1
  let created: CreatedSkill[] = []
  const flushProc = () => {
    if (!proc.length) return
    const onlyThought = proc.every((s) => s.kind === 'thought')
    // #325 single Thought row stays on Thought tip specs (no rail)
    if (onlyThought && proc.length === 1) {
      const s = proc[0]
      items.push(<Thought key={s.key} text={s.text ?? ''} live={!!s.live} />)
    } else {
      items.push(<ProcessTimeline key={`pt${proc[0].key}`} steps={proc} />)
    }
    // #437: result images sit right under the rail that holds the generation (model-name) row
    if (genAt < 0 && proc.some((s) => s.kind === 'image' || s.kind === 'video')) genAt = items.length
    // #650 follow-up: the created-skill card sits right under the rail holding 「Skill Created」
    created.forEach((c) => items.push(<SkillCreatedCard key={`sc${c.id}`} skill={c} />))
    created = []
    proc = []
  }
  // #413: an in-loop memory add shows as the 记忆已更新 › row, not as a tool row
  const memBlocks = m.blocks.filter((b) => b.type === 'memory_updated')
  const memCalls = new Set(memBlocks.flatMap((b) => [b.tool_id, ...(b.tool_ids ?? [])]).filter(Boolean))
  // #423: at most one 记忆已更新 › row per turn; older saved turns with several blocks fold into the first
  const firstMem = memBlocks[0]
  const memIdsAll = [...new Set(memBlocks.flatMap((b) => b.memory_ids ?? []))]
  // #423: texts for 「已保存 N 条」 detail (deduped, order preserved)
  const memTextsAll = [...new Set(memBlocks.flatMap((b) => b.texts ?? []).filter(Boolean))]
  // #423: memory add never shows a raw tool row, incl. a no-op identical repeat (no 记忆已更新 › row either)
  const memAddIds = new Set(m.blocks.filter((b) => b.type === 'tool_use' && toolName(b.name) === 'memory' && (b.input as { action?: string } | undefined)?.action === 'add').map((b) => b.id))
  const hideMemCall = (b: BotBlock) => (b.type === 'tool_use' || b.type === 'tool_result') && toolName(b.name) === 'memory' && !!b.id
    && (memCalls.has(b.id) || memAddIds.has(b.id))
  let planShown = false
    // #627: thinking after an image/video gen row → ref_analysis (参考素材分析结束), not a second 思考完成
  let sawMediaGen = false
  m.blocks.forEach((b, i) => {
    // #763: ask_user never paints its own 向你提问 timeline row (the docked card is the status)
    if ((b.type === 'tool_use' || b.type === 'tool_result') && toolName(b.name) === 'ask_user') return
    if (hideMemCall(b)) {
      // #437: memory write in flight → 记忆更新中 (no ›); becomes 记忆已更新 › when memory_updated lands
      if (
        !done
        && b.type === 'tool_use'
        && (b.input as { action?: string } | undefined)?.action === 'add'
        && !!b.id
        && !memCalls.has(b.id)
        && !resultOf(b, i)
      ) {
        flush()
        proc.push({
          key: `p${i}-updating`,
          kind: 'memory_updating',
          label: processLabel('memory_updating', true),
          live: true,
        })
      }
      return
    }
    // #437: a finished turn has no 等待结果 row; model-name row → result images → text
    if (done && b.type === 'tool_use' && toolName(b.name) === 'wait_generation') return
    if (b.type === 'memory_updated' && b !== firstMem) return
    if (isPlan(b)) {
      if (planShown) return
      planShown = true
      flushProc()
      flush()
      items.push(<Plan key={`p${i}`} b={plan!} live={!done} />)
      return
    }
    // #326: process-eligible blocks join the rail (live + done); skip tool_result siblings
    // Resolve kind with result context (search_pages needs tool_result count)
    const result = b.type === 'tool_use' ? resultOf(b, i) : undefined
    const stepLiveProbe = !done && (
      i === m.blocks.length - 1
      || (b.type === 'tool_use' && !result && !m.blocks.slice(i + 1).some((x) => processKindOf(x)))
    )
    let kindResolved = processKindOf(b, { result, live: stepLiveProbe })
    // #627: post-image/video thinking paints as 参考素材分析结束 (live pin), never a visible second 思考完成
    if (kindResolved === 'thought' && b.type === 'thinking' && sawMediaGen) kindResolved = 'ref_analysis'
    if (kindResolved === 'image' || kindResolved === 'video') sawMediaGen = true
    if (kindResolved && (b.type === 'thinking' ? !!b.text?.trim() : true) && b.type !== 'tool_result') {
      // When done, process tool_use still rails (muted); do not also fold into StepGroup
      if (b.type === 'tool_use' || b.type === 'thinking' || b.type === 'memory_updated') {
        flush() // non-process tool run ends before process rail
        const stepLive = stepLiveProbe
        // Writing-code sub-steps: ensure a muted `code` header row precedes the first sub-kind
        if (CODE_SUB_KINDS.has(kindResolved) && !proc.some((s) => s.kind === 'code')) {
          proc.push({
            key: `p${i}-code`,
            kind: 'code',
            label: processLabel('code', false),
            live: false,
          })
        }
        if (kindResolved === 'skill_created') { const c = skillCreatedOf(b, result); if (c) created.push(c) }
        const pages = kindResolved === 'search_pages' ? searchResultCount(b, result) : undefined
        const model = (kindResolved === 'image' || kindResolved === 'video') ? processModelName(b.input) : undefined
        const aspectRatio = (kindResolved === 'image' || kindResolved === 'video') ? processAspectRatio(b.input) : undefined
        // #430: updating an existing entry shows 记忆已读取 (not clickable) right before 记忆已更新 ›
        if (b.type === 'memory_updated' && memBlocks.some((x) => (x.updated_ids ?? []).length > 0)) {
          proc.push({ key: `p${i}-read`, kind: 'memory_retrieved', label: processLabel('memory_retrieved', false), live: false })
        }
        // #421: a failed generate_* (or its wait_generation) must not read as the done/success row
        const ownState = result ? stepState(result) : undefined
        let waitFailed = false
        if ((kindResolved === 'image' || kindResolved === 'video') && b.type === 'tool_use' && ownState !== 'cancelled' && ownState !== 'error') {
          for (let j = i + 1; j < m.blocks.length; j++) {
            const nb = m.blocks[j]
            if (nb.type !== 'tool_use') continue
            const nn = toolName(nb.name)
            if (nn === 'wait_generation') {
              const wr = resultOf(nb, j)
              waitFailed = !!(wr && stepState(wr) === 'error')
              break
            }
            if (IMAGE_PROCESS_TOOLS.has(nn) || VIDEO_TOOLS.has(nn) || GEN_TOOLS.has(nn)) break
          }
        }
        const genFailed = ownState === 'error' || waitFailed
        const genCancelled = ownState === 'cancelled'
        proc.push({
          key: `p${i}`,
          kind: kindResolved,
          // #393 nit: a declined / refused paid step never reads as done
          // #421: failed generation reads as failed, not the success/model-name row
          // #420/#421: failed/cancelled tool_use on the rail reads 「工具名 · 失败/Failed」 (incl. canvas tools)
          label: b.type === 'tool_use' && (genCancelled || genFailed)
            && (kindResolved === 'image' || kindResolved === 'video' || kindResolved === 'tool')
            ? `${toolLabel(b.name)} · ${t(genCancelled ? 'chatMessage.cancelled' : 'chatMessage.failed')}`
            : processLabel(kindResolved, stepLive, {
              fallback: b.type === 'tool_use' ? toolLabel(b.name) : b.label,
              model,
              pages,
            }),
          live: stepLive,
          error: genFailed || undefined,
          text: b.type === 'thinking' ? b.text : undefined,
          aspectRatio,
          memoryIds: b.type === 'memory_updated' ? memIdsAll : undefined,
          memoryTexts: b.type === 'memory_updated' ? memTextsAll : undefined,
          favicon: kindResolved === 'search_pages' ? searchFavicon(result) : undefined,
        })
        return
      }
    }
    if (b.type === 'tool_use' && done) {
      flushProc()
      run.push({ use: b, result: resultOf(b, i), i })
      return
    }
    if (b.type !== 'tool_result') {
      // #348: streaming wait / emitting reply → Outputting… on the rail (Brain)
      if (!done && !quiet && proc.length && !proc.some((s) => s.live) && (b.type === 'text' || b.type === 'notice' || b.type === 'task')) {
        proc.push({
          key: `out${i}`,
          kind: 'outputting',
          label: processLabel('outputting', true),
          live: true,
        })
      }
      flushProc()
      flush(b.type === 'notice' && b.level === 'error') // turn ended in error / loop-guard stop: reuse the failed icon
      // #361: content refusal alternatives = plain Markdown <ul> in this text path —
      // NEVER suggestion chips / pill buttons / red toast as the primary refuse UI.
      if (b.type === 'text') items.push(<Markdown key={i} text={b.text ?? ''} />)
      if (b.type === 'tool_use') items.push(<Step key={i} editor={editor} use={b} result={resultOf(b, i)} />)
      if (b.type === 'retry') items.push(<Retry key={i} b={b} live={!done && !m.blocks.slice(i + 1).some((x) => x.type === 'retry')} />)
      if (b.type === 'ask' && !(dockAsks && isDockedQuestion(b))) items.push(renderAsk(b, b.ask_id ?? i))
      if (b.type === 'task') items.push(<Task key={i} editor={editor} b={b} />)
      if (b.type === 'run_stop') {
        // #492: skip reason=done in AssistantBlocks render (reloaded old chats included). latest-card scan unchanged.
        if ((b.stop?.reason ?? '') !== 'done') {
          items.push(<RunStop key={i} b={b} latest={!m.blocks.slice(i + 1).some((x) => x.type === 'run_stop')} />)
        }
      }
      if (b.type === 'notice') items.push(<div key={i} className="ca-chat__notice" data-level={b.level}>{b.text}</div>)
    }
  })
  // Streaming with process rail but no live row yet → Outputting… wait state
  if (!done && !quiet && proc.length && !proc.some((s) => s.live)) {
    proc.push({
      key: 'out-end',
      kind: 'outputting',
      label: processLabel('outputting', true),
      live: true,
    })
  }
  flushProc()
  flush()
  if (outputs.length) items.splice(genAt < 0 ? items.length : genAt, 0, <div key="results" className="ca-chat__thumbs ca-chat__results">{outputs.map((s) => <Thumb key={s} editor={editor} src={s} />)}</div>)
  // #360: under Done summary — thumbs only; NEVER a suggestion chip/pill row on media Done
  if (m.status === 'done' && isMediaDoneMessage(m)) {
    items.push(<DoneFeedback key="feedback" messageId={m.id} />)
  }
  return <>{items}</>
}

export function UserMessage({ editor, m, onBranch }: { editor: Editor; m: BotMessage; onBranch?: () => void }) {
  const text = textOf(m)
  const media = m.blocks.filter((b) => b.type === 'image' || b.type === 'video' || b.type === 'audio')
  const skills = m.blocks.filter((b) => b.type === 'skill')
  return (
    <div className="ca-chat__user" data-queued={m.status === 'queued' || undefined}>
      <div className="ca-chat__acts">
        <button type="button" className="ca-history__del" title={t('chatMessage.editAgain')} onClick={() => draftAtom.set(text)}>{Icons.textTool}</button>
        <CopyButton text={text} />
        <button type="button" className="ca-history__del" title={t('chatMessage.setAsScheduledTask')} onClick={() => schedulesOpenAtom.set({ prompt: text })}>{Icons.bell}</button>
        {onBranch && <button type="button" className="ca-history__del" title={t('chatMessage.forkNewChatFromHere')} onClick={onBranch}>{Icons.merge}</button>}
      </div>
      {media.length > 0 && <div className="ca-chat__thumbs">{media.map((b) => <Thumb key={b.url} editor={editor} src={b.url!} />)}</div>}
      {m.blocks.filter((b) => b.type === 'kit').map((b) => <span key={b.name} className="ca-chip"><span className="ca-icon">{Icons.assets}</span>{b.name}</span>)}
      {m.blocks.filter((b) => b.type === 'file').map((b) => <a key={b.url} className="ca-chip" href={b.url} target="_blank" rel="noreferrer"><span className="ca-icon">{Icons.page}</span>{b.name}</a>)}
      {/* #462: the skill chip sits inside the bubble, inline before the text, with the process-line skill icon */}
      {(text || skills.length > 0) && (
        <div className={skills.length > 0 ? 'ca-chat__bubble ca-chat__bubble--skill' : 'ca-chat__bubble'} data-testid="user-bubble">
          {skills.map((b) => <SkillChip key={b.name} name={b.name ?? ""} testId="user-skill-chip" />)}
          {skills.length > 0 ? <span className="ca-chat__text" data-testid="user-bubble-text">{text}</span> : text}
        </div>
      )}
      {m.status === 'queued' && <span className="ca-chat__hint">{t('chatMessage.queuedSendsAfterTheCurrent')}</span>}
    </div>
  )
}
