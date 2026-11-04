;(globalThis as any).localStorage ??= (() => {
  const ls: Record<string, string> = {}
  return { getItem: (k: string) => (k in ls ? ls[k] : null), setItem: (k: string, v: string) => { ls[k] = String(v) }, removeItem: (k: string) => { delete ls[k] } }
})()

// #644 design: dialog 「N 个模板」 == thumbnails really shown (Examples strip + preset tiles with media). $0, no network.
import { BUILTIN_SKILLS, skillMeta, skillMetaLabel, skillThumbCount } from '../../src/skills'
console.log(JSON.stringify(Object.fromEntries(BUILTIN_SKILLS.map((s) => {
  const meta = skillMeta(s)
  return [s.id, {
    thumbs: (s.examples?.length ?? 0) + (s.presets ?? []).filter((p) => !!(p.image || p.video)).length,
    count: skillThumbCount(s), templates: meta?.templates ?? 0, label: meta ? skillMetaLabel({ ...meta, usage: 0 }) : null,
  }]
}))))
