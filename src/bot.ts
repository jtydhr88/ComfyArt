import { atom, react } from 'tldraw'

import { api, setAgentPlanConfirmed } from './comfy'
import { resultsAtom } from './jobs'
import { notify } from './notices'
import { onComfyEvent, onReconnect } from './ws'
import { lang, t } from './i18n'
import { wsBodyError } from './wsErrors'
import { handleScheduleTurnDone, isSchedulePending, noteScheduleNotify } from './schedulePending'

export interface AskOption { id: string; label: string; description?: string; recommended?: boolean }
export interface AskQuestion {
  id: string
  prompt: string
  options?: AskOption[]
  min_selections?: number
  max_selections?: number
  allow_other?: boolean
  defaults?: string[]
  page?: number
  placeholder?: string
}
export type AskAnswers = Record<string, { selected: string[]; other_text?: string }>
export interface BotBlock {
  type: string
  text?: string
  name?: string
  input?: Record<string, any>
  id?: string
  status?: string
  duration_ms?: number
  url?: string
  shape?: string
  level?: string
  ask_id?: string
  prompt?: string
  options?: AskOption[]
  min_selections?: number
  max_selections?: number
  allow_other?: boolean
  allow_skip?: boolean
  defaults?: string[]
  page?: number
  page_count?: number
  questions?: AskQuestion[]
  answers?: AskAnswers
  kind?: string
  lines?: { text: string; price: string }[]
  total?: string
  total_label?: string
  selected?: string[]
  other_text?: string
  label?: string
  holder?: string
  srcs?: string[]
  error?: string
  detail?: Record<string, any>
  // #382 memory-updated row
  memory_ids?: string[]
  /** #413: id of the memory tool call that wrote it (in-loop write) */
  tool_id?: string
  /** #423: every memory call merged into this turn's one row */
  tool_ids?: string[]
  /** #423: ids in memory_ids that were updates of an existing memory */
  updated_ids?: string[]
  count?: number
  texts?: string[]
  // #391 run_stop card
  run_id?: string
  stop?: { reason: string; sub?: string; dimension?: string; detail?: string; step?: number }
  done?: string[]
  remaining?: { deliverables: number; kind: string; steps: number }
  details?: { zh: string[]; en: string[] }
  copy?: RunStopCopy
  self_check?: Record<string, any>
  can_continue?: boolean
  /** #419: user stop only: paid jobs this turn had already submitted (they still finish and are charged) */
  submitted?: number
  notify?: boolean
}
export interface RunStopText { title: string; body: string; primary: string | null; secondary: string | null; reason?: string; continue?: string }
export interface RunStopCopy { key: string; action: 'continue' | 'rephrase' | 'retry'; tone: 'ok' | 'warn' | 'error' | 'neutral'; zh: RunStopText; en: RunStopText }
export interface RunBudgetMeter { used: number; limit: number; pct: number }
export interface RunBudgetView { run_id?: string; step: number; hard_cap: number; tokens: RunBudgetMeter; credits: RunBudgetMeter; time: RunBudgetMeter; soft: boolean }
/** #391: live budget bar of the running turn, per chat (not persisted; the stop card keeps the final numbers). */
export const runBudgetAtom = atom<Record<string, RunBudgetView>>('bot run budget', {})
export interface BotUsage { input_tokens?: number; output_tokens?: number; cache_read_input_tokens?: number; cost_usd?: number }
export interface BotMessage { id: string; chat_id: string; parent_id: string | null; role: 'user' | 'assistant'; blocks: BotBlock[]; status: string; usage: BotUsage | null; created_at: number }
export interface BotChat { id: string; user: string; project: string; title: string; provider: string; run_mode: 'auto' | 'ask'; pinned: boolean; archived: boolean; busy?: boolean; created_at: number; updated_at: number }
export interface ModelOption { value: string; label: string; group: string }
export interface ProviderInfo { id: string; label: string; available: boolean; version: string; detail: string; logged_in: boolean | null; stateful: boolean; attachments: boolean; branch: boolean; models: string[]; model_options?: ModelOption[] }
export type BotSettings = Record<string, string | boolean | number>

