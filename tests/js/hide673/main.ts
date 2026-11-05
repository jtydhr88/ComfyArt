// #673: real src/skills.ts against an in-memory store. Prints one JSON report of what each pick-list exposes.
import { setLang } from '../i18n_stub'
import * as S from '../../../src/skills'
async function safe(fn: () => Promise<unknown>) { try { return await fn() } catch (e) { return { error: String((e as Error).message) } } }
async function main() {
  setLang('zh')
  const all = await S.loadSkills()
  const listed = await S.loadListedSkills()
  const chips = S.skillChips(listed)
  const byChip: Record<string, string[]> = {}
  for (const c of chips) byChip[c] = listed.filter((s) => S.matchesSkillChip(s, c)).map((s) => s.id)
  const featured = [...new Set(S.skillFeaturedCases(listed).map((f) => f.skill.id))]
  const agentList = ((await S.skillTool({ action: 'list' })) as { skills: { id: string }[] }).skills.map((s) => s.id)
  const hiddenReads: Record<string, unknown> = {}
  const resolved: Record<string, unknown> = {}
  for (const id of S.HIDDEN_BUILTIN_SKILL_IDS) {
    const b = S.BUILTIN_SKILLS.find((s) => s.id === id)!
    hiddenReads[id] = { byId: await safe(() => S.skillTool({ action: 'read', id })), byName: await safe(() => S.skillTool({ action: 'read', name: b.name })), idInName: await safe(() => S.skillTool({ action: 'read', name: id })), nameInId: await safe(() => S.skillTool({ action: 'read', id: b.name })) }
    // saved session / card path: handoff.ts + Home starter use loadSkills().find(id) → withPreset → run params
    resolved[id] = await safe(async () => {
      const s = all.find((x) => x.id === id)
      if (!s) return { found: false }
      const p = S.withPreset(s, s.presets?.[0]?.id ?? null)
      return { found: true, name: s.name, params: Object.keys(S.skillRunParams(p, S.skillDefaults(p), s.presets?.[0]?.id ?? null)).length >= 0,
        cover: S.skillCover(s) !== undefined, desc: typeof S.skillDescription(s) }
    })
  }
  const listedRead = await safe(() => S.skillTool({ action: 'read', id: 'poster-differentiated-compiler' }))
  const unknown = await safe(() => S.skillTool({ action: 'read', id: 'nope' }))
  // #673 deep link / resend / try-it: attach-time refusal, zero network
  const guard: Record<string, unknown> = {}
  let requests = 0
  const realFetch = globalThis.fetch
  globalThis.fetch = (async () => { requests++; throw new Error('no network in #673 guard') }) as typeof fetch
  for (const lg of ['zh', 'en'] as const) {
    setLang(lg)
    const find = (id: string) => all.find((x) => x.id === id)!
    const out: Record<string, unknown> = {}
    for (const id of ['yingzao', 'crt-interface']) {
      S.skillNoticeAtom.set(null); S.skillAtom.set(find('poster-differentiated-compiler'))
      // deep link + try-it: attachSkill; resend + send safety net: blockHiddenSkill
      const attached = S.attachSkill(find(id))
      const linkChip = S.skillAtom.get()?.id ?? null
      const linkNotice = S.skillNoticeAtom.get()
      S.skillNoticeAtom.set(null)
      let submits = 0
      const blocked = S.blockHiddenSkill(find(id))
      if (!blocked) submits++  // the resend / sendToAgent path would call sendMessage here
      out[id] = { attached, linkChip, linkNotice, blocked, resendNotice: S.skillNoticeAtom.get(), submits }
    }
    S.skillNoticeAtom.set('stale')
    const okAttach = S.attachSkill(find('poster-differentiated-compiler'))
    out.listed = { attached: okAttach, chip: S.skillAtom.get()?.id, notice: S.skillNoticeAtom.get(), blocked: S.blockHiddenSkill(find('poster-differentiated-compiler')) }
    out.notice = S.hiddenSkillNotice(find('yingzao'))
    out.readErr = (await safe(() => S.skillTool({ action: 'read', id: 'yingzao' })) as any).error
    guard[lg] = out
  }
  guard.requests = requests
  globalThis.fetch = realFetch
  setLang('zh')
  console.log(JSON.stringify({ guard,
    hidden: S.HIDDEN_BUILTIN_SKILL_IDS, builtinAll: S.BUILTIN_SKILLS.map((s) => s.id), listed: listed.map((s) => s.id),
    chips, byChip, featured, agentList, hiddenReads, resolved, listedReadId: (listedRead as any).id, unknown,
  }))
}
main()
