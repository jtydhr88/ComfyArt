import { createShapeId, type Editor, type TLShape, type TLShapeId } from 'tldraw'

import { defaultTarget, loadNamed, loadWorkflow, mediaMeta, refKind, uploadImage, validTarget, viewUrl, type PromptGraph, type RefKind } from './comfy'
import type { LoraPick } from './loras'
import { ask, stripThink } from './llm'
import { freeSpot, spawnHolder, startJob, type ErrorSink, type GenInfo } from './jobs'
import { GENERATOR, type GeneratorShape } from './shapes/GeneratorShape'
import { agentModels, isVideo, modelOf } from './models'
import { CUSTOM_GENERATE, customGraph, withAlpha } from './customWorkflows'
import { t } from './i18n'
import { applyRefs, PALETTE_MODE, refControlsOf, refHints, refLimit, refModesOf, refStrengthsOf, usableRefs } from './refModes'
import { paletteImage, palettePrompt } from './palette'
import { annotated, randomSeed, type Built } from './workflows'
import { imageToVideoGraph, lipSyncGraph, MAX_VIDEO_REF_KINDS, motionGraph, r2vGraph, storyboardGraph, t2vGraph, VIDEO_AREAS, videoSize, type Scene } from './videoGraphs'
import { SHOTS, STYLES, VIDEO_RATIOS } from './genOptions'

export function scenesOf(shape: GeneratorShape): Scene[] {
  return (shape.meta.scenes as Scene[] | undefined) ?? []
}

export function capRefs(srcs: string[]): string[] {
  const count: Record<RefKind, number> = { image: 0, video: 0, audio: 0 }
  return srcs.filter((src) => count[refKind(src)]++ < MAX_VIDEO_REF_KINDS[refKind(src)])
}

const H3_MAX_SECONDS = 3600 / 24

export type VideoMode = 'frames' | 'refs' | 'motion' | 'lipsync'
const VIDEO_MODES: VideoMode[] = ['refs', 'motion', 'lipsync']
export const videoModeOf = (shape: GeneratorShape): VideoMode => (VIDEO_MODES.includes(shape.meta.videoMode as VideoMode) ? shape.meta.videoMode as VideoMode : 'frames')
export const motionOf = (shape: GeneratorShape) => (shape.meta.motion as string | undefined) ?? null
export const speechOf = (shape: GeneratorShape) => (shape.meta.speech as string | undefined) ?? null

const SHORT_SIDE: Record<string, number> = { '1K': 1024, '2K': 2048 }

function ratioOf(ratio: string): number {
  const [a, b] = ratio.split(':').map(Number)
  return a / b
}

export function nearestRatio(aspect: number, ratios: string[]): string {
  return ratios.reduce((a, b) => Math.abs(Math.log(ratioOf(b) / aspect)) < Math.abs(Math.log(ratioOf(a) / aspect)) ? b : a)
}

const snap16 =(v: number) => Math.round(v / 16) * 16

export function targetSize({ ratio, resolution, workflow, cw, ch }: GeneratorShape['props']): [number, number] {
  const r = ratioOf(ratio)
  if (isVideo(workflow)) return videoSize(r, VIDEO_AREAS[resolution] ?? VIDEO_AREAS['768p'])
  if (resolution === 'custom') return [snap16(cw), snap16(ch)]
  const short = SHORT_SIDE[resolution] ?? 1024
  return r >= 1 ? [snap16(short * r), short] : [short, snap16(short / r)]
}

export function createGenerator(editor: Editor, video = false, props: Partial<GeneratorShape['props']> = {}, focus = true, from?: [number, number]): TLShapeId {
  const id = createShapeId()
  const ratio = props.ratio ?? (video ? VIDEO_RATIOS[0] : '1:1')
  const workflow = props.workflow || agentModels(video)[0].id
  const [w, h] = targetSize({ ...editor.getShapeUtil<GeneratorShape>(GENERATOR).getDefaultProps(), ...props, ratio, workflow })
  const [x, y] = freeSpot(editor, w, h, from)
  editor.createShape({ id, type: GENERATOR, x, y, props: { ...props, w, h, ratio, workflow } })
  if (focus) {
    editor.setCurrentTool('select')
    editor.select(id)
    editor.zoomToSelectionIfOffscreen(64, { animation: { duration: 200 } })
  }
  return id
}

export function refsOf(shape: GeneratorShape): string[] {
  return (shape.meta.refs as string[] | undefined) ?? []
}

export const BASE_STRENGTH = 60

export function baseOf(shape: GeneratorShape): { src: string; strength: number } | null {
  const src = shape.meta.base as string | undefined
  return src ? { src, strength: (shape.meta.strength as number | undefined) ?? BASE_STRENGTH } : null
}

export function lastFrameOf(shape: GeneratorShape): string | null {
  return (shape.meta.lastFrame as string | undefined) ?? null
}

export function colorsOf(shape: GeneratorShape): string[] {
  return (shape.meta.colors as string[] | undefined) ?? []
}

