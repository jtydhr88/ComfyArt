import { atom, createShapeId, type Editor, type TLImageShape, type TLShape, type TLShapeId, type TLVideoShape } from 'tldraw'

import { commentTarget } from './actions'
import { botEnabledAtom, logDirect, sendMessage, settingsAtom, type BotBlock } from './bot'
import { capRefs, createGenerator, generate, genInfoOf, nearestRatio } from './generate'
import { DURATIONS, VIDEO_RATIOS } from './genOptions'
import { uploadImage, viewUrl, type RefKind } from './comfy'
import { fileSrc, placeMedia, toMedia, type ErrorSink } from './jobs'
import { describeItem, itemImages, linkedKit, type LibraryItem } from './library'
import { ask, ocrLines, parseJson, transcribeFile } from './llm'
import { AUDIO, AUDIO_SIZE, type AudioShape } from './shapes/EmbedShapes'
import { refFrameContents, refFrameOf, refLinkedOf } from './chatFrame'
import { memoryPrompt } from './memory'
import { formatCanvasSnapshot, packUnifiedContext, type SnapshotNode } from './canvasSnapshot'
import { OWNER_DEFAULT, WORKSPACE_DEFAULT } from './memoryStore'
import { directSettings, modelOf } from './models'
import { COMMENT, type CommentShape } from './shapes/CommentShape'
import { GENERATOR, type GeneratorShape } from './shapes/GeneratorShape'
import { blockHiddenSkill, type Skill } from './skills'
import { t } from './i18n'

export type AgentMode = 'agent' | 'image' | 'video'

export const draftAtom = atom('agent draft', '')
export const extraRefsAtom = atom<TLShapeId[]>('agent refs', [])
/** #644: composer-only reference images (no canvas shape) — an old hidden-skill ?skill= link restores its refs here. */
export interface LooseRef { src: string; name: string }
export const looseRefsAtom = atom<LooseRef[]>('composer loose refs', [])
export const agentModeAtom = atom<AgentMode>('agent mode', 'agent')
export const kitsAtom = atom<LibraryItem[]>('agent kits', [])

export type RefShape = TLImageShape | TLVideoShape | AudioShape
export interface ChatDoc { src: string; name: string }

export const docsAtom = atom<ChatDoc[]>('agent docs', [])
export const DOC_ACCEPT = '.pdf,.docx,.md,.markdown,.txt,.json'
export const isRefShape = (s: TLShape): s is RefShape => s.type === 'image' || s.type === 'video' || s.type === AUDIO

export const srcOf = (editor: Editor, shape: RefShape): string | null => fileSrc(editor, shape)

export function refKindOf(shape: RefShape): RefKind {
  return shape.type === AUDIO ? 'audio' : shape.type
}

function mediaName(editor: Editor, shape: RefShape): string {
  if (shape.type === AUDIO) return shape.props.name
  const asset = shape.props.assetId ? editor.getAsset(shape.props.assetId) : null
  return (asset?.type === shape.type && asset.props.name) || ''
}

const REF_LONG = 512
const isDoc = (f: File) => DOC_ACCEPT.split(',').some((ext) => f.name.toLowerCase().endsWith(ext))

export async function uploadRefs(editor: Editor, files: File[]) {
  for (const f of files) {
    const kind = f.type.startsWith('video/') ? 'video' : f.type.startsWith('image/') ? 'image' : f.type.startsWith('audio/') ? 'audio' : null
    if (!kind && !isDoc(f)) continue
    const ref = await uploadImage(f, f.name)
    if (!kind) {
      docsAtom.set([...docsAtom.get(), { src: viewUrl(ref), name: f.name }])
      continue
    }
    const center = editor.getViewportPageBounds().center
    let id: TLShapeId
    if (kind === 'audio') {
      id = createShapeId()
      editor.createShape({ id, type: AUDIO, x: center.x - AUDIO_SIZE[0] / 2, y: center.y - AUDIO_SIZE[1] / 2, props: { src: viewUrl(ref), name: f.name } })
    } else {
      const m = await toMedia(ref, kind)
      const w = Math.min(m.w, REF_LONG)
      id = placeMedia(editor, m, f.name, center.x - w / 2, center.y - w * m.h / m.w / 2, w)
    }
    extraRefsAtom.set([...extraRefsAtom.get().filter((x) => x !== id), id])
  }
}


