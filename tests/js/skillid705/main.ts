// #705: real src/skills.ts skillTool against an in-memory store (no WaveSpeed, no page). Prints one JSON report.
import { setLang } from '../i18n_stub'
import * as S from '../../../src/skills'
async function safe(fn: () => Promise<unknown>) { try { return await fn() } catch (e) { return { error: String((e as Error).message) } } }
async function main() {
  const out: Record<string, unknown> = { marker: S.SKILL_NON_RETRYABLE }
  for (const lang of ['en', 'zh'] as const) {
    setLang(lang)
    const list = (await S.skillTool({ action: 'list' })) as { skills: { id: string; name: string }[] }
    const reads: Record<string, unknown> = {}
    for (const b of S.listedSkills(S.BUILTIN_SKILLS)) {  // #673: hidden built-ins are not readable for new selection
      const byId = (await safe(() => S.skillTool({ action: 'read', id: b.id }))) as any
      const byName = (await safe(() => S.skillTool({ action: 'read', name: b.name }))) as any
      if (byId?.id !== b.id || byName?.id !== b.id) reads[b.id] = { byId, byName }
    }
    out[lang] = {
      inList: list.skills.some((s) => s.id === 'linkedin-banner'),
      badReads: reads,
      empty: await safe(() => S.skillTool({ action: 'read' })),
      emptyId: await safe(() => S.skillTool({ action: 'read', id: '' })),
      blankName: await safe(() => S.skillTool({ action: 'read', name: '  ' })),
      unknownName: await safe(() => S.skillTool({ action: 'read', name: 'nope' })),
    }
  }
  console.log(JSON.stringify(out))
}
main()
