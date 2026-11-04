// #155: WaveSpeed error kinds -> readable zh/en messages (never the raw WaveSpeed text).
import { setLang } from './i18n_stub'
import { agentError, agentErrorText, fmtUsd, wsBodyError, wsErrorText } from '../../src/wsErrors'

const kinds = ['insufficientCredit', 'moderation', 'rateLimit', 'invalidKey', 'network', 'failed']
const raw = { error: { message: 'WaveSpeed request failed (500) Internal Error xyz', kind: 'failed' } }
const out: Record<string, unknown> = {}
for (const lang of ['zh', 'en'] as const) {
  setLang(lang)
  out[lang] = {
    kinds: Object.fromEntries(kinds.map((k) => [k, wsErrorText(k)])),
    raw: wsBodyError(raw, 'x'),
    untagged: wsBodyError({ error: { message: 'mask file not found' } }, 'x'),
    plain: wsBodyError({ error: 'src must be a /api/view URL' }, 'x'),
    unknown: wsErrorText('nope'),
    agent: agentError(wsErrorText('insufficientCredit')!),
    agentThrown: agentErrorText(wsErrorText('insufficientCredit')!),
    timeout: wsErrorText('timeout', 0.32),
    timeoutNoAmount: wsErrorText('timeout'),
    unregisteredModel: wsErrorText('unregisteredModel'),
    noTaskId: wsErrorText('noTaskId', 0.1),
    tiny: wsErrorText('noOutput', 0.004),
    zero: wsErrorText('timeout', 0),
    zeroNoTaskId: wsErrorText('noTaskId', 0),
    cent: wsErrorText('timeout', 0.01),
    timeoutId: wsErrorText('timeout', 0.32, 'ws-abc123'),
    noOutputId: wsErrorText('noOutput', undefined, 'ws-abc123'),
    noTaskIdWithId: wsErrorText('noTaskId', 0.32, 'ws-abc123'),
    bodyId: wsBodyError({ error: { message: 'x', kind: 'timeout', charged_usd: 0.32, task_id: 'ws-abc123' } }, 'x'),
    timeoutBody: wsBodyError({ error: { message: 'WaveSpeed task timed out, may have been charged about (quoted price) $1.5', kind: 'timeout', charged_usd: 1.5 } }, 'x'),
  }
}
out.fmtUsd = [0.1, 0.14, 1.5, 0.32, 0.004, 0.009, 0, 0.01, 2.005, 12].map(fmtUsd)
console.log(JSON.stringify(out))