/** #384: compact per-turn canvas snapshot for the agent request body (shares #382 budget). */
export function canvasNodesFromEditor(editor: Editor): { nodes: SnapshotNode[]; selection: string[] } {
  const ids = [...editor.getCurrentPageShapeIds()]
  const selection = [...editor.getSelectedShapeIds()].map(String)
  const nodes: SnapshotNode[] = []
  for (const id of ids) {
    const shape = editor.getShape(id)
    if (!shape || shape.type === COMMENT) continue
    const gen = genInfoOf(shape)
    const workflow = gen?.workflow
      || (shape.type === GENERATOR ? (shape as GeneratorShape).props.workflow : undefined)
    const model = workflow ? (modelOf(workflow)?.label || workflow) : undefined
    let name: string | undefined
    if (shape.type === 'frame') name = (shape as { props: { name?: string } }).props.name
    else if ('props' in shape && typeof (shape as { props: { text?: string } }).props.text === 'string') {
      name = (shape as { props: { text: string } }).props.text.slice(0, 80)
    }
    nodes.push({ id: String(shape.id), type: String(shape.type), ...(name ? { name } : {}), ...(model ? { model } : {}) })
  }
  return { nodes, selection }
}

export async function sendToAgent(editor: Editor, text: string, refs: RefShape[], skill: Skill | null, kits: LibraryItem[] = [], docs: ChatDoc[] = [], context = '', opts?: { runMode?: 'interactive' | 'unattended'; chip?: string; loose?: LooseRef[] }) {
  // #673 safety net: a hidden (deferred) skill never starts a run — no request at all; the composer shows the notice.
  if (blockHiddenSkill(skill)) return
  const linked = linkedKit(editor.getDocumentSettings().meta.brandKit)
  if (linked && !kits.some((k) => k.id === linked.id)) kits = [...kits, linked]
  const frame = refLinkedOf(editor) ? refFrameOf(editor) : null
  if (frame) {
    const { media, notes } = refFrameContents(editor, frame)
    const extra = media.filter((s): s is RefShape => isRefShape(s) && !refs.some((r) => r.id === s.id))
    const first = refs.length + 1
    const last = refs.length + extra.length
    const items = extra.length ? ` Attached ${first === last ? `item ${first} comes` : `items ${first}-${last} come`} from it.` : ''
    const said = notes.length ? ` Notes in it: ${notes.map((n) => `"${n}"`).join('; ')}.` : ''
    if (items || said) context = [context, `[Linked reference frame "${frame.props.name}" (${frame.id}): follow it as the reference for this work.${items}${said}]`].filter(Boolean).join('\n')
    refs = [...refs, ...extra]
  }
  const sent = await Promise.all(refs.map(async (r) => {
    const src = srcOf(editor, r)
    if (!src) return []
    const kind = refKindOf(r)
    const transcript = kind === 'audio' ? await transcribeFile(src).catch(() => '') : ''
    return [{ id: r.id, src, name: mediaName(editor, r), kind, ...(transcript ? { transcript } : {}) }]
  }))
  const loose = (opts?.loose ?? []).map((l, i) => ({ id: `loose:${i}` as TLShapeId, src: l.src, name: l.name, kind: 'image' as const }))
  if (loose.length) sent.push(loose)
  const mem = settingsAtom.get()['memory-enabled'] === false ? '' : memoryPrompt(text)
  // #384: every turn attaches a fresh canvas snapshot; pack against the shared #382 window budget.
  const { nodes, selection } = canvasNodesFromEditor(editor)
  const snap = formatCanvasSnapshot({
    nodes,
    selection,
    owner_id: OWNER_DEFAULT,
    workspace_id: WORKSPACE_DEFAULT,
    project_id: String(editor.getDocumentSettings().meta?.projectId || 'local'),
  })
  const packed = packUnifiedContext({
    memoryPrompt: mem,
    snapshot: snap.text,
    text,
    imageCount: refs.length + loose.length,
  })
  const ctx = [packed.snapshot, context].filter(Boolean).join('\n')
  await sendMessage({
    text,
    refs: sent.flat(),
    docs,
    kits: kits.map((k) => ({ name: k.name, description: describeItem(k), images: itemImages(k) })),
    ...(skill ? { skill: skill.name } : {}),
    memory: packed.memoryPrompt,
    ...(ctx ? { context: ctx } : {}),
    ...(opts?.runMode ? { run_mode: opts.runMode } : {}),
    ...(opts?.chip ? { chip: opts.chip } : {}),
  })
}

export function commentNotes(editor: Editor, comments: CommentShape[]) {
  const images: TLImageShape[] = []
  const lines = comments.map((c) => {
    const text = `- ${c.props.text.trim()}`
    const target = commentTarget(editor, c)
    if (!target) return text
    if (!images.some((s) => s.id === target.shape.id)) images.push(target.shape)
    const r = target.region
    return `${text} [on ${target.shape.id}, region x=${Math.round(r.x)} y=${Math.round(r.y)} w=${Math.round(r.w)} h=${Math.round(r.h)} of ${target.src.w}×${target.src.h} px]`
  })
  return { text: lines.join('\n'), images }
}