export const TOOL_LABELS: Record<string, string> = {
  ToolSearch: t('bot.findTools'),
  tool_search: t('bot.findTools'),
  server_info: t('bot.checkStatus'),
  get_canvas: t('bot.viewCanvas'),
  view_canvas: t('bot.lookAtCanvas'),
  view_video: t('bot.watchVideo'),
  list_models: t('bot.viewModels'),
  brand_kits: t('bot.viewBrandKit'),
  generate_image: t('bot.generateImage'),
  generate_video: t('bot.generateVideo'),
  edit_image: t('bot.editImage'),
  animate_image: t('common.animateImage'),
  upscale_image: t('common.upscale'),
  remove_background: t('common.removeBackground'),
  expand_image: t('bot.expandImage'),
  split_layers: t('common.splitLayers'),
  change_angle: t('common.multiAngle'),
  replace_text: t('common.editText'),
  edit_region: t('common.inpaint'),
  erase_region: t('common.eraser'),
  move_object: t('common.moveObject'),
  style_transfer: t('common.styleTransfer'),
  vectorize_image: t('imageToolbar.vectorize'),
  extend_video: t('common.extendVideo'),
  upscale_video: t('actions.upscaleVideo'),
  remove_video_background: t('common.removeBackground'),
  generate_music: t('audio.music'),
  generate_sound_effect: t('audio.soundEffect'),
  text_to_speech: t('audio.voiceover'),
  edit_elements: t('imageToolbar.editElements'),
  create_mockup: t('mockup.title'),
  place_design: t('mockup.design'),
  image_to_3d: t('imageToolbar.imageTo3d'),
  wait_generation: t('bot.waitForResults'),
  place_html: t('bot.placeWebPage'),
  create_slides: t('bot.createPpt'),
  add_text: t('bot.addText'),
  add_shape: t('bot.addShape'),
  create_frame: t('bot.createArtboard'),
  update_shapes: t('bot.adjustElements'),
  delete_shapes: t('bot.deleteElements'),
  focus: t('bot.locateElements'),
  memory: t('common.memory'),
  skill: t('bot.skill'),
  custom_workflow: t('customWorkflows.title'),
  ask_user: t('bot.askYou'),
  update_plan: t('bot.plan'),
}

export const toolName = (name = '') => name.replace(/^mcp__\w+__/, '')
export const toolLabel = (name?: string) => TOOL_LABELS[toolName(name)] ?? toolName(name)

export const providersAtom = atom<ProviderInfo[]>('bot providers', [])
export const botEnabledAtom = atom<boolean | null>('bot enabled', null)
export const settingsAtom = atom<BotSettings>('bot settings', {})
export const chatsAtom = atom<BotChat[]>('bot chats', [])
export const chatIdAtom = atom<string | null>('bot chat id', null)
export const messagesAtom = atom<BotMessage[]>('bot messages', [])
export const newProviderAtom = atom<string>('bot new provider', '')
/** #294: whether the Agent list has arrived. 'loading' until the first /bot/status answers; on failure, the real error text. */
export const providersStateAtom = atom<{ state: 'loading' | 'ready' | 'error'; error?: string }>('bot providers state', { state: 'loading' })

let project = ''
let me = ''

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await api(path, init)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(wsBodyError(body, t('err.requestFailed', res.status)))
  return body as T
}

const send = (body: unknown, method = 'POST'): RequestInit => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export async function loadProviders(opts?: { refresh?: boolean }) {
  // #247: 「重新检测」passes refresh so the server drops the 60s probe cache
  const q = opts?.refresh ? '?refresh=1' : ''
  let status: { enabled: boolean; user: string; providers: ProviderInfo[] }
  try {
    status = await json<{ enabled: boolean; user: string; providers: ProviderInfo[] }>(`/comfyart/bot/status${q}`)
  } catch (e) {
    // #294: keep an already-loaded list on a failed re-check; only the first load reports the error to send
    if (providersStateAtom.get().state !== 'ready') providersStateAtom.set({ state: 'error', error: e instanceof Error ? e.message : String(e) })
    throw e
  }
  providersStateAtom.set({ state: 'ready' })
  me = status.user
  botEnabledAtom.set(status.enabled)
  // #661: same class of crash as chats — AgentPanel providers.find on undefined
  providersAtom.set(status.providers ?? [])
}

function applySettings(settings: BotSettings) {
  settingsAtom.set(settings)
}

export async function loadSettings() {
  applySettings(await json<BotSettings>('/comfyart/settings'))
}

export async function saveSettings(patch: BotSettings) {
  applySettings(await json<BotSettings>('/comfyart/settings', send(patch, 'PUT')))
}