export const negativeOf = (shape: GeneratorShape) => (shape.meta.negative as string | undefined) ?? ''
export const seedOf = (shape: GeneratorShape) => (shape.meta.seed as number | null | undefined) ?? null
export const runOnOf = (shape: GeneratorShape) => validTarget(shape.meta.runOn) ?? defaultTarget()
export const lorasOf = (shape: GeneratorShape) => (shape.meta.loras as LoraPick[] | undefined) ?? []

function applySeed(graph: PromptGraph, seed: number) {
  for (const node of Object.values(graph)) {
    if (node.class_type === 'RandomNoise') node.inputs.noise_seed = seed
    if (node.class_type === 'KSampler') node.inputs.seed = seed
  }
}

function applyLoras(graph: PromptGraph, unet: string, loras: LoraPick[]) {
  const source = JSON.stringify([unet, 0])
  const consumers = Object.values(graph).filter((n) => JSON.stringify(n.inputs.model) === source)
  let model: [string, number] = [unet, 0]
  loras.forEach(({ name, strength }, i) => {
    graph[`lora${i}`] = { class_type: 'LoraLoaderModelOnly', inputs: { model, lora_name: name, strength_model: strength / 100 } }
    model = [`lora${i}`, 0]
  })
  for (const n of consumers) n.inputs.model = model
}

async function caption(spec: string, prompt: string, width: number, height: number): Promise<string> {
  const { system, template } = await loadWorkflow(spec) as unknown as { system: string; template: string }
  return stripThink(await ask(template.replace('{w}', String(width)).replace('{h}', String(height)).replace('{prompt}', prompt), system, []))
}

async function generateGraph(shape: GeneratorShape): Promise<Built> {
  const { ratio, count, workflow, duration, transparent, quality, style } = shape.props
  const suffix = (isVideo(workflow) ? SHOTS : STYLES).find(([k]) => k === style)?.[2]
  const refs = refsOf(shape)
  const model = isVideo(workflow) ? null : modelOf(workflow) ?? agentModels(false)[0]
  const colors = isVideo(workflow) ? [] : colorsOf(shape)
  const picked = model ? usableRefs(model, refs, refModesOf(shape)).slice(0, refLimit(model)) : []
  const palette = colors.length && model?.refs && model.id !== CUSTOM_GENERATE && picked.length < refLimit(model)
    ? viewUrl(await uploadImage(await paletteImage(colors), `palette-mosaic-${colors.join('').replace(/#/g, '')}.png`))
    : null
  const used = palette ? [...picked, { src: palette, mode: PALETTE_MODE }] : picked
  const hints = refHints(used)
  const prompt = [
    [shape.props.prompt, suffix, transparent && 'isolated subject on a plain white background'].filter(Boolean).join(', '),
    ...hints,
    colors.length > 0 && palettePrompt(colors),
  ].filter(Boolean).join(' ')
  if (isVideo(workflow)) {
    const area = VIDEO_AREAS[shape.props.resolution] ?? VIDEO_AREAS['768p']
    const scenes = scenesOf(shape).filter((sc) => sc.prompt.trim())
    if (scenes.length) {
      return storyboardGraph(scenes.map((sc) => ({ ...sc, prompt: [sc.prompt, suffix].filter(Boolean).join(', ') })), ratioOf(ratio), refs[0] ? annotated(refs[0]) : null, area)
    }
    const mode = videoModeOf(shape)
    if (mode === 'refs' && refs.length) return r2vGraph(refs.map((src) => ({ file: annotated(src), kind: refKind(src) })), prompt, ratioOf(ratio), duration, area)
    const motion = motionOf(shape)
    if (mode === 'motion' && refs[0] && motion) return motionGraph(annotated(refs[0]), annotated(motion), prompt, ratioOf(ratio), duration, area)
    const speech = speechOf(shape)
    if (mode === 'lipsync' && refs[0] && speech) {
      const { seconds } = await mediaMeta(speech, 'audio')
      return lipSyncGraph(annotated(refs[0]), annotated(speech), prompt, ratioOf(ratio), Math.min(seconds, H3_MAX_SECONDS), area)
    }
    const last = lastFrameOf(shape)
    return refs.length || last
      ? imageToVideoGraph(refs[0] ? annotated(refs[0]) : null, prompt, ratioOf(ratio), duration, last ? annotated(last) : null, area)
      : t2vGraph(prompt, ratioOf(ratio), duration, area)
  }
  const [width, height] = targetSize(shape.props)
  if (model?.id === CUSTOM_GENERATE) {
    const loras = lorasOf(shape)
    const start = baseOf(shape)
    const [image, image2] = picked.map((r) => annotated(r.src))
    const custom = await customGraph('generate', { prompt, width, height, count, image, image2, base: start ? annotated(start.src) : undefined, strength: start ? start.strength / 100 : undefined }, (graph, markers, result) => {
      if (loras.length) {
        if (!markers.unet) throw new Error(t('customWorkflows.needsUnet', model.label))
        applyLoras(graph, markers.unet, loras)
      }
      if (transparent) withAlpha(graph, markers, result)
    })
    if (!custom) throw new Error(t('customWorkflows.generateGone', model.label))
    return custom
  }
  if (!model) throw new Error('unknown image model')
  const extra = [...model.sizes!, model.steps?.[0], model.negative?.[0], model.refs === 'latent' && 'guider'].filter((n) => typeof n === 'string')
  const { graph, id } = await loadNamed(model.id, 'unet', 'vae', 'prompt', 'size', 'sampler', 'decode', 'save', ...extra)
  graph[id.prompt].inputs[model.prompt!] = model.caption ? await caption(model.caption, prompt, width, height) : prompt
  if (model.negative) graph[id[model.negative[0]]].inputs[model.negative[1]] = negativeOf(shape)
  if (model.lora !== undefined) applyLoras(graph, id.unet, lorasOf(shape))
  applyRefs(graph, id, model, used, refStrengthsOf(shape), refControlsOf(shape), width, height)
  for (const name of model.sizes!) Object.assign(graph[id[name]].inputs, { width, height })
  graph[id.size].inputs.batch_size = count
  const base = baseOf(shape)
  if (base) {
    graph.b0 = { class_type: 'LoadImage', inputs: { image: annotated(base.src) } }
    graph.b1 = { class_type: 'ImageScale', inputs: { image: ['b0', 0], upscale_method: 'lanczos', width, height, crop: 'center' } }
    graph.b2 = { class_type: 'VAEEncode', inputs: { pixels: ['b1', 0], vae: [id.vae, 0] } }
    graph.b3 = { class_type: 'RepeatLatentBatch', inputs: { samples: ['b2', 0], amount: count } }
    graph[id.sampler].inputs.latent_image = ['b3', 0]
    if (graph[id.sampler].class_type === 'KSampler') graph[id.sampler].inputs.denoise = base.strength / 100
    else {
      graph.b4 = { class_type: 'SplitSigmasDenoise', inputs: { sigmas: graph[id.sampler].inputs.sigmas, denoise: base.strength / 100 } }
      graph[id.sampler].inputs.sigmas = ['b4', 1]
    }
  }
  if (model.steps) graph[id[model.steps[0]]].inputs.steps = model.steps[1][quality] ?? model.steps[1].standard
  if (transparent) {
    Object.assign(graph, {
      bg1: { class_type: 'LoadBackgroundRemovalModel', inputs: { bg_removal_name: 'birefnet.safetensors' } },
      bg2: { class_type: 'RemoveBackground', inputs: { bg_removal_model: ['bg1', 0], image: [id.decode, 0] } },
      bg3: { class_type: 'InvertMask', inputs: { mask: ['bg2', 0] } },
      bg4: { class_type: 'JoinImageWithAlpha', inputs: { image: [id.decode, 0], alpha: ['bg3', 0] } },
    })
    graph[id.save].inputs.images = ['bg4', 0]
  }
  return { graph, result: id.save }
}

