;(globalThis as any).localStorage ??= (() => {
  const ls: Record<string, string> = {}
  return { getItem: (k: string) => (k in ls ? ls[k] : null), setItem: (k: string, v: string) => { ls[k] = String(v) }, removeItem: (k: string) => { delete ls[k] } }
})()
// #687 — feed pre-#687 field keys (OLD env JSON) into the dialog value path; $0, no network.
import { BUILTIN_SKILLS, skillDefaults, skillRunParams, missingInputs } from '../../src/skills'
const OLD: Record<string, Record<string, string>> = JSON.parse(process.env.OLD ?? '{}')
console.log(JSON.stringify(Object.fromEntries(Object.entries(OLD).map(([id, old]) => {
  const s = BUILTIN_SKILLS.find((x) => x.id === id)!
  const defaults = skillDefaults(s)
  const values = { ...defaults, ...old }
  try {
    return [id, { name: s.name, defaults, params: skillRunParams(s, values), missing: missingInputs(s, values), error: null }]
  } catch (e) { return [id, { name: s.name, defaults, error: String(e) }] }
}))))
