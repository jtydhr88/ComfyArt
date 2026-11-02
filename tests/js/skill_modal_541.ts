// #541 harness (+ #581 usage store needs localStorage in node)
;(globalThis as any).localStorage ??= (() => {
  const ls: Record<string, string> = {}
  return { getItem: (k: string) => (k in ls ? ls[k] : null), setItem: (k: string, v: string) => { ls[k] = String(v) }, removeItem: (k: string) => { delete ls[k] } }
})()

// #541 harness: Lovart meta line is real data only (template count from presets[]; no usage counter).
import { BUILTIN_SKILLS, isSkillMediaVideo, presetImage, skillMeta } from '../../src/skills'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { SkillExamples } from '../../src/ui/SkillExamples'
const img = (s: string) => Object.fromEntries(BUILTIN_SKILLS.find((k) => k.id === s)!.presets!.map((p) => [p.id, presetImage(BUILTIN_SKILLS.find((k) => k.id === s)!, p)]))
const mock = ['https://x.test/e1.webp', 'https://x.test/e2.webp', 'https://x.test/e3.webp', 'https://x.test/e4.webp', 'https://x.test/e5.webp']
const old = { id: 'old-skill', name: 'Old', instructions: 'Old rules.', custom: true }
console.log(JSON.stringify({
  meta: Object.fromEntries(BUILTIN_SKILLS.map((s) => [s.id, skillMeta(s)])),
  presets: Object.fromEntries(BUILTIN_SKILLS.map((s) => [s.id, s.presets?.length ?? 0])),
  old: skillMeta(old),
  imgs: { product: img('product'), brand: img('brand'), packaging: img('packaging') },
  exUrls: Object.fromEntries(BUILTIN_SKILLS.filter((s) => s.examples?.length).map((s) => [s.id, s.examples])),
  examples: Object.fromEntries(BUILTIN_SKILLS.map((s) => [s.id, s.examples?.length ?? 0])),
  exMock: renderToStaticMarkup(createElement(SkillExamples, { examples: mock })),
  exOne: renderToStaticMarkup(createElement(SkillExamples, { examples: [mock[0]] })),
  exNone: [renderToStaticMarkup(createElement(SkillExamples, {})), renderToStaticMarkup(createElement(SkillExamples, { examples: [] }))],
  productIds: BUILTIN_SKILLS.find((s) => s.id === 'product')!.presets!.map((p) => p.id),
  productNew: BUILTIN_SKILLS.find((s) => s.id === 'product')!.presets!.slice(3).map((p) => presetImage(BUILTIN_SKILLS.find((s) => s.id === 'product')!, p)),
  exVideoMock: renderToStaticMarkup(createElement(SkillExamples, { examples: ['https://x.test/clip.mp4', 'https://x.test/e2.webp'] })),
  isVideoMp4: isSkillMediaVideo('https://x.test/clip.mp4'),
  isVideoWebp: isSkillMediaVideo('https://x.test/e2.webp'),
}))
