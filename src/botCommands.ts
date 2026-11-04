import { agentError, agentErrorText } from './wsErrors'
import { react, type Editor, type TLImageShape, type TLShapeId, type TLVideoShape } from 'tldraw'

import * as actions from './actions'
import { generateAudio, imageTo3d, musicModels, viewsTo3d, voices } from './assetGen'
import { clampMusicSeconds, musicMissing } from './music'
import { editElements } from './elements'
import { bakeToImage, createMockup } from './mockup'
import { api, popAgentCommand, pushAgentCommand } from './comfy'
import { LAYOUT_HANDLERS, shapeOf, type Args, type Handler } from './botLayout'
import { placeInChatFrame } from './chatFrame'
import { capRefs, createGenerator, generate } from './generate'
import { durationNote, fitDuration, RATIOS, VIDEO_RATIOS, videoResolution } from './genOptions'
import { tl } from './i18n'
import { VIDEO_TARGETS } from './videoGraphs'
import { type ErrorSink, errorText, fileSrc, GAP, resultsAtom, whenSubmitted } from './jobs'
import { agentModels } from './models'
import { modesFor } from './refModes'
import { AUDIO } from './shapes/EmbedShapes'
import { GENERATOR, type GeneratorShape } from './shapes/GeneratorShape'
import { MOCKUP, type MockupShape } from './shapes/MockupShape'
import { vectorize } from './vectorize'
import type { Edit, TransitionType } from './videoEdit'
import type { Crop } from './workflows'
import { CLIENT_ID, onComfyEvent, onReconnect } from './ws'
import { setPendingModel } from './wavespeed'
import { CUSTOM_MODEL3D, customWorkflowCommand } from './customWorkflows'

const AUDIO_MAX_SECONDS = 1000

/** Tool result when the user declines the cost confirm. Agent must reply as normal chat text (#127). */
const COST_DECLINED = {
  cancelled: true,
  status: 'declined',
  note:
    '已取消该生成，未扣费 / Cancelled this generation; nothing was charged. '
    + 'Reply to the user with that message in a normal chat message (not as an error or notice), '
    + 'then ask how they want to adjust. Do not retry, resubmit, or change model/params for this plan item in this turn.',
} as const

async function awaitSubmit(holderId: string) {
  const gate = whenSubmitted(holderId)
  if (!gate) return 'ok' as const
  return gate
}

function imageOf(editor: Editor, id: unknown): TLImageShape {
  const shape = shapeOf(editor, id)
  if (shape.type !== 'image') throw new Error(`${shape.id} is a ${shape.type}, not an image`)
  return shape as TLImageShape
}

function videoOf(editor: Editor, id: unknown): TLVideoShape {
  const shape = shapeOf(editor, id)
  if (shape.type !== 'video') throw new Error(`${shape.id} is a ${shape.type}, not a video`)
  return shape as TLVideoShape
}

function regionOf(args: Args): Crop {
  const r = { x: Number(args.x) || 0, y: Number(args.y) || 0, w: Number(args.width), h: Number(args.height) }
  if (!(r.w > 0 && r.h > 0)) throw new Error('width and height must be positive image pixels')
  return r
}

function place(editor: Editor, id: TLShapeId, args: Args, chat: string) {
  const shape = editor.getShape(id)!
  if (args.frame) {
    const frame = shapeOf(editor, args.frame)
    if (frame.type !== 'frame') throw new Error(`${frame.id} is not a frame`)
    editor.reparentShapes([id], frame.id)
    editor.updateShape({ id, type: shape.type, x: GAP, y: GAP })
  } else if (args.near) {
    const b = editor.getShapePageBounds(shapeOf(editor, args.near))!
    editor.updateShape({ id, type: shape.type, x: b.maxX + GAP, y: b.y })
  } else if (chat) {
    placeInChatFrame(editor, id, chat)
  }
}

