import { atom, createShapeId, type Editor, type TLImageShape, type TLShape } from 'tldraw'

import { agentModeAtom, draftAtom, extraRefsAtom, generateDirect, sendToAgent, type AgentMode } from '../agent'
import { refreshBot } from '../bot'
import { t } from '../i18n'
import { refFromUrl, refKind } from '../comfy'
import { editElements } from '../elements'
import { createGenerator } from '../generate'
import { placeMedia, toMedia, type ErrorSink } from '../jobs'
import { attachSkill, CREATE_ENTRY_CHIP_KEY, loadSkills, skillAtom, skillCreatorAtom, withPreset } from '../skills'
import { chatViewAtom } from '../ui/AgentPanel'
import { audioDialogAtom } from '../ui/AudioDialog'
import { enterMode } from '../ui/mode'
import { EDIT_SKILL_PARAM, startSkillEdit } from '../skillEdit'
import { AUDIO, AUDIO_SIZE } from '../shapes/EmbedShapes'
import { GENERATOR, type GeneratorShape } from '../shapes/GeneratorShape'

const KEYS = ['ask', 'mode', 'ref', 'skill', 'tool', 'createSkill', 'editSkill', 'preset']
const REF_LONG = 512
const GAP = 20

/** #537 / #496 / #540: home 「实用工具」→ canvas; toolbar opens the matching menu/panel (no auto-run). */
export type HomeToolId =
  | 'cutout' | 'extend' | 'upscale' | 'inpaint' | 'mockup'
  | 'quick' | 'erase' | 'crop' | 'expand' | 'adjust' | 'text' | 'angles' | 'vectorize' | 'move' | 'transform'
  | 'to3d' | 'lipsync' | 'motion' | 'audio'
export const HOME_TOOLS: HomeToolId[] = [
  'cutout', 'extend', 'upscale', 'inpaint', 'mockup',
  'quick', 'erase', 'crop', 'expand', 'adjust', 'text', 'angles', 'vectorize', 'move', 'transform',
  'to3d', 'lipsync', 'motion', 'audio',
]
/** #570: how each home tool lands on the canvas once the image is placed + selected (data, not per-id code):
 *  'menu' opens the tool's pinned bar popover (its own panel at the image's right when unpinned),
 *  'panel' opens the tool's own panel at the image's right, 'bar' swaps the image toolbar to the tool's own bar.
 *  Tools not listed only select (cutout / mockup / vectorize) or were already handled (crop, modes). ⋯ never auto-opens. */
export const HOME_LANDING: Record<string, 'menu' | 'panel' | 'bar'> = { upscale: 'panel', to3d: 'panel', transform: 'bar' }

export const homeToolAtom = atom<HomeToolId | null>('home tool', null)

async function placeRefs(editor: Editor, srcs: string[]): Promise<TLShape[]> {
  const visualSrcs = srcs.filter((src) => refKind(src) !== 'audio')
  if (!visualSrcs.length) return []
  const media = await Promise.all(visualSrcs.map((src) => toMedia(refFromUrl(src), refKind(src) === 'video' ? 'video' : 'image')))
  const sizes = media.map((m) => Math.min(1, REF_LONG / Math.max(m.w, m.h, 1)))
  const total = media.reduce((n, m, i) => n + m.w * sizes[i], 0) + GAP * (media.length - 1)
  const center = editor.getViewportPageBounds().center
  let x = center.x - total / 2
  return media.map((m, i) => {
    const w = m.w * sizes[i]
    const id = placeMedia(editor, m, m.ref.filename, x, center.y - m.h * sizes[i] / 2, w)
    x += w + GAP
    return editor.getShape(id)!
  })
}

function placeAudio(editor: Editor, src: string): TLShape {
  const id = createShapeId()
  const [w, h] = AUDIO_SIZE
  const center = editor.getViewportPageBounds().center
  editor.createShape({ id, type: AUDIO, x: center.x - w / 2, y: center.y - h / 2, props: { src, name: refFromUrl(src).filename } })
  return editor.getShape(id)!
}

function focusComposer() {
  // #491 (c): the full-screen switch re-mounts the layout and can leave focus on the view toggle; retry for a few frames
  let tries = 0
  const go = () => {
    document.querySelector<HTMLTextAreaElement>('.ca-composer__input')?.focus()
    const el = document.querySelector<HTMLTextAreaElement>('.ca-composer__input')
    if ((!el || document.activeElement !== el) && ++tries < 30) requestAnimationFrame(go)
    else if (tries < 30) setTimeout(() => { if (document.activeElement !== el) el?.focus() }, 150)
  }
  requestAnimationFrame(go)
}

function isHomeTool(tool: string | null): tool is HomeToolId {
  return !!tool && (HOME_TOOLS as string[]).includes(tool)
}

/** Place media, select it, and (for menu tools) stash which toolbar menu to open — never auto-run. */
const MODE_HOME_TOOLS = ['quick', 'erase', 'expand', 'adjust', 'text', 'angles', 'move', 'inpaint'] as const

