;(globalThis as any).localStorage ??= (() => {
  const ls: Record<string, string> = {}
  return { getItem: (k: string) => (k in ls ? ls[k] : null), setItem: (k: string, v: string) => { ls[k] = String(v) }, removeItem: (k: string) => { delete ls[k] } }
})()

// #569 harness: per-skill data through the real src/skills.ts. No network, $0.
import { BUILTIN_SKILLS, hasSkillDialog, skillMeta } from '../../src/skills'
const old = { id: 'old-skill', name: 'Old', instructions: 'Old rules.', custom: true }
console.log(JSON.stringify({
  skills: Object.fromEntries(BUILTIN_SKILLS.map((s) => [s.id, {
    presets: s.presets?.map((p) => ({ id: p.id, zh: p.name.zh, en: p.name.en, image: p.image ?? null, prompt: !!p.prompt })) ?? null,
    examples: s.examples ?? null,
    inputs: (s.inputs ?? []).map((f) => ({ key: f.key, type: f.type, zh: f.label.zh, en: f.label.en ?? null, required: !!f.required, ph: f.placeholder ?? null })),
    meta: skillMeta(s),
  }])),
  old: { dialog: hasSkillDialog(old), meta: skillMeta(old) },
}))
