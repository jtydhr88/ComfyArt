/** #748 — structure converted from the reference raw (scripts/convert_raw_748.py → src/data/skills-748.json),
 *  driven by raw/INDEX.md「Final skill table」. Skill ids ARE the reference skillKeys.
 *  template card: left = templates (stack depth = media count), right = that template's own questions.
 *  example card: right = the shared questions; left = our washed examples (1:1 per slot from data/wash-748.json; missing = PENDING_WASH).
 *  The data carries NO URLs / usage numbers / long copy (→ docs/design/748/COPY-REWRITE.md, WASH-TODO.md). */
import data from './data/skills-748.json'
import wash from './data/wash-748.json'
import copy from './data/copy-748.json'
import { lang } from './i18n'
import type { Skill, SkillInput, SkillPreset } from './skills'

interface RawInput { key: string; type: 'text' | 'image'; required: boolean; label: { zh: string; en: string }; maxLength?: number; maxCount?: number; maxSizeMb?: number }
interface RawTemplate { name: { zh: string; en: string }; depth: number; media: { type: 'image' | 'video'; ratio: number | null }[]; inputs: RawInput[] }
export interface RefSkill748 {
  source: string; kind: 'template' | 'example'; title: { zh: string; en: string }; assetDir: string
  templates?: RawTemplate[]; inputs?: RawInput[]; coverMode?: 'single' | 'carousel'; highlights?: { type: 'image' | 'video'; ratio: number | null }[]; hold?: string
}

export const SKILLS_748 = (data as { skills: Record<string, RefSkill748> }).skills
/** washed-asset folder for a skill id (review-assets paths predate the skillKey ids); own ids map to themselves. */
export const assetDir = (id: string): string => SKILLS_748[id]?.assetDir ?? id
export const skillSource = (id: string): string | undefined => SKILLS_748[id]?.source

type Loc = { zh: string; en: string }
interface Ours { description?: Loc; prompt?: Loc; placeholders?: Record<string, Loc>; templates?: Record<string, Ours> }
/** #751 — OUR product copy (docs/design/748/COPY-REWRITE.md → convert → data/copy-748.json). */
const COPY = copy as Record<string, Ours>
const loc = (l?: Loc) => (l ? (lang === 'zh' ? l.zh : l.en) : undefined)

function toInput(q: RawInput, ours?: Record<string, Loc>): SkillInput {
  const long = q.type === 'text' && (q.maxLength ?? 0) > 200
  return {
    key: q.key, label: q.label, type: q.type === 'image' ? 'image' : long ? 'textarea' : 'text', ...(q.required ? { required: true } : {}),
    // OUR generic placeholder (reference long copy → COPY-REWRITE.md, pending product rewrite)
    ...(q.type === 'text' ? { placeholder: ours?.[q.key] ?? { zh: `请填写${q.label.zh}`, en: `Enter ${q.label.en.toLowerCase()}` } } : {}),
    ...(q.maxLength ? { maxLength: q.maxLength } : {}), ...(q.type === 'image' ? { accept: 'image' as const } : {}),
    ...(q.maxCount ? { maxCount: q.maxCount } : {}), ...(q.maxSizeMb ? { maxSizeMb: q.maxSizeMb } : {}),
  }
}

/** #751 — ONE unified placeholder for every slot whose wash has not landed (marked pendingWash). Never cycle washed stills. */
export const PENDING_WASH = 'comfyart:pending-wash'
export const isPendingWash = (u?: string | null) => u === PENDING_WASH
const WASH = (wash as { examples: Record<string, (string | null)[]> }).examples

/** #751 — example card left = exactly the raw highlights, 1:1 slot → asset (src/data/wash-748.json).
 *  video slot = the skill's own washed video; image slot = its own washed still, else PENDING_WASH + pendingWash. */
function examplesFromHighlights(skill: Skill, r: RefSkill748): { examples?: string[]; pendingWash?: number[] } {
  const hl = r.highlights ?? []
  if (!hl.length) return {}
  const slots = WASH[skill.id] ?? []
  const pendingWash: number[] = []
  const examples = hl.map((h, i) => {
    const u = h.type === 'video' ? skill.video : slots[i]
    if (u) return u
    pendingWash.push(i)
    return PENDING_WASH
  })
  return { examples, pendingWash }
}

export function applyRaw748(skill: Skill): Skill {
  const r = SKILLS_748[skill.id]
  if (!r) return skill
  const name = lang === 'zh' ? r.title.zh : r.title.en
  const ours = COPY[skill.id] ?? {}
  const description = loc(ours.description) ?? skill.description
  if (r.kind === 'example') return { ...skill, name, description, presets: undefined, inputs: (r.inputs ?? []).map((q) => toInput(q, ours.placeholders)), ...examplesFromHighlights(skill, r) }
  const tpls = r.templates ?? []
  if (!tpls.length) return { ...skill, name, description }
  const presets = tpls.map((t, i): SkillPreset => {
    const old = skill.presets?.[i]
    const isVideo = t.media[0]?.type === 'video'
    const image = old?.image ?? PENDING_WASH // the template's own wash (1:1), else the unified placeholder
    const stack = t.depth > 1 ? Array.from({ length: t.depth }, (_, j) => (j === 0 ? image : PENDING_WASH)) : undefined
    const pendingWash = Array.from({ length: t.depth }, (_, j) => j).filter((j) => (j === 0 ? image : PENDING_WASH) === PENDING_WASH)
    const vid = old?.video ?? (isVideo ? skill.video : undefined)
    return {
      id: old?.id ?? `t${i + 1}`, name: t.name,
      prompt: loc(ours.templates?.[i + 1]?.prompt) ?? `Template: ${t.name.en}. Follow this template's own inputs.`,
      ...(ours.templates?.[i + 1]?.description ? { description: ours.templates[i + 1].description } : {}),
      image, ...(vid ? { video: vid } : {}), ...(stack ? { stack } : {}), ...(pendingWash.length ? { pendingWash } : {}),
      inputs: t.inputs.map((q) => toInput(q, ours.templates?.[i + 1]?.placeholders)),
    }
  })
  return { ...skill, name, description, presets, inputs: presets[0].inputs }
}
