import { useEffect } from 'react'
import { atom, useValue } from 'tldraw'

import { BUILTIN_AGENT, chatIdAtom, chatsAtom, defaultProvider, lostProvider, NO_KEY_DETAIL, providerLabel, messagesAtom, newProviderAtom, openChat, providersAtom, providersStateAtom, saveSettings, settingsAtom, updateChat, type ProviderInfo } from '../bot'
import { errorText } from '../jobs'
import { confirmAtom } from './Confirm'
import { AgentLogo } from './agentLogos'
import { FieldSelect } from './FieldSelect'
import { Icons } from './icons'
import { t } from '../i18n'

export const botSettingsOpenAtom = atom('bot settings open', false)
// #247: which tool card the Agent settings should scroll to when opened from 去配置
export const agentSetupFocusAtom = atom<string | null>('agent setup focus', null)

// #585: last resolved agent pill (id + display shortLabel) so /bot/status loading can reuse icon+label
export const AGENT_LABEL_CACHE_KEY = 'comfyart.lastAgentLabel'
type AgentLabelCache = { id: string; shortLabel: string }

/** #585: humanize an agent id when no product/server short label exists — never show raw id (e.g. claude-code). */
export function safeAgentDisplayName(id: string): string {
  const parts = id.split(/[-_]/).filter(Boolean)
  if (!parts.length) return t('agentPicker.builtinAgentShort')
  return parts.map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

export function readAgentLabelCache(): AgentLabelCache | null {
  try {
    const raw = localStorage.getItem(AGENT_LABEL_CACHE_KEY)
    if (!raw) return null
    const o = JSON.parse(raw) as unknown
    if (!o || typeof o !== 'object' || Array.isArray(o)) return null
    const id = (o as { id?: unknown }).id
    const short = (o as { shortLabel?: unknown }).shortLabel
    if (typeof id !== 'string' || !id.trim()) return null
    if (typeof short !== 'string' || !short.trim()) return null
    const trimmedId = id.trim()
    const trimmedShort = short.trim()
    // refuse a cached label that is just the raw id
    return { id: trimmedId, shortLabel: trimmedShort === trimmedId ? safeAgentDisplayName(trimmedId) : trimmedShort }
  } catch {
    return null
  }
}

export function writeAgentLabelCache(entry: AgentLabelCache) {
  try {
    const id = entry.id.trim()
    const shortLabel = entry.shortLabel.trim()
    if (!id || !shortLabel) return
    localStorage.setItem(AGENT_LABEL_CACHE_KEY, JSON.stringify({
      id,
      shortLabel: shortLabel === id ? safeAgentDisplayName(id) : shortLabel,
    }))
  } catch { /* private mode / quota */ }
}

// #219: the composer bar shows a short name; the full name stays in the list and on hover
const SHORT_LABELS: Record<string, string> = { 'deepseek-harness': 'DeepSeek' }
// built-in first, then detected tools, then undetected ones
const rank = (p: ProviderInfo) => (p.id === BUILTIN_AGENT ? 0 : p.available ? 1 : 2)
export const shortLabel = (p: ProviderInfo) => {
  if (p.id === BUILTIN_AGENT) return t('agentPicker.builtinAgentShort')
  if (SHORT_LABELS[p.id]) return SHORT_LABELS[p.id]
  const L = (p.label || '').trim()
  // #585: never fall through to a raw id even when server/product shortLabel is missing
  if (L && L !== p.id) return L
  return safeAgentDisplayName(p.id)
}

// #324: off-row title prefers provider.detail; empty → docs「未检测到 · 去配置」
export function offRowTitle(p: ProviderInfo) {
  const d = (p.detail || '').trim()
  if (d && d !== NO_KEY_DETAIL) return d
  return `${t('agentPicker.notDetected')} · ${t('agentSetup.setUp')}`
}
// #324: visible one-line reason — probe miss stays short i18n; keep other details as-is
export function offRowReason(p: ProviderInfo) {
  const d = (p.detail || '').trim()
  if (!d || d === NO_KEY_DETAIL || /executable not found/i.test(d)) return t('agentPicker.notDetected')
  return d
}

// #246: the agent list lives in the composer mode menu; same items, ✓, #220 disabled/confirm rules
export function useCurrentAgent() {
  const providers = useValue(providersAtom)
  const chat = useValue('current chat', () => chatsAtom.get().find((c) => c.id === chatIdAtom.get()) ?? null, [])
  const pending = useValue(newProviderAtom)
  const providerId = chat?.provider ?? (pending || defaultProvider())
  const loading = useValue('agent list loading', () => providersStateAtom.get().state === 'loading', [])
  const found = providers.find((p) => p.id === providerId) ?? null
  // #585: persist last resolved label+icon when /bot/status succeeds so the next load can paint it immediately
  useEffect(() => {
    if (!found) return
    writeAgentLabelCache({ id: found.id, shortLabel: shortLabel(found) })
  }, [found?.id, found?.label])
  // #557/#585: while the provider list is still loading, show the last cached agent (or Loomi on first open)
  // instead of the generic mode fallback / raw id, so the pill never flashes.
  if (!found && loading) {
    const cached = readAgentLabelCache()
    if (cached) return { ...LOADING_AGENT, id: cached.id, label: cached.shortLabel }
    return { ...LOADING_AGENT, id: BUILTIN_AGENT, label: '' }
  }
  return found
}

const LOADING_AGENT: ProviderInfo = { id: BUILTIN_AGENT, label: '', available: true, version: '', detail: '', logged_in: null, stateful: false, attachments: false, branch: false, models: [] }

export function AgentItems({ onError, current, close, onChosen }: { onError: (msg: string) => void; current: boolean; close: () => void; onChosen: () => void }) {
  const providers = useValue(providersAtom)
  const chat = useValue('current chat', () => chatsAtom.get().find((c) => c.id === chatIdAtom.get()) ?? null, [])
  const started = useValue('chat started', () => messagesAtom.get().length > 0, [])
  const pending = useValue(newProviderAtom)
  const providerId = chat?.provider ?? (pending || defaultProvider())
  const provider = providers.find((p) => p.id === providerId)
  const fail = (e: unknown) => onError(errorText(e))
  const lost = lostProvider()
  const choose = (id: string) => {
    onChosen()
    if (id === providerId) return
    newProviderAtom.set(id)
    void saveSettings({ 'bot-provider': id }).catch(fail)
    if (chat && started) void openChat(null)
  }
  const pick = (id: string) => {
    close()
    if (id === BUILTIN_AGENT || id === providerId || settingsAtom.get()['enable-mcp'] === true) return choose(id)
    confirmAtom.set({
      title: t('agentPicker.enableMcpTitle'),
      desc: t('agentPicker.enableMcpConfirm'),
      ok: t('agentPicker.enableMcpOk'),
      run: () => { void saveSettings({ 'enable-mcp': true }).then(() => choose(id)).catch(fail) },
    })
  }
  return (
    <>
      <div className="ca-agentpick__list">
      {[...providers].sort((x, y) => rank(x) - rank(y)).map((p) => !p.available && p.id !== BUILTIN_AGENT ? (
        // #247: an undetected tool can't be picked; the whole row (40%) opens its setup card instead
        <button key={p.id} type="button" className="ca-menu__item ca-agentpick__row ca-agentpick__off" title={offRowTitle(p)} onClick={() => { close(); agentSetupFocusAtom.set(p.id); botSettingsOpenAtom.set(true) }}>
          <AgentLogo id={p.id} />
          <span className="ca-agentpick__text"><span className="ca-agentpick__name">{providerLabel(p)}</span><span className="ca-agentpick__status">{offRowReason(p)}</span></span>
          <span className="ca-agentpick__check"><span className="ca-agentpick__setup">{t('agentSetup.setUp')}</span></span>
        </button>
      ) : (
        <button key={p.id} type="button" className="ca-menu__item ca-agentpick__row" disabled={!p.available} title={p.detail || p.version} onClick={() => pick(p.id)}>
          <AgentLogo id={p.id} />
          <span className="ca-agentpick__text"><span className="ca-agentpick__name">{providerLabel(p)}</span>{!p.available && <span className="ca-agentpick__status">{t('botSettings.unavailable')}</span>}</span>
          <span className="ca-agentpick__check">{current && p.id === providerId ? <span className="ca-icon">{Icons.check}</span> : null}</span>
        </button>
      ))}
      </div>
      {provider && !provider.available && provider.detail && provider.detail !== NO_KEY_DETAIL && <div className="ca-chat__hint">{provider.detail}</div>}
      {lost && <div className="ca-chat__hint">{t('agentPicker.fellBackToBuiltin', providerLabel(lost))}</div>}
      {chat && started && <div className="ca-chat__hint">{t('agentPicker.switchingAgentStartsANew')}</div>}
    </>
  )
}

// #246: what the old Agent button's menu had below the list (model, ask-before-generating, Agent settings); shown in agent mode only
export function AgentExtras({ onError, close }: { onError: (msg: string) => void; close: () => void }) {
  const providers = useValue(providersAtom)
  const settings = useValue(settingsAtom)
  const chat = useValue('current chat', () => chatsAtom.get().find((c) => c.id === chatIdAtom.get()) ?? null, [])
  const pending = useValue(newProviderAtom)
  const providerId = chat?.provider ?? (pending || defaultProvider())
  const provider = providers.find((p) => p.id === providerId)
  const modelKey = `bot-model-${providerId}`
  const model = String(settings[modelKey] ?? '')
  const options = provider?.model_options ?? provider?.models.map((m) => ({ value: m, label: m, group: '' })) ?? []
  const fail = (e: unknown) => onError(errorText(e))
  // #349: shared FieldSelect (same bot-model-* source for Home + canvas; #316 tokens via .ca-fieldselect)
  const fieldOptions = [
    { id: '', label: t('common.default') },
    ...options.map((o) => ({
      id: o.value,
      label: o.group ? `${o.group} · ${o.label}` : o.label,
      title: o.value,
    })),
  ]
  return (
    <>
      {options.length > 0 && (
        <div className="ca-agentpick__section">
          <div className="ca-agentpick__sectiontitle">{t('agentPicker.model')}</div>
          <FieldSelect
            value={model}
            options={fieldOptions}
            onChange={(value) => { void saveSettings({ [modelKey]: value }).catch(fail) }}
            placeholder={t('common.default')}
            menuClassName="ca-agentpick__modelmenu"
          />
        </div>
      )}
      <label className="ca-agentpick__ask" data-disabled={!chat || undefined}>
        <input
          type="checkbox"
          checked={chat?.run_mode === 'ask'}
          disabled={!chat}
          onChange={(e) => chat && void updateChat(chat.id, { run_mode: e.target.checked ? 'ask' : 'auto' }).catch(fail)}
        />
        <span>{t('agentPicker.askBeforeGenerating', chat ? '' : t('agentPicker.availableAfterTheFirstMessage'))}</span>
      </label>
      <button type="button" className="ca-menu__item" onClick={() => { close(); botSettingsOpenAtom.set(true) }}>
        <span className="ca-icon">{Icons.adjust}</span><span className="ca-menu__grow">{t('agentPicker.agentSettings')}</span>
      </button>
    </>
  )
}