async function toChat(editor: Editor, chat: string, holder: TLShapeId | undefined) {
  const result = await started(editor, holder)
  if (chat && result && 'ids' in result) placeInChatFrame(editor, holder!, chat)
  return result
}

function refUrls(editor: Editor, refs: unknown): string[] {
  if (!Array.isArray(refs)) return []
  return refs.map((r) => {
    if (typeof r === 'string' && /^(\/|https?:)/.test(r)) return r
    const src = fileSrc(editor, shapeOf(editor, r))
    if (!src) throw new Error(`${r} has no image`)
    return src
  })
}

function editOf(editor: Editor, args: Args): Edit {
  if (!Array.isArray(args.clips) || !args.clips.length) throw new Error('clips: give at least one {id, start, end}')
  const clips = args.clips.map((c: Args) => {
    const src = fileSrc(editor, videoOf(editor, c.id))
    if (!src) throw new Error(`${c.id} has no video file`)
    const start = Number(c.start) || 0
    const end = Number(c.end)
    if (!(end > start)) throw new Error(`clip ${c.id}: end must be after start (seconds in the source video)`)
    return { src, start, end, speed: Number(c.speed) || 1, volume: c.volume == null ? 1 : Number(c.volume) }
  })
  const types: TransitionType[] = ['none', 'fade', 'black', 'white']
  const transitions = clips.slice(1).map((_, i) => {
    const tr = Array.isArray(args.transitions) ? args.transitions[i] : null
    if (tr && !types.includes(tr.type)) throw new Error(`transition type must be one of ${types.join(', ')}`)
    return { type: (tr?.type ?? 'none') as TransitionType, duration: Number(tr?.duration) || 0.5 }
  })
  let music: Edit['music'] = null
  if (args.music) {
    const shape = shapeOf(editor, args.music.id)
    if (shape.type !== AUDIO) throw new Error(`${shape.id} is a ${shape.type}, not an audio element`)
    const src = fileSrc(editor, shape)!
    music = { src, name: String((shape.props as { name?: string }).name ?? ''), start: Number(args.music.start) || 0, volume: args.music.volume == null ? 1 : Number(args.music.volume) }
  }
  const subtitles = (Array.isArray(args.captions) ? args.captions : []).map((c: Args, i: number) => ({
    id: `c${i}`, text: String(c.text), start: Number(c.start) || 0, end: Number(c.end), size: Number(c.size) || 56, color: String(c.color ?? '#FFFFFF'),
  }))
  return { clips, transitions, subtitles, music }
}