async function openHomeTool(editor: Editor, tool: HomeToolId, refs: string[]) {
  if (tool === 'audio') {
    if (refs[0] && refKind(refs[0]) === 'audio') {
      const shape = placeAudio(editor, refs[0])
      editor.select(shape.id)
    }
    audioDialogAtom.set(true)
    return
  }
  if (tool === 'lipsync' || tool === 'motion') {
    const shapes = refs.length ? await placeRefs(editor, refs.slice(0, 1)) : []
    const src = shapes[0] ? (editor.getAsset((shapes[0] as TLImageShape).props.assetId!)?.props.src as string | undefined) : refs[0]
    const id = createGenerator(editor, true)
    const firstImage = src && refKind(src) === 'image' ? [src] : src ? [src] : []
    editor.updateShape<GeneratorShape>({
      id,
      type: GENERATOR,
      meta: { refs: firstImage, videoMode: tool, lastFrame: null, scenes: null },
    })
    editor.select(id)
    return
  }
  const shapes = await placeRefs(editor, refs.slice(0, 1))
  const shape = shapes[0]
  if (!shape) return
  editor.setCurrentTool('select')
  editor.select(shape.id)
  editor.zoomToSelectionIfOffscreen(64, { animation: { duration: 200 } })
  if ((MODE_HOME_TOOLS as readonly string[]).includes(tool)) {
    enterMode(tool as (typeof MODE_HOME_TOOLS)[number])
    return
  }
  if (tool === 'crop') {
    editor.setCroppingShape(shape.id)
    return
  }
  if (tool === 'cutout' || tool === 'mockup' || tool === 'vectorize') {
    // Toolbar buttons run on click — place+select only (mutation: no auto-run)
    return
  }
  // upscale / to3d / transform / extend — ImageToolbar / VideoToolbar open the menu/panel from the atom
  homeToolAtom.set(tool)
}

export async function takeHandoff(editor: Editor, onError: ErrorSink) {
  const url = new URL(location.href)
  const text = url.searchParams.get('ask')?.trim() ?? ''
  const mode = (url.searchParams.get('mode') ?? 'agent') as AgentMode
  const refs = url.searchParams.getAll('ref')
  const skillId = url.searchParams.get('skill')
  // #494-2: the skill dialog's preset — its prompt is appended after the skill's instructions for this run
  const presetId = url.searchParams.get('preset')
  const tool = url.searchParams.get('tool')
  const createSkill = url.searchParams.get('createSkill') === '1'
  const editSkill = url.searchParams.get(EDIT_SKILL_PARAM)
  if (!text && !refs.length && !skillId && !createSkill && !editSkill && !isHomeTool(tool) && tool !== 'elements') return
  for (const k of KEYS) url.searchParams.delete(k)
  history.replaceState(null, '', url)
  if (editSkill) {
    // #462 Edit in chat: one auto-sent turn in this fresh project; the composer stays empty with its normal placeholder
    const skill = (await loadSkills()).find((s) => s.custom && s.id === editSkill)
    if (!skill) return onError(t('skillsDialog.notFound', editSkill))
    agentModeAtom.set('agent')
    await refreshBot()
    return startSkillEdit(editor, skill, (text, s, context) => sendToAgent(editor, text, [], s, [], [], context))
  }
  if (createSkill) {
    // #491 / #542: both create entries (home 创建技能, Skills page 创建) land here identically: chat-only full screen
    // (chatView 'max'), the 技能创建器 chip, caret in the input. Nothing is sent; the user sends from the composer.
    chatViewAtom.set('max')
    agentModeAtom.set('agent')
    skillCreatorAtom.set({ on: true, chip: CREATE_ENTRY_CHIP_KEY })
    if (text) draftAtom.set(text)  // #542: an old ask= link keeps its text as a draft, never auto-sent
    if (refs.length) extraRefsAtom.set((await placeRefs(editor, refs)).map((s) => s.id))
    // #542 P1-1: wait for the provider list like every other agent handoff, so the mode pill shows the same product
    // label (Loomi) and the same collapsed reference button as the normal composer, whichever entry was used
    await refreshBot().catch(() => {})
    focusComposer()
    return
  }
  if (tool === 'elements') {
    const [shape] = await placeRefs(editor, refs.slice(0, 1))
    if (shape) editElements(editor, shape as TLImageShape, onError)
    return
  }
  if (isHomeTool(tool)) {
    await openHomeTool(editor, tool, refs)
    return
  }

  agentModeAtom.set(mode)
  const found = skillId ? (await loadSkills()).find((s) => s.id === skillId) ?? null : null
  const skill = found && withPreset(found, presetId)
  if (skill && !attachSkill(skill)) {  // #673: hidden skill from an old link — no chip, notice shown, nothing sent
    if (text) draftAtom.set(text)
    return
  }
  const shapes = await placeRefs(editor, refs)
  if (!text) {
    extraRefsAtom.set(shapes.map((s) => s.id))
    return
  }
  await refreshBot()
  if (mode !== 'agent') return generateDirect(editor, text, [{ refs: shapes as TLImageShape[], prompt: text }], mode === 'video', onError)
  skillAtom.set(null)
  await sendToAgent(editor, text, shapes as TLImageShape[], skill)
}

/** #286: the project couldn't be created on the canvas page, so the home draft would be lost. Put the prompt from
 *  the URL back into the canvas chat box (and its mode), drop the handoff params so nothing auto-sends, and report. */
export function restoreHandoff(onError: ErrorSink, message: string) {
  const url = new URL(location.href)
  const text = url.searchParams.get('ask')?.trim() ?? ''
  const mode = url.searchParams.get('mode') as AgentMode | null
  for (const k of KEYS) url.searchParams.delete(k)
  history.replaceState(null, '', url)
  if (mode) agentModeAtom.set(mode)
  if (text) draftAtom.set(text)
  onError(message)
}