export function commentsToChat(editor: Editor, comments: CommentShape[]) {
  const { text, images } = commentNotes(editor, comments)
  draftAtom.set([draftAtom.get(), text].filter(Boolean).join('\n'))
  extraRefsAtom.set([...new Set([...extraRefsAtom.get(), ...images.map((s) => s.id)])])
}

export type { DirectSettings } from './models'

export interface DirectRun { refs: RefShape[]; prompt: string; near?: TLShapeId; loose?: string[] }

const RESULT_GAP = 40

function startDirect(editor: Editor, run: DirectRun, video: boolean, onError: ErrorSink): BotBlock {
  const refs = run.refs.filter((r): r is TLImageShape => r.type === 'image')
  const settings = directSettings(video ? 'video' : 'image')
  const picked = settings.ratio ?? (video ? VIDEO_RATIOS[0] : '1:1')
  const ratio = video && refs[0] ? nearestRatio(refs[0].props.w / refs[0].props.h, VIDEO_RATIOS) : picked
  const media = video && run.refs.some((r) => r.type !== 'image')
  const own = run.refs.flatMap((r) => srcOf(editor, r) ?? [])
  const srcs = media ? capRefs([...own, ...(run.loose ?? [])]) : [...refs.flatMap((r) => srcOf(editor, r) ?? []), ...(run.loose ?? [])].slice(0, video ? 1 : undefined)
  const near = run.near && editor.getShapePageBounds(run.near)
  const holder = createGenerator(editor, video, { ...settings, prompt: run.prompt, ratio }, false, near ? [near.x, near.maxY + RESULT_GAP] : undefined)
  if (srcs.length) editor.updateShape<GeneratorShape>({ id: holder, type: GENERATOR, meta: { refs: srcs, ...(media ? { videoMode: 'refs' } : {}) } })
  void generate(editor, editor.getShape<GeneratorShape>(holder)!, onError)
  const model = modelOf(editor.getShape<GeneratorShape>(holder)!.props.workflow)?.label
  return {
    type: 'task',
    label: t('agent.directLabel', video ? t('dock.videoGeneration') : t('dock.imageGeneration'), ratio),
    holder,
    detail: { tool: video ? 'generate_video' : 'generate_image', prompt: run.prompt, ...(model ? { model } : {}), params: { aspect_ratio: ratio, ...(srcs.length ? { references: srcs.length } : {}) } },
  }
}

export function eachRuns(refs: RefShape[], targets: RefShape[], promptFor: (runRefs: RefShape[]) => string): DirectRun[] {
  if (!targets.length) return [{ refs, prompt: promptFor(refs) }]
  return targets.map((target) => {
    const runRefs = refs.filter((r) => r === target || !targets.includes(r))
    return { refs: runRefs, prompt: promptFor(runRefs), near: target.id }
  })
}

export async function generateDirect(editor: Editor, text: string, runs: DirectRun[], video: boolean, onError: ErrorSink) {
  const blocks = runs.map((run) => startDirect(editor, run, video, onError))
  if (botEnabledAtom.get()) await logDirect(text, blocks)
}

export function eachLine(refs: RefShape[], targets: RefShape[]): string {
  const n = (list: RefShape[]) => list.map((r) => refs.indexOf(r) + 1).join(', ')
  const shared = refs.filter((r) => !targets.includes(r))
  return `[Do this separately for each of attached items ${n(targets)}: one result per item, placed next to it${shared.length ? `, reusing attached items ${n(shared)} in every result` : ''}.]`
}

const STORY_SYSTEM = `Split a video idea into a storyboard. Reply with ONE JSON object and nothing else: {"scenes": [{"prompt": "<detailed English shot description with camera motion and sound>", "duration": ${DURATIONS.join('|')}}]}. Use as many scenes as the idea needs and keep characters and style consistent.`

export async function planStoryboard(idea: string): Promise<{ prompt: string; duration: number }[]> {
  const scenes = parseJson(await ask(idea, STORY_SYSTEM, []))?.scenes
  if (!Array.isArray(scenes)) throw new Error(t('agent.smartStoryboardFailedPleaseTry'))
  return scenes.filter((s) => s?.prompt).map((s) => ({ prompt: String(s.prompt), duration: DURATIONS.includes(Number(s.duration)) ? Number(s.duration) : DURATIONS[0] }))
}

export async function extractText(editor: Editor, shape: TLImageShape): Promise<string> {
  const src = srcOf(editor, shape)
  if (!src) return ''
  return (await ocrLines(src)).join('\n')
}
