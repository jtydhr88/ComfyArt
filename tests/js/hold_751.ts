// #751 HOLD harness: pendingWash 1:1 slots, our COPY.
;(globalThis as any).localStorage ??= (() => {
  const ls: Record<string, string> = {}
  return { getItem: (k: string) => (k in ls ? ls[k] : null), setItem: (k: string, v: string) => { ls[k] = String(v) }, removeItem: (k: string) => { delete ls[k] } }
})()
import { BUILTIN_SKILLS, getTemplateUsage, recordTemplateUse } from '../../src/skills'
import { PENDING_WASH, SKILLS_748 } from '../../src/skillRaw748'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { SkillExamples } from '../../src/ui/SkillExamples'

const before = getTemplateUsage('packaging-design-director', 't2')
const r1 = recordTemplateUse('packaging-design-director', 't2')
const r2 = recordTemplateUse('packaging-design-director', 't2')
const final = BUILTIN_SKILLS.filter((s) => s.id in SKILLS_748)
console.log(JSON.stringify({
  usage: { before, r1, r2, after: getTemplateUsage('packaging-design-director', 't2'), other: getTemplateUsage('packaging-design-director', 't1'),
    store: JSON.parse(localStorage.getItem('comfyart.skillTemplateUsage') ?? '{}') },
  PENDING_WASH,
  skills: Object.fromEntries(final.map((s) => [s.id, {
    name: s.name, description: s.description ?? null, examples: s.examples ?? null, pendingWash: s.pendingWash ?? null, video: s.video ?? null,
    inputs: (s.inputs ?? []).map((i) => ({ key: i.key, ph: i.placeholder ?? null })),
    presets: (s.presets ?? []).map((p) => ({ image: p.image ?? null, stack: p.stack ?? null, pendingWash: p.pendingWash ?? null, prompt: p.prompt ?? null,
      inputs: (p.inputs ?? []).map((i) => ({ key: i.key, ph: i.placeholder ?? null })) })),
  }])),
  pendingHtml: renderToStaticMarkup(createElement(SkillExamples, { examples: [PENDING_WASH, PENDING_WASH], pendingWash: [0, 1] })),
}))