/** #321: probe Local LLM URL / key / model without sending a chat turn. */
export type LocalLlmTestCode = 'ok' | 'no_url' | 'unreachable' | 'auth_failed' | 'model_missing' | 'timeout'
export type LocalLlmTestResult = { ok: boolean; code: LocalLlmTestCode; model?: string; status?: number; models?: string[]; detail?: string }
export async function testLocalLlm(draft: { url?: string; key?: string; model?: string }) {
  return json<LocalLlmTestResult>('/comfyart/bot/local-llm/test', send(draft))
}


export function defaultProvider(): string {
  const providers = providersAtom.get()
  const saved = String(settingsAtom.get()['bot-provider'] ?? '')
  // #219: the built-in agent is the default; a remembered external tool that is no longer detected falls back to it
  return providers.find((p) => p.id === saved && p.available)?.id ?? providers.find((p) => p.id === BUILTIN_AGENT)?.id ?? providers.find((p) => p.available)?.id ?? providers[0]?.id ?? ''
}

export const BUILTIN_AGENT = 'local-llm'
export const NO_KEY_DETAIL = 'no-wavespeed-key'

export const providerLabel = (p: ProviderInfo) => (p.id === BUILTIN_AGENT ? t('agentPicker.builtinAgent') : p.label)

/** #219: the remembered external tool that is gone, so the picker can say it fell back to the built-in agent. */
export function lostProvider(): ProviderInfo | null {
  const saved = String(settingsAtom.get()['bot-provider'] ?? '')
  const p = providersAtom.get().find((x) => x.id === saved)
  return p && !p.available && saved !== BUILTIN_AGENT ? p : null
}

export const currentChat = () => (chatsAtom.get() ?? []).find((c) => c.id === chatIdAtom.get()) ?? null
export const busy = () => !!currentChat()?.busy

export async function loadChats() {
  // #661: never set chatsAtom to undefined — a body without `chats` used to white-screen AgentPanel (.find)
  chatsAtom.set((await json<{ chats: BotChat[] }>(`/comfyart/bot/chats?project=${encodeURIComponent(project)}`)).chats ?? [])
}

/** #387: merge server pending asks into messages after refresh/reconnect. */
function mergePendingAsks(messages: BotMessage[], asks: Array<BotBlock & { message_id?: string }>): BotMessage[] {
  if (!asks.length) return messages
  const byId = new Map(asks.filter((a) => a.ask_id).map((a) => [a.ask_id!, a]))
  const seen = new Set<string>()
  const out = messages.map((m) => {
    let changed = false
    const blocks = m.blocks.map((b) => {
      if (b.type !== 'ask' || !b.ask_id || !byId.has(b.ask_id)) return b
      seen.add(b.ask_id)
      if (b.status === 'pending') return b
      changed = true
      const a = byId.get(b.ask_id)!
      const { message_id: _mid, ...rest } = a as BotBlock & { message_id?: string }
      return { ...rest, type: 'ask' as const, status: 'pending' as const }
    })
    return changed ? { ...m, blocks } : m
  })
  const missing = asks.filter((a) => a.ask_id && !seen.has(a.ask_id))
  if (!missing.length) return out
  const byMsg = new Map<string, typeof missing>()
  for (const a of missing) {
    const mid = a.message_id || ''
    if (!byMsg.has(mid)) byMsg.set(mid, [])
    byMsg.get(mid)!.push(a)
  }
  return out.map((m) => {
    const extra = byMsg.get(m.id)
    if (!extra?.length) return m
    const blocks = extra.map((a) => {
      const { message_id: _mid, ...rest } = a
      return { ...rest, type: 'ask' as const, status: 'pending' as const }
    })
    return { ...m, blocks: [...m.blocks, ...blocks] }
  })
}

export async function openChat(id: string | null) {
  chatIdAtom.set(id)
  if (!id) return messagesAtom.set([])
  const { chat, messages } = await json<{ chat: BotChat; messages: BotMessage[] }>(`/comfyart/bot/chats/${id}`)
  if (chatIdAtom.get() !== id) return
  upsertChat(chat)
  let merged = messages
  try {
    const { asks } = await json<{ asks: BotBlock[] }>(`/comfyart/bot/chats/${id}/asks`)
    if (asks?.length) merged = mergePendingAsks(messages, asks)
  } catch {
    /* list is best-effort; messages alone usually already hold pending blocks */
  }
  if (chatIdAtom.get() !== id) return
  messagesAtom.set(merged)
}