async function startGenerator(editor: Editor, video: boolean, args: Args, onError: ErrorSink, chat: string) {
  const models = agentModels(video)
  const wantsRefs = !video && Array.isArray(args.refs) && args.refs.length > 0
  // #133: an Auto pick the user disabled in model prefs falls back to the default (result.model says which ran)
  const model = args.model ? models.find((m) => m.id === args.model) ?? (args.auto_model ? models[0] : undefined) : (wantsRefs && models.find((m) => m.refs)) || models[0]
  if (!models.length) throw new Error(`no ${video ? 'video' : 'image'} models loaded yet (WaveSpeed model list unavailable); try again shortly`)
  if (!model) throw new Error(`unknown model ${JSON.stringify(args.model)}; valid ${video ? 'video' : 'image'} ids: ${models.map((m) => m.id).join(', ')} (default ${models[0].id})`)
  const modes = Array.isArray(args.ref_modes) ? args.ref_modes.map(String) : []
  const allowed = modesFor(model).map((m) => m.id)
  const bad = modes.find((m: string) => m && !allowed.includes(m))
  if (bad) throw new Error(`${model.label} has no ref mode ${JSON.stringify(bad)}; it supports ${allowed.join(', ') || 'none'}`)
  if (wantsRefs && !model.refs && !(model.control && args.refs.every((_: unknown, i: number) => modes[i]))) throw new Error(`${model.label} does not accept refs; use a model with accepts_refs from list_models, give every ref a structure ref_mode, or drop refs`)
  const ratios = video ? VIDEO_RATIOS : RATIOS
  if (args.ratio && !ratios.includes(args.ratio)) throw new Error(`ratio must be one of ${ratios.join(', ')}`)
  // #128: round the asked seconds up to the model's next allowed duration (capped at its longest) and say so
  const lengths = model.durations?.map(Number)
  const duration = fitDuration(args.duration, lengths)
  const notes = video ? { zh: durationNote(args.duration, duration, lengths, (k, ...a) => tl('zh', k, ...a)), en: durationNote(args.duration, duration, lengths, (k, ...a) => tl('en', k, ...a)) } : null
  const props = video
    ? { prompt: String(args.prompt), workflow: model.id, ratio: args.ratio ?? ratios[0], duration, resolution: videoResolution(args.resolution == null ? '' : String(args.resolution), model.resolutions, model.defaults?.resolution) }
    : { prompt: String(args.prompt), workflow: model.id, ratio: args.ratio ?? '1:1', count: Math.min(4, Math.max(1, Number(args.count) || 1)) }
  const media = video ? [...refUrls(editor, args.reference_images), ...refUrls(editor, args.reference_videos), ...refUrls(editor, args.reference_audios)] : []
  const motion = video && args.motion_video ? refUrls(editor, [args.motion_video])[0] : null
  const speech = video && args.speech_audio ? refUrls(editor, [args.speech_audio])[0] : null
  if ((motion || speech) && !args.first_frame) throw new Error(`${motion ? 'motion_video' : 'speech_audio'} needs first_frame: the image of the person`)
  const mode = motion ? 'motion' : speech ? 'lipsync' : media.length ? 'refs' : null
  const refs = !video ? refUrls(editor, args.refs) : mode === 'refs' ? capRefs(media) : refUrls(editor, args.first_frame ? [args.first_frame] : [])
  const meta = {
    quiet: true,
    ...(mode ? { videoMode: mode } : {}),
    ...(motion ? { motion } : {}),
    ...(speech ? { speech } : {}),
    ...(refs.length ? { refs } : {}),
    ...(!video && modes.length ? { refModes: Object.fromEntries(refs.flatMap((src, i) => (modes[i] ? [[src, modes[i]]] : []))) } : {}),
    // #133 Auto: 2+ refs run on the multi-reference edit model the backend picked (edit_model)
    ...(!video && typeof args.edit_model === 'string' ? { featureModels: { image_edit: args.edit_model } } : {}),
    // #708: a skill-pinned edit model's tier (e.g. pose-fission → nano-banana-pro/edit at 2k)
    ...(!video && typeof args.edit_resolution === 'string' ? { editResolution: args.edit_resolution } : {}),
    ...(!video && args.base ? { base: refUrls(editor, [args.base])[0], strength: Number(args.base_strength) || 60 } : {}),
    ...(video && !mode && args.last_frame ? { lastFrame: refUrls(editor, [args.last_frame])[0] } : {}),
    ...(notes?.en ? { durationAsked: Number(args.duration) } : {}),
  }
  const id = createGenerator(editor, video, props, false)
  editor.updateShape<GeneratorShape>({ id, type: GENERATOR, meta })
  place(editor, id, args, chat)
  void generate(editor, editor.getShape<GeneratorShape>(id)!, onError)
  const outcome = await awaitSubmit(id)
  if (outcome === 'declined') return { ...COST_DECLINED }
  if (outcome === 'error') {
    const err = resultsAtom.get()[id]?.error
    throw new Error(err ? agentErrorText(err) : 'generation submit failed')
  }
  if (notes?.en) return { ids: [id], model: model.id, duration, duration_note: notes, note: `call wait_generation with these ids; the video is ${duration}s, not the ${args.duration}s asked: tell the user (duration_note, in their language)` }
  return { ids: [id], model: model.id, ...(video ? { duration } : {}), note: 'call wait_generation with these ids' }
}

