// #712: a run billed with no image -> the failed row + the relayed zh/en reason and amount. The kind/charged come
// from the mocked backend's real poll result (query string); the copy is the real wsErrorText. $0 mocks.
import { createRoot } from 'react-dom/client'
import { AssistantBlocks } from '../../../src/ui/ChatMessage'
import { TOOL_LABELS } from '../../../src/bot'
import { wsErrorText } from '../../../src/wsErrors'
import { withTopUpLink } from '../../../src/shapes/GeneratorShape'
import { setLang, t } from '../i18n_stub'

const q = new URLSearchParams(location.search)
const lang = q.get('lang') === 'en' ? 'en' : 'zh'
setLang(lang)
if (q.get('theme') === 'dark') document.documentElement.dataset.theme = 'dark'
TOOL_LABELS.generate_image = t('bot.generateImage')
const charged = q.get('charged') ? Number(q.get('charged')) : undefined
const msg = wsErrorText(q.get('kind'), charged, q.get('task') ?? undefined) ?? 'unknown kind'
const model = q.get('model') || ''
const m: any = {
  id: 'f', role: 'assistant', status: 'done', blocks: [
    { type: 'tool_use', id: 'g1', name: 'mcp__comfyart__generate_image', input: { model, prompt: 'cat' } },
    { type: 'tool_result', id: 'g1', name: 'mcp__comfyart__generate_image', status: 'error',
      text: JSON.stringify({ status: 'failed', generation_succeeded: false, error: msg, user_message: msg, model }) },
    { type: 'text', text: msg },
    // #715: an ordinary long inline code next to the task id must keep main's wrapping (no ellipsis)
    ...(q.get('code') ? [{ type: 'text', text: `\n\n${lang === 'zh' ? '普通代码：' : 'Plain code: '}\`${q.get('code')}\`` }] : []),
  ],
}
const width = Number(q.get('w')) || 520  // #715: narrow (360px) long-id shots
createRoot(document.getElementById('root')!).render(q.get('surface') === 'card'
  // #715: the canvas generator card's error overlay (same markup as GeneratorShape)
  ? <div className="ca-root" style={{ width, padding: 16, background: 'var(--ca-bg)', ...(q.get('w') ? { boxSizing: 'border-box' as const } : {}) }}>
      <div className="ca-gen-card" data-testid="ws-card" style={{ width: width - 32, height: 200 }}>
        <div className="ca-gen-card__error" role="alert" data-testid="ws-failure">{withTopUpLink(msg)}</div></div></div>
  : <div className="ca-root" style={{ width, padding: 16, background: 'var(--ca-bg)', ...(q.get('w') ? { boxSizing: 'border-box' as const } : {}) }}>
    <div className="ca-chat"><div className="ca-chat__bot" id="ours" data-testid="ws-failure"><AssistantBlocks editor={null as any} m={m} /></div></div>
  </div>)
;(globalThis as any).__ready = true
