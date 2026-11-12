import { atom } from 'tldraw'

import { api, cloudMode, defaultTarget, lanMode, loadModelPaths, readUserJson, writeUserJson } from './comfy'
import { CUSTOM_GENERATE, workflowConfigAtom } from './customWorkflows'
import { t } from './i18n'
import { lanHas } from './instances'

export interface ModelDef {
  id: string
  label: string
  desc: string
  files: string[]
  video?: boolean
  refs?: 'qwen' | 'latent' | 'custom'
  prompt?: string
  steps?: [string, Record<string, number>]
  sizes?: string[]
  caption?: string
  control?: string
  negative?: [string, string]
  lora?: string | null
  single?: boolean
}

export const IMAGE_MODELS: ModelDef[] = [
  {
    id: 'qwen-image-2.1-t2i.api.json', label: 'Qwen Image 2.1', desc: t('models.highOverallQualityAccurateChinese'), files: ['qwen_image_2.1_int8_convrot.safetensors'],
    refs: 'qwen', prompt: 'prompt', steps: ['sampler', { fast: 12, standard: 25, high: 40 }], sizes: ['size'], lora: 'qwen-image-2.1',
  },
  {
    id: 'z-image-turbo-t2i.api.json', label: 'Z-Image Turbo', desc: t('models.fast8StepGenerationGreat'), files: ['z_image_turbo_bf16.safetensors'],
    prompt: 'text', sizes: ['size'], lora: 'z-image',
  },
  {
    id: 'krea2-turbo-t2i.api.json', label: 'Krea 2 Turbo', desc: t('models.krea2TurboFast8Step'), files: ['krea2_turbo_int8_convrot.safetensors'],
    prompt: 'text', sizes: ['size'], lora: null,
  },
  {
    id: 'flux2-klein-9b-t2i.api.json', label: 'Flux.2 Klein 9B', desc: t('models.fast4StepGenerationSupports'), files: ['flux-2-klein-9b-nvfp4.safetensors'],
    refs: 'latent', prompt: 'text', sizes: ['size', 'scheduler'], lora: 'flux2-klein',
  },
  {
    id: 'flux3-klein-t2i.api.json', label: 'FLUX.3 Klein', desc: t('models.flux3KleinFast16Step'), files: ['flux3-image-klein-int8-convrot.safetensors'],
    refs: 'latent', prompt: 'text', sizes: ['size'], lora: 'flux3-klein',
  },
  {
    id: 'moss-image-t2i.api.json', label: 'MOSS-Image', desc: t('models.mossImageFullCaption'), files: ['moss_image_sft_int8_convrot.safetensors'],
    prompt: 'text', sizes: ['size'], lora: 'moss-image',
  },
  {
    id: 'minimax-h3-image-t2i.api.json', label: 'MiniMax H3 Image', desc: t('models.minimaxH3Image'), files: ['minimax_h3_image_pruned_int8_convrot.safetensors'],
    refs: 'qwen', prompt: 'prompt', sizes: ['size'], lora: null, single: true,
  },
  {
    id: 'qwen-image-2512-t2i.api.json', label: 'Qwen Image 2512', desc: t('models.solidDetailAndCompositionSupports'), files: ['qwen_image_2512_fp8_e4m3fn.safetensors'],
    prompt: 'text', steps: ['sampler', { fast: 20, standard: 30, high: 50 }], sizes: ['size'], control: 'Qwen-Image-2512-Fun-Controlnet-Union-2602.safetensors', negative: ['negative', 'text'], lora: 'qwen-image',
  },
  {
    id: 'ideogram4-t2i.api.json', label: 'Ideogram 4', desc: t('models.greatAtLayoutLogosAnd'), files: ['ideogram4_fp8_scaled.safetensors', 'ideogram4_unconditional_fp8_scaled.safetensors'],
    prompt: 'text', caption: 'ideogram4-caption.json',
    steps: ['scheduler', { fast: 12, standard: 20, high: 48 }], sizes: ['size', 'scheduler'],
  },
]

export const VIDEO_MODELS: ModelDef[] = [
  { id: 't2v-minimax-h3.api.json', label: 'MiniMax H3', desc: t('models.syncedAudioAndVideoSupports'), files: ['minimax_h3_fl2va_pruned_int8_convrot.safetensors'], video: true },
]

export const isVideo = (workflow: string) => VIDEO_MODELS.some((m) => m.id === workflow)
function customModels(): ModelDef[] {
  const file = workflowConfigAtom.get().generate
  return file ? [{ id: CUSTOM_GENERATE, label: file.replace(/\.json$/, ''), desc: t('customWorkflows.customModelDesc'), files: [], lora: null, refs: 'custom' }] : []
}

export const modelOf = (workflow: string) => [...IMAGE_MODELS, ...VIDEO_MODELS, ...customModels()].find((m) => m.id === workflow)

export interface ModelPrefs { auto: boolean; enabled: string[] }

const FILE = 'comfyart/models.json'
const ALL = [...IMAGE_MODELS, ...VIDEO_MODELS].map((m) => m.id)

export const modelPrefsAtom = atom<ModelPrefs>('model prefs', { auto: true, enabled: ALL })
export const installedAtom = atom<string[] | null>('installed models', null)

export async function loadModels() {
  const [prefs, files, paths] = await Promise.all([readUserJson<ModelPrefs | null>(FILE, null), api('/models/diffusion_models'), loadModelPaths()])
  if (prefs) modelPrefsAtom.set(prefs)
  const names: string[] = files.ok ? await files.json() : []
  installedAtom.set([...IMAGE_MODELS, ...VIDEO_MODELS].filter((m) => m.files.every((f) => names.includes(f) || f in paths)).map((m) => m.id))
}

export async function saveModelPrefs(prefs: ModelPrefs) {
  modelPrefsAtom.set(prefs)
  await writeUserJson(FILE, prefs)
}

export function installedModels(video: boolean): ModelDef[] {
  const builtin = (video ? VIDEO_MODELS : IMAGE_MODELS).filter((m) => isInstalled(m.id))
  return video ? builtin : [...builtin, ...customModels()]
}

export function agentModels(video: boolean): ModelDef[] {
  const { auto, enabled } = modelPrefsAtom.get()
  const list = installedModels(video)
  const picked = auto ? list : list.filter((m) => enabled.includes(m.id))
  return picked.length ? picked : list.length ? list.slice(0, 1) : (video ? VIDEO_MODELS : IMAGE_MODELS).slice(0, 1)
}

export function isInstalled(id: string, runOn = defaultTarget()): boolean {
  const installed = installedAtom.get()
  const def = [...IMAGE_MODELS, ...VIDEO_MODELS].find((m) => m.id === id)
  if (cloudMode() || !installed || !def) return true
  const here = installed.includes(id)
  if (!lanMode() || runOn === 'local') return here
  const lan = lanHas(def.files, runOn)
  return runOn === 'auto' ? here || lan : lan
}