function upsertChat(chat: BotChat) {
  if (chat.project !== project || chat.user !== me) return
  const list = chatsAtom.get() ?? []
  chatsAtom.set(list.some((c) => c.id === chat.id) ? list.map((c) => (c.id === chat.id ? { ...c, ...chat } : c)) : [chat, ...list])
}

async function ensureChat(): Promise<BotChat> {
  const current = currentChat()
  if (current) return current
  const provider = newProviderAtom.get() || defaultProvider()
  if (!provider) {
    // #294: never claim "no Agent" while the list is still loading or when loading it failed
    const ps = providersStateAtom.get()
    if (ps.state === 'loading') throw new Error(t('bot.agentListLoading'))
    if (ps.state === 'error') throw new Error(t('bot.agentListLoadFailed', ps.error ?? ''))
    throw new Error(t('bot.noAgentAvailableConfigureOne'))
  }
  const { chat } = await json<{ chat: BotChat }>('/comfyart/bot/chats', send({ project, provider }))
  upsertChat(chat)
  chatIdAtom.set(chat.id)
  messagesAtom.set([])
  return chat
}

export interface SendInput { text: string; refs: { id: string; src: string; name: string; kind: 'image' | 'video' | 'audio'; transcript?: string }[]; docs: { src: string; name: string }[]; kits: { name: string; description: string; images: string[] }[]; skill?: string; /** #491: display-only chip (e.g. 技能创建器) — shown in the bubble, never sent as a skill to read */ chip?: string; memory?: string; context?: string; /** #388 turn mode (interactive|unattended); not chat auto|ask */ run_mode?: 'interactive' | 'unattended' }

export async function sendMessage(input: SendInput) {
  const chat = await ensureChat()
  await json(`/comfyart/bot/chats/${chat.id}/send`, send({ ...input, lang }))  // #132: server-side replies (loop-guard stop) follow the UI language
}

export async function logDirect(text: string, blocks: BotBlock[]) {
  const chat = await ensureChat()
  await json(`/comfyart/bot/chats/${chat.id}/log`, send({ text, blocks }))
}

export async function stopTurn() {
  const chat = currentChat()
  if (chat?.busy) await json(`/comfyart/bot/chats/${chat.id}/stop`, { method: 'POST' })
}

/** #391: resume a paused run from its server-side checkpoint (409 when another Continue won). */
export async function continueRun(runId: string, lang: string) {
  await json(`/comfyart/bot/runs/${runId}/continue`, send({ lang }))
}

export async function answerAsk(askId: string, selected: string[], other: string, answers?: AskAnswers) {
  const chat = currentChat()
  if (!chat) return
  const body: Record<string, unknown> = { selected, other_text: other }
  if (answers !== undefined) body.answers = answers
  await json(`/comfyart/bot/chats/${chat.id}/asks/${askId}/answer`, send(body))
}

export async function updateChat(id: string, patch: Partial<Pick<BotChat, 'title' | 'run_mode' | 'pinned' | 'archived'>>) {
  upsertChat((await json<{ chat: BotChat }>(`/comfyart/bot/chats/${id}`, send(patch, 'PATCH'))).chat)
}

export async function deleteChat(id: string) {
  await json(`/comfyart/bot/chats/${id}`, { method: 'DELETE' })
  chatsAtom.set((chatsAtom.get() ?? []).filter((c) => c.id !== id))
  if (chatIdAtom.get() === id) await openChat(null)
}

export async function branchFrom(messageId: string) {
  const chat = currentChat()
  if (!chat) return
  const { chat: branch, messages } = await json<{ chat: BotChat; messages: BotMessage[] }>(`/comfyart/bot/chats/${chat.id}/branch`, send({ message_id: messageId }))
  upsertChat(branch)
  chatIdAtom.set(branch.id)
  messagesAtom.set(messages)
}

function patchMessages(chatId: string, messageId: string, fn: (m: BotMessage) => BotMessage) {
  if (chatIdAtom.get() !== chatId) return
  messagesAtom.set(messagesAtom.get().map((m) => (m.id === messageId ? fn(m) : m)))
}

