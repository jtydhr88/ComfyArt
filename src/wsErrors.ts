// #155: WaveSpeed failures are shown as readable zh/en messages, never the raw WaveSpeed error text.
import { t } from './i18n'

/** #715: text right before the `id` in wsErr.taskRef (zh/en); a code span after one of these renders as .ca-task-id. */
export const TASK_REF_PREFIXES = ['任务编号：', 'Task ID: ']
export const isTaskRefCode = (before: string) => TASK_REF_PREFIXES.some((p) => before.endsWith(p))

export const TOP_UP_URL = 'https://wavespeed.ai/top-up'
const KINDS = ['insufficientCredit', 'moderation', 'rateLimit', 'invalidKey', 'network', 'failed', 'timeout', 'loraUrl', 'loraUnsupported', 'loraTooMany', 'noOutput', 'noTaskId', 'unregisteredModel'] as const
export type WsErrorKind = typeof KINDS[number]

/** The readable message for a backend error kind, or null when the error is not a tagged WaveSpeed failure. */
export function wsErrorText(kind: unknown, charged?: unknown, taskId?: unknown): string | null {
  if (typeof kind !== 'string' || !(KINDS as readonly string[]).includes(kind)) return null
  // #174: a timed-out task may still be billed; show the quoted amount when known, never auto-retry
  // #712: a run that may be billed with no image (no output / no task id) states the reason and the amount
  if (kind === 'timeout' || kind === 'noOutput' || kind === 'noTaskId') {
    const amt = typeof charged === 'number' && Number.isFinite(charged) ? fmtUsd(charged) : null
    // #715: '$0.00' / '< $0.01' are not estimates -> drop 「约」/'about' in front of them
    const base = amt === null ? t(`wsErr.${kind}NoAmount`)
      : charged as number < 0.01 ? t(`wsErr.${kind}`, amt).replace(`约 ${amt}`, ` ${amt}`).replace(`about ${amt}`, amt) : t(`wsErr.${kind}`, amt)
    // #712: when a task id was obtained (timeout / noOutput) show it for feedback or refunds; noTaskId has none
    return kind !== 'noTaskId' && typeof taskId === 'string' && taskId.trim() ? `${base}\n\n${t('wsErr.taskRef', `\`${taskId.trim()}\``)}` : base  // #715 design: own line; id as `code` (nowrap, copyable)
  }
  return kind === 'insufficientCredit' ? t('wsErr.insufficientCredit', TOP_UP_URL) : t(`wsErr.${kind}`)
}

/** `{ error: { message, kind } }` bodies from /comfyart/wavespeed/* and /comfyart/ocr. */
/** #712: always 2 decimals ($0.10, $0.14); a positive amount under one cent reads '< $0.01'. */
export const fmtUsd = (n: number) => (n > 0 && n < 0.01 ? '< $0.01' : `$${n.toFixed(2)}`)

export function wsBodyError(body: any, fallback: string): string {
  const err = body?.error
  // never stringify an object into "[object Object]": only string text passes through, otherwise the localized fallback
  return wsErrorText(err?.kind, err?.charged_usd, err?.task_id) ?? (typeof err === 'string' && err.trim() ? err : typeof err?.message === 'string' && err.message.trim() ? err.message : fallback)
}

export const RELAY_NOTE = 'user_message is already in the user\'s language; reply with it word for word (keep any link), do not paraphrase or quote a raw error'

/** Agent tool result for a failed generation: the agent must relay our zh/en copy verbatim (#155 follow-up). */
export function agentError(message: string) {
  return { error: message, user_message: message, note: RELAY_NOTE }
}

/** Thrown tool errors carry the same relay instruction. */
export function agentErrorText(message: string): string {
  return `${message}\n[${RELAY_NOTE.replace('user_message', 'this message')}]`
}