async function started(editor: Editor, holder: TLShapeId | undefined) {
  if (!holder) throw new Error('that shape has no source media to work on')
  const shape = editor.getShape(holder)!
  editor.updateShape({ id: holder, type: shape.type, meta: { ...shape.meta, quiet: true } })
  const outcome = await awaitSubmit(holder)
  if (outcome === 'declined') return { ...COST_DECLINED }
  if (outcome === 'error') {
    const err = resultsAtom.get()[holder]?.error
    throw new Error(err ? agentErrorText(err) : 'generation submit failed')
  }
  return { ids: [holder], note: 'call wait_generation with these ids' }
}

function shapesWithSrc(editor: Editor, srcs: string[]): string[] {
  const all = editor.store.query.records('shape').get()
  return srcs.flatMap((src) => all.filter((s) => fileSrc(editor, s) === src).map((s) => s.id))
}

function waitResults(editor: Editor, ids: string[], timeout: number) {
  const unknown = new Set(ids.filter((id) => !resultsAtom.get()[id] && !editor.getShape(id as TLShapeId)))
  const settle = () => {
    const results = resultsAtom.get()
    return ids.map((id) => {
      const r = results[id]
      if (!r) return { id, status: unknown.has(id) ? 'unknown id' : 'running' }
      if (!r.error) return { id, status: 'done', urls: r.srcs, shapes: shapesWithSrc(editor, r.srcs) }
      // Intentional cost-confirm cancel is not a failure (#127).
      if (/已取消该生成，未扣费|Cancelled this generation; nothing was charged|已取消：未确认费用|Cancelled: cost not confirmed/.test(r.error)) {
        return { id, status: 'declined', cancelled: true, error: r.error }
      }
      return { id, status: 'error', ...agentError(r.error) }
    })
  }
  return new Promise<object>((resolve) => {
    let stop = () => { }
    let done = false
    const finish = () => {
      if (done) return
      done = true
      clearTimeout(timer)
      stop()
      const results = settle()
      resolve({ status: results.some((r) => r.status === 'running') ? 'running' : 'done', results })
    }
    const timer = setTimeout(finish, timeout * 1000)
    stop = react('wait generation', () => {
      if (settle().every((r) => r.status !== 'running')) queueMicrotask(finish)
    })
  })
}