export function generate(editor: Editor, shape: GeneratorShape, onError: ErrorSink) {
  const kind = isVideo(shape.props.workflow) ? 'video' : 'image'
  const name = shape.props.prompt || scenesOf(shape)[0]?.prompt || ''
  const seed = seedOf(shape) ?? randomSeed()
  const built = generateGraph(shape).then((b) => { applySeed(b.graph, seed); return b })
  return startJob(editor, shape.id, built, { name: name.slice(0, 32), kind, extra: { seed }, runOn: runOnOf(shape) }, onError)
}

export function genInfoOf(shape: TLShape): GenInfo | null {
  return (shape.meta.gen as GenInfo | undefined) ?? null
}

function settingsOf(info: GenInfo): Partial<GeneratorShape['props']> {
  return {
    prompt: info.prompt ?? '',
    ...(info.ratio ? { ratio: info.ratio } : {}),
    ...(info.resolution ? { resolution: info.resolution } : {}),
    ...(info.duration ? { duration: info.duration } : {}),
    ...(info.workflow ? { workflow: info.workflow } : {}),
    ...info.settings,
  }
}

const inputsOf = (info: GenInfo) => info.inputs ?? (info.refs ? { refs: info.refs } : {})

export function remix(editor: Editor, shape: TLShape) {
  const info = genInfoOf(shape)
  if (!info?.prompt) return
  const id = createGenerator(editor, isVideo(info.workflow ?? ''), settingsOf(info))
  editor.updateShape<GeneratorShape>({ id, type: GENERATOR, meta: inputsOf(info) })
}

export function regenerate(editor: Editor, shape: TLShape, onError: ErrorSink) {
  const info = genInfoOf(shape)
  if (!info?.prompt) return
  const holder = spawnHolder(editor, shape)
  editor.updateShape<GeneratorShape>({ id: holder, type: GENERATOR, props: { ...settingsOf(info), count: 1 }, meta: { temp: true, ...inputsOf(info) } })
  return generate(editor, editor.getShape<GeneratorShape>(holder)!, onError)
}
