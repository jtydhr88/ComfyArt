import { useEffect, useState, type ReactNode } from 'react'
import { useValue } from 'tldraw'

import { BUILTIN_AGENT, botEnabledAtom, providerLabel, providersAtom, refreshBot, saveSettings, settingsAtom, testLocalLlm, type BotSettings as Settings, type LocalLlmTestCode, type ProviderInfo } from '../bot'
import { errorText } from '../jobs'
import { agentSetupFocusAtom, botSettingsOpenAtom } from './AgentPicker'
import { docsUrl } from './SettingsMenu'
import { FieldSelect } from './FieldSelect'
import { Icons } from './icons'
import { Modal } from './Modal'
import { t } from '../i18n'

// #219: the built-in agent's endpoint, model and key; the key is a password field and comes back masked
const TEXT_FIELDS: [string, string, string, ('text' | 'password')?][] = [
  ['bot-local-llm-url', t('botSettings.localLlmUrl'), t('botSettings.localLlmUrlHint')],
  ['bot-model-local-llm', t('botSettings.localLlmModel'), t('botSettings.localLlmModelHint')],
  ['bot-local-llm-key', t('botSettings.localLlmKey'), t('botSettings.localLlmKeyHint'), 'password'],
  ['bot-comfy-mcp-command', t('botSettings.comfyMcpCommand'), t('botSettings.leaveEmptyToFindComfy')],
]
const LLM_FIELD_KEYS = new Set(['bot-local-llm-url', 'bot-model-local-llm', 'bot-local-llm-key'])
const SWITCHES: [string, string][] = [
  ['enable-mcp', t('botSettings.enableMcpLetTheAgent')],
  ['enable-bot', t('botSettings.enableAgentUseCommandLine')],
]
const FLAGS: [string, string][] = [
  ['bot-enable-comfy-mcp', t('botSettings.alsoMountTheOfficialComfy')],
]

const URL_KEY = 'bot-local-llm-url'
const KEY_KEY = 'bot-local-llm-key'
const MODEL_KEY = 'bot-model-local-llm'
const WAVESPEED_HOST = 'llm.wavespeed.ai'
const hostOf = (url: unknown) => { try { return new URL(String(url ?? '').trim()).hostname.toLowerCase() } catch { return '' } }

const TEST_MSG: Record<LocalLlmTestCode, (model?: string) => string> = {
  ok: () => t('botSettings.testOk'),
  no_url: () => t('botSettings.testNoUrl'),
  unreachable: () => t('botSettings.testUnreachable'),
  auth_failed: () => t('botSettings.testAuthFailed'),
  model_missing: (model) => t('botSettings.testModelMissing', model || ''),
  timeout: () => t('botSettings.testTimeout'),
}