const HANDLERS: Record<string, Handler> = {
  ...LAYOUT_HANDLERS,
  // list_models is answered by the backend (api/mcp_tools/canvas.py _list_models: paged, under the 4000-char cap);
  // the MCP tool never reaches the page, so there is no frontend handler (#95).
  generate_image: (editor, args, onError, chat) => startGenerator(editor, false, args, onError, chat),
  generate_video: (editor, args, onError, chat) => startGenerator(editor, true, args, onError, chat),
  edit_video: (editor, args, onError) => {
    const edit = editOf(editor, args)
    return started(editor, actions.editVideo(editor, videoOf(editor, args.clips[0].id), edit, onError))
  },
  edit_image: (editor, args, onError) => started(editor, actions.quickEdit(editor, imageOf(editor, args.id), String(args.prompt), onError)),
  animate_image: (editor, args, onError) => started(editor, actions.animate(editor, imageOf(editor, args.id), String(args.prompt), onError, args.loop !== false)),
  upscale_image: (editor, args, onError) => {
    const factor = args.factor === 4 ? 4 : 2
    const shape = imageOf(editor, args.id)
    return started(editor, args.creative ? actions.creativeUpscale(editor, shape, factor, String(args.style ?? ''), 0.3, onError) : actions.upscale(editor, shape, factor, onError))
  },
  remove_background: (editor, args, onError) => started(editor, actions.cutout(editor, imageOf(editor, args.id), onError)),
  expand_image: (editor, args, onError) => started(editor, actions.expand(editor, imageOf(editor, args.id),
    { l: Number(args.left) || 0, t: Number(args.top) || 0, r: Number(args.right) || 0, b: Number(args.bottom) || 0 }, String(args.prompt ?? ''), onError)),
  split_layers: (editor, args, onError) => started(editor, actions.splitLayers(editor, imageOf(editor, args.id), Number(args.layers) || 4, String(args.prompt ?? ''), onError)),
  change_angle: (editor, args, onError) => started(editor, actions.angles(editor, imageOf(editor, args.id), Number(args.horizontal) || 0, Number(args.vertical) || 0, Number(args.zoom ?? 5), onError)),
  replace_text: (editor, args, onError) => started(editor, actions.editText(editor, imageOf(editor, args.id), [[String(args.from), String(args.to)]], onError)),
  edit_region: (editor, args, onError) => started(editor, actions.editRegion(editor, imageOf(editor, args.id), regionOf(args), String(args.prompt), onError)),
  erase_region: (editor, args, onError) => started(editor, actions.eraseRegion(editor, imageOf(editor, args.id), regionOf(args), onError)),
  move_object: (editor, args, onError) => {
    if (!args.object && (args.x == null || args.y == null)) throw new Error('give object (what to move) or x/y (a point on it, image pixels)')
    const target = args.object ? { text: String(args.object) } : { x: Number(args.x), y: Number(args.y) }
    return started(editor, actions.moveTarget(editor, imageOf(editor, args.id), target, Number(args.dx) || 0, Number(args.dy) || 0, onError))
  },
  style_transfer: (editor, args, onError) => started(editor, actions.styleTransfer(editor, imageOf(editor, args.id), String(args.style ?? ''), args.ref ? refUrls(editor, [args.ref])[0] : null, onError)),
  vectorize_image: async (editor, args) => ({ id: await vectorize(editor, imageOf(editor, args.id)) }),
  extend_video: (editor, args, onError) => started(editor, actions.extendVideo(editor, videoOf(editor, args.id), String(args.prompt), fitDuration(args.duration), onError)),
  upscale_video: (editor, args, onError) => {
    const long = (VIDEO_TARGETS.find(([label]) => label === args.target) ?? VIDEO_TARGETS[0])[1]
    return started(editor, actions.upscaleVideo(editor, videoOf(editor, args.id), long, onError))
  },
  remove_video_background: (editor, args, onError) => started(editor, actions.cutoutVideo(editor, videoOf(editor, args.id), onError)),
  generate_music: (editor, args, onError, chat) => {
    const model = args.model ? musicModels().find((m) => m.id === args.model) : musicModels()[0]
    if (!model) throw new Error(`unknown music model ${JSON.stringify(args.model)} — see list_models`)
    const missing = musicMissing({ prompt: String(args.prompt ?? ''), lyrics: String(args.lyrics ?? '') })
    if (missing) throw new Error(missing === 'prompt' ? 'prompt (music style) is required' : 'lyrics are required')
    return toChat(editor, chat, generateAudio(editor, {
      kind: 'music', model: model.id, prompt: String(args.prompt).trim(), lyrics: String(args.lyrics ?? ''), seconds: clampMusicSeconds(model.id, Math.max(1, Number(args.duration) || 30)), ...(args.seed != null && Number.isFinite(Number(args.seed)) ? { seed: Number(args.seed) } : {}),
      ...(args.bpm ? { bpm: Number(args.bpm) } : {}), ...(args.language ? { language: String(args.language) } : {}), ...(args.key ? { key: String(args.key) } : {}),
    }, onError, true))
  },
  generate_sound_effect: (editor, args, onError, chat) => toChat(editor, chat, generateAudio(editor, { kind: 'sfx', prompt: String(args.prompt), seconds: Math.min(AUDIO_MAX_SECONDS, Math.max(1, Number(args.duration) || 8)) }, onError, true)),
  text_to_speech: (editor, args, onError, chat) => {
    if (args.reference) {
      const shape = shapeOf(editor, args.reference)
      if (shape.type !== AUDIO) throw new Error(`${shape.id} is not an audio shape`)
      return toChat(editor, chat, generateAudio(editor, { kind: 'clone', text: String(args.text), reference: fileSrc(editor, shape)! }, onError, true))
    }
    if (args.voice && !voices().includes(args.voice)) throw new Error(`voice must be one of ${voices().join(', ')}`)
    return toChat(editor, chat, generateAudio(editor, { kind: 'speech', text: String(args.text), voice: args.voice ?? voices()[0] }, onError, true))
  },
  edit_elements: (editor, args, onError) => started(editor, editElements(editor, imageOf(editor, args.id), onError)),
  create_mockup: (editor, args, onError) => started(editor, createMockup(editor, imageOf(editor, args.id), onError)),
  place_design: async (editor, args) => {
    const shape = shapeOf(editor, args.id)
    if (shape.type !== MOCKUP) throw new Error(`${shape.id} is not a mockup — make one with create_mockup`)
    const p = (shape as MockupShape).props
    const num = (v: unknown, fallback: number) => (v == null ? fallback : Number(v))
    editor.updateShape<MockupShape>({
      id: shape.id as MockupShape['id'], type: MOCKUP,
      props: {
        ...(args.design ? { design: refUrls(editor, [args.design])[0] } : {}),
        x: num(args.x, p.x), y: num(args.y, p.y), scale: num(args.scale, p.scale),
        rotation: (num(args.rotation, (p.rotation * 180) / Math.PI) * Math.PI) / 180, warp: num(args.warp, p.warp),
      },
    })
    return args.bake ? { image: await bakeToImage(editor, editor.getShape<MockupShape>(shape.id as MockupShape['id'])!) } : { updated: shape.id }
  },
  image_to_3d: (editor, args, onError) => started(editor, Array.isArray(args.views) && args.views.length
    ? viewsTo3d(editor, args.views.map((v: unknown) => imageOf(editor, v)), onError)
    : imageTo3d(editor, imageOf(editor, args.id), onError, args.model === 'pixal3d' ? 'pixal3d' : args.model === 'custom' ? CUSTOM_MODEL3D : 'trellis2')),
  custom_workflow: (_editor, args) => customWorkflowCommand(args),
  wait_generation: (editor, args) => waitResults(editor, (args.ids ?? []).map(String), Number(args.timeout_s) || 60),
}

