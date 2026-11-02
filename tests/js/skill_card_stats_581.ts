// #581 harness: real local usage store + meta label; no fake favorite counts.
// Avoid SkillRunDialog SSR (pulls SkillsDialog → tldraw); wiring asserted in py source greps.
;(globalThis as any).localStorage = (() => {
  const ls: Record<string, string> = {}
  return {
    getItem: (k: string) => (k in ls ? ls[k] : null),
    setItem: (k: string, v: string) => { ls[k] = String(v) },
    removeItem: (k: string) => { delete ls[k] },
  }
})()

import {
  BUILTIN_SKILLS,
  getSkillUsage,
  loadSkillUsage,
  recordSkillUse,
  skillMeta,
  skillMetaLabel,
  skillShareUrl,
  toggleFavourite,
  loadFavourites,
} from '../../src/skills'
import { setLang, t } from '../../src/i18n'

const poster = BUILTIN_SKILLS.find((s) => s.id === 'poster')!
const product = BUILTIN_SKILLS.find((s) => s.id === 'product')!
const emptySkill = { id: 'no-presets-yet', name: 'Empty', instructions: 'x' }

const emptyUsage = loadSkillUsage()
const metaEmpty = skillMeta(poster) // poster: examples only → templates 0, usage 0 → null
const metaProductBefore = skillMeta(product)

recordSkillUse('product')
recordSkillUse('product')
recordSkillUse('poster')

const after = loadSkillUsage()
const metaProductAfter = skillMeta(product)
const metaPosterAfter = skillMeta(poster)
const metaEmptySkill = skillMeta(emptySkill)

setLang('zh')
const zhJoined = skillMetaLabel(metaProductAfter!)
const zhUsageOnly = skillMetaLabel(metaPosterAfter!)
const zhTemplatesOnly = skillMetaLabel({ templates: 6, usage: 0 })

setLang('en')
const enJoined = skillMetaLabel(metaProductAfter!)

const share = skillShareUrl('product', 'https://app.example/comfyart/?ask=hi&mode=agent&ref=a.png')
const sharePlain = skillShareUrl('poster', 'https://app.example/')

toggleFavourite('product')
const favs = loadFavourites()

console.log(JSON.stringify({
  emptyUsage,
  metaEmpty,
  metaProductBefore,
  after,
  productUses: getSkillUsage('product'),
  posterUses: getSkillUsage('poster'),
  metaProductAfter,
  metaPosterAfter,
  metaEmptySkill,
  zhJoined,
  zhUsageOnly,
  zhTemplatesOnly,
  enJoined,
  share,
  sharePlain,
  favs,
  tShareZh: (setLang('zh'), t('skillRun.share')),
}))