export function BotSettings({ onError }: { onError: (msg: string) => void }) {
  const open = useValue(botSettingsOpenAtom)
  const settings = useValue(settingsAtom)
  const providers = useValue(providersAtom)
  const enabled = useValue(botEnabledAtom)
  const [draft, setDraft] = useState<Settings>({})
  const [testing, setTesting] = useState(false)
  const [testState, setTestState] = useState<{ ok: boolean; text: string } | null>(null)
  // #345: Advanced (comfy-mcp) starts collapsed
  const [advancedOpen, setAdvancedOpen] = useState(false)
  // #219: a stored custom key belongs to its host; a new host clears it (the backend enforces the same rule)
  const hostChanged = hostOf(draft[URL_KEY]) !== hostOf(settings[URL_KEY])
  const keyCleared = hostChanged && !!settings[KEY_KEY] && hostOf(draft[URL_KEY]) !== WAVESPEED_HOST
  const edit = (key: string, value: string) => {
    const next = { ...draft, [key]: value }
    if (key === URL_KEY && hostOf(value) !== hostOf(settings[URL_KEY]) && draft[KEY_KEY] === settings[KEY_KEY]) next[KEY_KEY] = ''
    if (key === URL_KEY && hostOf(value) === hostOf(settings[URL_KEY])) next[KEY_KEY] = settings[KEY_KEY] ?? ''
    setDraft(next)
    setTestState(null)
  }

  useEffect(() => {
    if (open) void refreshBot().catch((e) => onError(errorText(e)))
  }, [open])

  useEffect(() => { setDraft(settings); setTestState(null) }, [settings])

  if (!open) return null
  const close = () => botSettingsOpenAtom.set(false)
  const save = () => void saveSettings(draft).then(() => refreshBot()).then(close).catch((e) => onError(errorText(e)))
  const testConnection = () => {
    if (testing) return
    setTesting(true)
    setTestState(null)
    void testLocalLlm({
      url: String(draft[URL_KEY] ?? ''),
      key: String(draft[KEY_KEY] ?? ''),
      model: String(draft[MODEL_KEY] ?? ''),
    }).then((r) => {
      const code = (r.code in TEST_MSG ? r.code : 'unreachable') as LocalLlmTestCode
      setTestState({ ok: !!r.ok, text: TEST_MSG[code](r.model) })
    }).catch(() => {
      setTestState({ ok: false, text: t('botSettings.testFailed') })
    }).finally(() => setTesting(false))
  }

  const llmFields = TEXT_FIELDS.filter(([key]) => LLM_FIELD_KEYS.has(key))
  const otherFields = TEXT_FIELDS.filter(([key]) => !LLM_FIELD_KEYS.has(key))

  return (
    <Modal className="ca-botsettings" title={t('botSettings.agentSettings')} onClose={close}>
      <div className="ca-rename__body">
        {/* #345 ① Built-in Agent */}
        <section className="ca-botsettings__section" data-testid="botsettings-builtin">
          <div className="ca-botsettings__sectiontitle">{t('botSettings.builtinAgent')}</div>
          <div className="ca-chat__hint">{t('botSettings.builtinAgentHint')}</div>
          {llmFields.map(([key, label, hint, type]) => (
            <label key={key} className="ca-rename__field">
              <span>{label}</span>
              <input className="ca-panel__input" type={type ?? 'text'} autoComplete="off" value={String(draft[key] ?? '')} placeholder={hint} onChange={(e) => edit(key, e.target.value)} onKeyDown={(e) => e.stopPropagation()} />
              {key === KEY_KEY && keyCleared && !draft[KEY_KEY] && <span className="ca-adv__help">{t('botSettings.urlChangedReenterKey')}</span>}
              {key === KEY_KEY && <span className="ca-adv__help">{t('botSettings.localLlmKeyEnvHint')}</span>}
            </label>
          ))}
          <div className="ca-botsettings__test" data-testid="local-llm-test">
            <button type="button" className="ca-panel__secondary" disabled={testing} onClick={testConnection}>
              {testing ? t('botSettings.testing') : t('botSettings.testConnection')}
            </button>
            {testState && (
              <span className="ca-botsettings__testmsg" data-ok={testState.ok || undefined} data-err={!testState.ok || undefined} role="status">
                {testState.text}
              </span>
            )}
          </div>
        </section>

        {/* #364 Agent「审核」— post-image review thought on Done (default ON) */}
        <section className="ca-botsettings__section" data-testid="botsettings-review">
          <label className="ca-notice__push" data-testid="bot-enable-review">
            <input
              type="checkbox"
              checked={draft['bot-enable-review'] !== false}
              onChange={(e) => setDraft({ ...draft, 'bot-enable-review': e.target.checked })}
            />
            <span>{t('botSettings.review')}</span>
          </label>
          <div className="ca-chat__hint">{t('botSettings.reviewDesc')}</div>
        </section>

        {/* #345 ② Local third-party agents — switches + AgentSetup; dependency logic unchanged */}
        <AgentSetup providers={providers} enabled={enabled} onError={onError} draft={draft} edit={edit}>
          {SWITCHES.map(([key, label]) => (
            <label key={key} className="ca-notice__push">
              <input type="checkbox" checked={!!draft[key]} onChange={(e) => setDraft({ ...draft, [key]: e.target.checked })} />
              <span>{label}</span>
            </label>
          ))}
        </AgentSetup>

        {/* #345 ③ Advanced — collapsed by default */}
        <section className="ca-botsettings__section" data-testid="botsettings-advanced">
          <button
            type="button"
            className="ca-botsettings__advtoggle"
            aria-expanded={advancedOpen}
            onClick={() => setAdvancedOpen((v) => !v)}
          >
            <span className="ca-botsettings__sectiontitle">{t('botSettings.advanced')}</span>
            <span className="ca-icon" data-flip={advancedOpen || undefined}>{Icons.chevron}</span>
          </button>
          {advancedOpen && (
            <div className="ca-botsettings__advbody">
              {otherFields.map(([key, label, hint, type]) => (
                <label key={key} className="ca-rename__field">
                  <span>{label}</span>
                  <input className="ca-panel__input" type={type ?? 'text'} autoComplete="off" value={String(draft[key] ?? '')} placeholder={hint} onChange={(e) => edit(key, e.target.value)} onKeyDown={(e) => e.stopPropagation()} />
                </label>
              ))}
              {FLAGS.map(([key, label]) => (
                <label key={key} className="ca-notice__push">
                  <input type="checkbox" checked={!!draft[key]} onChange={(e) => setDraft({ ...draft, [key]: e.target.checked })} />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          )}
        </section>

        <label className="ca-rename__field">
          <span>{t('botSettings.ocrEngine')}</span>
          <FieldSelect
            value={String(draft['ocr-engine'] ?? 'local')}
            options={[
              { id: 'local', label: t('botSettings.ocrLocal') },
              { id: 'agent', label: t('botSettings.ocrAgent') },
            ]}
            onChange={(id) => setDraft({ ...draft, 'ocr-engine': id })}
          />
        </label>
        <div className="ca-panel__foot">
          <button type="button" className="ca-panel__secondary" onClick={close}>{t('common.cancel')}</button>
          <button type="button" className="ca-panel__primary" onClick={save}>{t('common.save')}</button>
        </div>
      </div>
    </Modal>
  )
}

// #247: setup guide for each external agent tool the backend knows about (no new tools here).
// Install links go to each tool's official docs only; we never write install commands ourselves.
export const AGENT_DOCS: Record<string, string> = {
  'claude-code': 'https://docs.claude.com/en/docs/claude-code/overview',
  codex: 'https://developers.openai.com/codex/cli',
  'qwen-code': 'https://github.com/QwenLM/qwen-code',
  'deepseek-harness': 'https://www.npmjs.com/package/@deepseek-ai/dsh',
  hermes: 'https://hermes-agent.nousresearch.com/docs/getting-started/installation',
}
export const AGENT_GUIDE_PATH = '/guides/external-agents'
export const mcpConfig = (origin: string) => JSON.stringify({ mcpServers: { comfyart: { type: 'http', url: `${origin}/comfyart/mcp` } } }, null, 2)

function AgentSetup({ providers, enabled, onError, draft, edit, children }: {
  providers: ProviderInfo[]
  enabled: boolean | null
  onError: (msg: string) => void
  draft: Settings
  edit: (key: string, value: string) => void
  children?: ReactNode
}) {
  const [copied, setCopied] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)
  const config = mcpConfig(location.origin)
  const guide = `${docsUrl()}${AGENT_GUIDE_PATH}`
  const copy = (id: string) => void navigator.clipboard?.writeText(config).then(() => { setCopied(id); setTimeout(() => setCopied(null), 1500) }).catch(() => {})
  const focus = useValue(agentSetupFocusAtom)
  useEffect(() => {
    if (!focus) return
    document.querySelector(`.ca-agentsetup__card[data-agent="${focus}"]`)?.scrollIntoView({ block: 'start' })
    agentSetupFocusAtom.set(null)
  }, [focus, providers.length])
  const check = () => { setChecking(true); void refreshBot({ refresh: true }).catch((e) => onError(errorText(e))).finally(() => setChecking(false)) }
  return (
    <section className="ca-agentsetup ca-botsettings__section" data-testid="agent-setup">
      <div className="ca-botsettings__sectiontitle">{t('agentSetup.title')}</div>
      <div className="ca-chat__hint">{t('agentSetup.desc')}</div>
      {children}
      {!enabled && <div className="ca-chat__hint">{t('botSettings.availableAgentsOnThisMachine')}</div>}
      {providers.filter((p) => p.id !== BUILTIN_AGENT).map((p) => (
        <div key={p.id} className="ca-agentsetup__card" data-agent={p.id}>
          <div className="ca-agentsetup__head">
            <span className="ca-agentsetup__name">{providerLabel(p)}</span>
            <span className="ca-agentsetup__chip" data-on={p.available || undefined} title={p.detail || p.version}>{p.available ? t('agentSetup.connected') : t('agentPicker.notDetected')}</span>
          </div>
          {p.id === 'hermes' && (
            <div className="ca-agentsetup__hermes" data-testid="hermes-settings">
              <label className="ca-rename__field">
                <span>{t('botSettings.hermesSshHost')}</span>
                <input
                  className="ca-panel__input"
                  type="text"
                  autoComplete="off"
                  value={String(draft['bot-hermes-ssh-host'] ?? '')}
                  placeholder={t('botSettings.hermesSshHostHint')}
                  onChange={(e) => edit('bot-hermes-ssh-host', e.target.value)}
                  onKeyDown={(e) => e.stopPropagation()}
                />
              </label>
              <label className="ca-rename__field">
                <span>{t('botSettings.hermesProfile')}</span>
                <input
                  className="ca-panel__input"
                  type="text"
                  autoComplete="off"
                  value={String(draft['bot-hermes-profile'] ?? '')}
                  placeholder={t('botSettings.hermesProfileHint')}
                  onChange={(e) => edit('bot-hermes-profile', e.target.value)}
                  onKeyDown={(e) => e.stopPropagation()}
                />
              </label>
            </div>
          )}
          <ol className="ca-agentsetup__steps">
            <li>
              <span>{t('agentSetup.install')}</span>
              {AGENT_DOCS[p.id] && <a href={AGENT_DOCS[p.id]} target="_blank" rel="noopener noreferrer">{t('agentSetup.officialDocs')}</a>}
              <a href={guide} target="_blank" rel="noopener noreferrer">{t('agentSetup.viewGuide')}</a>
            </li>
            <li>
              <span>{t('agentSetup.connect')}</span>
              <div className="ca-agentsetup__code"><pre>{config}</pre><button type="button" className="ca-panel__secondary" onClick={() => copy(p.id)}>{copied === p.id ? t('agentSetup.copied') : t('agentSetup.copy')}</button></div>
            </li>
            <li>
              <button type="button" className="ca-panel__secondary" disabled={checking} onClick={check}>{t('agentSetup.checkAgain')}</button>
            </li>
          </ol>
        </div>
      ))}
    </section>
  )
}