/** #382: insert 「记忆已更新 ›」 between thinking and reply; persist via PATCH. */
export async function announceMemoryUpdated(chatId: string, messageId: string, memories: { id: string; text: string }[]) {
  if (!memories.length) return
  const { insertMemoryUpdatedBlock } = await import('./memoryBudget')
  const apply = (m: BotMessage): BotMessage => ({
    ...m,
    blocks: insertMemoryUpdatedBlock(m.blocks as any, {
      memory_ids: memories.map((x) => x.id),
      texts: memories.map((x) => x.text),
    }) as BotBlock[],
  })
  patchMessages(chatId, messageId, apply)
  const local = messagesAtom.get().find((m) => m.id === messageId)
  if (!local) return
  try {
    await api(`/comfyart/bot/chats/${chatId}/messages/${messageId}`, send({ blocks: local.blocks }, 'PATCH'))
  } catch { /* offline: local row still shows for this session */ }
}

function appendBlock(m: BotMessage, block: BotBlock): BotMessage {
  return { ...m, blocks: [...m.blocks, block] }
}

export function outputsOf(blocks: BotBlock[]): string[] {
  const urls: string[] = []
  for (const b of blocks) {
    if (b.type === 'task') urls.push(...(b.srcs ?? []))
    if (b.type === 'tool_result' && toolName(b.name) === 'wait_generation') urls.push(...(b.text?.match(/\/api\/view\?[^"\s\\]*type=\w+/g) ?? []))
  }
  return [...new Set(urls)]
}

const reducers: Record<string, (e: any) => void> = {
  chat_created: (e) => upsertChat(e.chat),
  chat_updated: (e) => upsertChat(e.chat),
  chat_deleted: (e) => {
    chatsAtom.set((chatsAtom.get() ?? []).filter((c) => c.id !== e.chat_id))
    if (chatIdAtom.get() === e.chat_id) void openChat(null)
  },
  messages_logged: (e) => {
    if (chatIdAtom.get() === e.chat_id) messagesAtom.set([...messagesAtom.get(), ...e.messages])
  },
  message_queued: (e) => {
    if (chatIdAtom.get() === e.chat_id) messagesAtom.set([...messagesAtom.get(), e.user_message])
  },
  turn_start: (e) => {
    setAgentPlanConfirmed(false)
    chatsAtom.set((chatsAtom.get() ?? []).map((c) => (c.id === e.chat_id ? { ...c, busy: true } : c)))
    if (chatIdAtom.get() !== e.chat_id) return
    const rest = messagesAtom.get().filter((m) => m.id !== e.user_message.id)
    messagesAtom.set([...rest, e.user_message, e.assistant_message])
  },
  turn_delta: (e) => patchMessages(e.chat_id, e.message_id, (m) => {
    const last = m.blocks.at(-1)
    return last?.type === 'text' ? { ...m, blocks: [...m.blocks.slice(0, -1), { ...last, text: (last.text ?? '') + e.text }] } : appendBlock(m, { type: 'text', text: e.text })
  }),
  turn_thinking: (e) => patchMessages(e.chat_id, e.message_id, (m) => {
    const last = m.blocks.at(-1)
    return last?.type === 'thinking' ? { ...m, blocks: [...m.blocks.slice(0, -1), { ...last, text: (last.text ?? '') + e.text }] } : appendBlock(m, { type: 'thinking', text: e.text })
  }),
  turn_tool_use: (e) => patchMessages(e.chat_id, e.message_id, (m) => appendBlock(m, { type: 'tool_use', name: e.name, input: e.input, id: e.id })),
  turn_tool_result: (e) => patchMessages(e.chat_id, e.message_id, (m) => {
    const next = appendBlock(m, { type: 'tool_result', name: e.name, text: e.text, status: e.status, id: e.id, duration_ms: e.duration_ms })
    if (!e.memory_updated) return next
    // #423: one 记忆已更新 › row per turn — a merged add replaces the row in place
    const at = next.blocks.findIndex((b) => b.type === 'memory_updated')
    return at < 0 ? appendBlock(next, e.memory_updated) : { ...next, blocks: next.blocks.map((b, i) => (i === at ? e.memory_updated! : b)) }
  }),
  turn_retry: (e) => patchMessages(e.chat_id, e.message_id, (m) => appendBlock(m, e.block)),
  turn_run_budget: (e) => runBudgetAtom.set({ ...runBudgetAtom.get(), [e.chat_id]: e.budget }),
  turn_run_stop: (e) => patchMessages(e.chat_id, e.message_id, (m) => appendBlock(m, e.block)),
  turn_notify: (e) => {
    patchMessages(e.chat_id, e.message_id, (m) => appendBlock(m, e.block))
    // #388: schedule unattended turns own the notice (已跳过 / started) — suppress suggestion
    if (isSchedulePending(e.chat_id)) {
      noteScheduleNotify(e.chat_id, e.block?.text ?? '')
      return
    }
    if ((chatsAtom.get() ?? []).some((c) => c.id === e.chat_id)) void notify({ kind: 'suggestion', title: t('bot.runNeedsYou'), body: e.block?.text ?? '', chat: e.chat_id })
  },
  turn_ask: (e) => {
    patchMessages(e.chat_id, e.message_id, (m) => appendBlock(m, { type: 'ask', status: 'pending', ...e }))
    if ((chatsAtom.get() ?? []).some((c) => c.id === e.chat_id)) void notify({ kind: 'suggestion', title: t('bot.agentIsWaitingForYour'), body: e.prompt, chat: e.chat_id })
  },
  turn_ask_resolved: (e) => patchMessages(e.chat_id, e.message_id, (m) => ({
    ...m, blocks: m.blocks.map((b) => (b.type === 'ask' && b.ask_id === e.ask_id ? { ...b, status: e.status, selected: e.selected ?? b.selected, other_text: e.other_text ?? b.other_text, answers: e.answers ?? b.answers } : b)),
  })),
  turn_done: (e) => {
    setAgentPlanConfirmed(false)
    if (runBudgetAtom.get()[e.chat_id]) { const { [e.chat_id]: _gone, ...rest } = runBudgetAtom.get(); runBudgetAtom.set(rest) }
    const chat = (chatsAtom.get() ?? []).find((c) => c.id === e.chat_id)
    chatsAtom.set((chatsAtom.get() ?? []).map((c) => (c.id === e.chat_id ? { ...c, busy: false, ...(e.title ? { title: e.title } : {}) } : c)))
    if (chatIdAtom.get() === e.chat_id) void openChat(e.chat_id)
    // #388: schedule turns emit exactly one kind=schedule notice (skip or started)
    if (handleScheduleTurnDone(e)) return
    if (!chat || e.status === 'aborted') return
    const message = messagesAtom.get().find((m) => m.id === e.message_id)
    const text = message?.blocks.filter((b) => b.type === 'text').map((b) => b.text).join('').trim()
    void notify({
      kind: 'task',
      title: e.status === 'error' ? t('bot.agentFailed', e.title || chat.title || t('botCommands.chat')) : t('bot.agentDone', e.title || chat.title || t('botCommands.chat')),
      body: e.error || text?.slice(0, 200) || undefined,
      chat: e.chat_id,
      srcs: message ? outputsOf(message.blocks).slice(0, 4) : undefined,
    })
  },
}

function watchDirectTasks() {
  return react('direct tasks', () => {
    const results = resultsAtom.get()
    for (const m of messagesAtom.get()) {
      const pending = m.blocks.filter((b) => b.type === 'task' && !b.srcs && !b.error && b.holder && results[b.holder])
      if (!pending.length) continue
      const blocks = m.blocks.map((b) => (pending.includes(b) ? { ...b, srcs: results[b.holder!].srcs, ...(results[b.holder!].error ? { error: results[b.holder!].error } : {}) } : b))
      void api(`/comfyart/bot/chats/${m.chat_id}/messages/${m.id}`, send({ blocks }, 'PATCH'))
      patchMessages(m.chat_id, m.id, () => ({ ...m, blocks }))
    }
  })
}

export async function refreshBot(opts?: { refresh?: boolean }) {
  await Promise.all([loadProviders(opts), loadSettings()])
  if (botEnabledAtom.get()) await loadChats()
  else chatsAtom.set([])
}

export function startBot(projectId: string, isStale: () => boolean) {
  project = projectId
  void refreshBot().catch(() => {})  // #294: a failed first load is kept in providersStateAtom and shown on send
  const stops = [
    onComfyEvent('comfyart-bot', (e: { event: string }) => {
      if (!isStale()) reducers[e.event]?.(e)
    }),
    watchDirectTasks(),
    onReconnect(() => {
      if (isStale() || !botEnabledAtom.get()) return
      void loadChats().then(() => openChat(chatIdAtom.get()))
    }),
  ]
  return () => stops.forEach((stop) => stop())
}
