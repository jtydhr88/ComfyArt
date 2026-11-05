/** #748 — structure converted from the reference raw (scripts/convert_raw_748.py → src/data/skills-748.json),
 *  driven by raw/INDEX.md「Final skill table」. Skill ids ARE the reference skillKeys.
 *  template card: left = templates (stack depth = media count), right = that template's own questions.
 *  example card: right = the shared questions; left = our washed examples (highlights carry types/ratios only).
 *  The data carries NO URLs / usage numbers / long copy (→ docs/design/748/COPY-REWRITE.md, WASH-TODO.md). */
import data from './data/skills-748.json'
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

function toInput(q: RawInput): SkillInput {
  const long = q.type === 'text' && (q.maxLength ?? 0) > 200
  return {
    key: q.key, label: q.label, type: q.type === 'image' ? 'image' : long ? 'textarea' : 'text', ...(q.required ? { required: true } : {}),
    // OUR generic placeholder (reference long copy → COPY-REWRITE.md, pending product rewrite)
    ...(q.type === 'text' ? { placeholder: { zh: `请填写${q.label.zh}`, en: `Enter ${q.label.en.toLowerCase()}` } } : {}),
    ...(q.maxLength ? { maxLength: q.maxLength } : {}), ...(q.type === 'image' ? { accept: 'image' as const } : {}),
    ...(q.maxCount ? { maxCount: q.maxCount } : {}), ...(q.maxSizeMb ? { maxSizeMb: q.maxSizeMb } : {}),
  }
}

/** #748 — example card left = exactly the raw highlights (type order + count). A video highlight is the skill's
 *  one video (its cover is the same file, never an extra item); image highlights take our washed stills in order. */
function examplesFromHighlights(skill: Skill, r: RefSkill748): { examples?: string[] } {
  const hl = r.highlights ?? []
  if (!hl.length) return {}
  const isVid = (u: string) => /\.mp4(\?|$)/i.test(u)
  // placeholder pool: our own washed stills, cycled until per-slot wash lands (TODO(#748): WASH-TODO.md)
  const pool = [...new Set([...(skill.examples ?? []), ...(skill.featured ?? []), ...(skill.cover ? [skill.cover] : [])].filter((u) => !isVid(u)))]
  let i = 0
  const out = hl.map((h) => (h.type === 'video' ? skill.video : pool.length ? pool[i++ % pool.length] : undefined))
  return out.every((u) => !!u) ? { examples: out as string[] } : {}
}

export function applyRaw748(skill: Skill): Skill {
  const r = SKILLS_748[skill.id]
  if (!r) return skill
  const name = lang === 'zh' ? r.title.zh : r.title.en
  if (r.kind === 'example') return { ...skill, name, presets: undefined, inputs: (r.inputs ?? []).map(toInput), ...examplesFromHighlights(skill, r) }
  const tpls = r.templates ?? []
  if (!tpls.length) return { ...skill, name }
  // placeholder pool: our own already-washed stills for this skill (TODO(#748): per-slot wash, WASH-TODO.md)
  const taken = new Set((skill.presets ?? []).map((p) => p.image))
  const pool = [...(skill.featured ?? []), ...(skill.cover ? [skill.cover] : [])].filter((u) => !taken.has(u))
  const ph = (i: number) => (pool.length ? pool[i % pool.length] : undefined)
  let k = 0
  const presets = tpls.map((t, i): SkillPreset => {
    const old = skill.presets?.[i]
    const isVideo = t.media[0]?.type === 'video'
    const image = old?.image ?? ph(k++)
    const stack = t.depth > 1 ? Array.from({ length: t.depth }, (_, j) => (j === 0 ? image : ph(k++)) ?? '') : undefined
    const vid = old?.video ?? (isVideo ? skill.video : undefined)
    return {
      id: old?.id ?? `t${i + 1}`, name: t.name,
      prompt: `Template: ${t.name.en}. Follow this template's own inputs.`, // structure-only; reference prompts → COPY-REWRITE.md
      ...(image ? { image } : {}), ...(vid ? { video: vid } : {}), ...(stack ? { stack } : {}),
      inputs: t.inputs.map(toInput),
    }
  })
  return { ...skill, name, presets, inputs: presets[0].inputs }
}