export function registerCommandBus(editor: Editor, project: string, isStale: () => boolean, onError: ErrorSink) {
  const announce = () => api('/comfyart/mcp_page', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ client_id: CLIENT_ID, project }) }).catch((e) => onError(errorText(e)))
  void announce()
  const stops = [
    onReconnect(() => void announce()),
    onComfyEvent('comfyart-mcp-command', (msg: { id: string; action: string; project: string; chat?: string; args: Args }) => {
      if (msg.project !== project || isStale()) return
      const handler = HANDLERS[msg.action]
      const reply = (body: object) => api('/comfyart/mcp_command_result', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ command_id: msg.id, ...body }) })
        .catch((e) => onError(errorText(e)))
      if (!handler) return void reply({ ok: false, error: `unknown command ${msg.action}` })
      editor.markHistoryStoppingPoint(`agent:${msg.action}`)
      Promise.resolve()
        .then(() => {
          // #235: depth stays up until the handler promise settles, so startJob can snapshot the plan bypass
          pushAgentCommand()
          // generate_image/video pick their model from list_models themselves; other tools pass it to the cloud job
          setPendingModel(msg.action === 'generate_image' || msg.action === 'generate_video' ? undefined : msg.args?.model)
          try { return handler(editor, msg.args ?? {}, onError, msg.chat ?? '') } finally { setPendingModel(undefined) }
        })
        .then((result) => reply({ ok: true, result }), (e) => reply({ ok: false, error: errorText(e) }))
        .finally(() => popAgentCommand())
    }),
  ]
  return () => stops.forEach((stop) => stop())
}
