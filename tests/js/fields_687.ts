;(globalThis as any).localStorage ??= (() => {
  const ls: Record<string, string> = {}
  return { getItem: (k: string) => (k in ls ? ls[k] : null), setItem: (k: string, v: string) => { ls[k] = String(v) }, removeItem: (k: string) => { delete ls[k] } }
})()

// #687 — dump every built-in skill's dialog field structure (and motion featured / templates) for the Lovart spec table. $0, no network.
import { BUILTIN_SKILLS } from '../../src/skills'
console.log(JSON.stringify(Object.fromEntries(BUILTIN_SKILLS.map((s) => [s.id, {
  fields: (s.inputs ?? []).map((f) => ({ key: f.key, type: f.type, required: !!f.required, accept: f.accept ?? (f.type === 'image' ? 'image' : null), maxLength: f.maxLength ?? null,
    zh: f.label.zh, en: f.label.en ?? null, phZh: f.placeholder?.zh ?? null, phEn: f.placeholder?.en ?? null })),
  templates: (s.presets ?? []).filter((p) => !!(p.image || p.video)).length,
  presets: (s.presets ?? []).length,
  featured: s.featured ?? [],
}]))))
