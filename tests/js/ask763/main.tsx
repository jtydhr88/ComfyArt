// #763 HOLD 98fa5b44: no empty 输出中…/Outputting… shell while a question is docked, or after Skip/answer before reply text.
// Renders the chat column (AssistantBlocks dockAsks + streaming footer + docked card) like AgentPanel. $0 mocks, no network.
import { createRoot } from 'react-dom/client'
import { AssistantBlocks, askQuiet, isDockedQuestion, renderAsk, UserMessage } from '../../../src/ui/ChatMessage'
import { setLang, t } from '../i18n_stub'

const q = new URLSearchParams(location.search)
const lang = q.get('lang') === 'en' ? 'en' : 'zh'
setLang(lang)
if (q.get('theme') === 'dark') document.documentElement.dataset.theme = 'dark'

const use = (id: string, name: string, input: any = {}) => ({ type: 'tool_use', id, name, input })
const res = (id: string, name: string, text = '{}') => ({ type: 'tool_result', id, name, status: 'success', text })
const ask = (status: string, extra: any = {}) => ({
  type: 'ask', ask_id: 'a1', kind: 'question', status,
  questions: [{ id: 'q1', prompt: lang === 'en' ? 'What logo style do you prefer?' : '你更偏好哪种 logo 风格？',
    options: [{ id: 'm', label: lang === 'en' ? 'Minimal' : '极简' }, { id: 'p', label: lang === 'en' ? 'Playful' : '活泼' }, { id: 'r', label: lang === 'en' ? 'Retro' : '复古' }],
    allow_other: true }],
  ...extra,
})
const head = [
  { type: 'thinking', text: 'Plan the logo brief.' },
  use('c1', 'mcp__comfyart__canvas_read'), res('c1', 'mcp__comfyart__canvas_read'),
  { type: 'thinking', text: 'Ask the style first.' },
  use('u1', 'mcp__comfyart__ask_user'),
]
const scenes: Record<string, any[]> = {
  'q-open': [...head, ask('pending')],
  'skip-after': [...head, ask('answered', { answers: { q1: { selected: [] } } }), res('u1', 'mcp__comfyart__ask_user', '{"skipped":true}')],
  'answer-before-tokens': [...head, ask('answered', { answers: { q1: { selected: ['m'] } } }), res('u1', 'mcp__comfyart__ask_user', '{"selected":["m"]}')],
  'answer-then-text': [...head, ask('answered', { answers: { q1: { selected: ['m'] } } }), res('u1', 'mcp__comfyart__ask_user', '{}'), { type: 'text', text: lang === 'en' ? 'Going minimal.' : '那就走极简风。' }],
  'other-typed': [...head, ask('answered', { answers: { q1: { selected: [], other_text: lang === 'en' ? 'Hand-drawn ink' : '手绘墨线' } } }), res('u1', 'mcp__comfyart__ask_user', '{}')],
  'gen-no-question': [{ type: 'thinking', text: 'Plan.' }, use('c1', 'mcp__comfyart__canvas_read'), res('c1', 'mcp__comfyart__canvas_read')],
  'thought-leak': [{ type: 'thinking', text: 'Plan the logo.\nLet me call ask_user with one multiple-choice question.' }, use('u1', 'mcp__comfyart__ask_user'), ask('answered', { answers: { q1: { selected: ['m'] } } }), res('u1', 'mcp__comfyart__ask_user', '{}'), { type: 'text', text: lang === 'en' ? 'Noted.' : '收到。' }],
}
const scene = q.get('scene') ?? 'q-open'
const m: any = { id: 'm1', role: 'assistant', status: 'streaming', blocks: scenes[scene] }
const user: any = { id: 'u1', role: 'user', status: 'done', blocks: [{ type: 'text', text: lang === 'en' ? 'Design a logo for Moka cafe; ask my style first.' : '为咖啡店 Moka 设计 logo，先问我偏好的风格。' }] }
const docked = m.blocks.filter(isDockedQuestion)
const editor: any = {}

function App() {
  return (
    <div className="ca-panel" style={{ width: 400, display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <div className="ca-chat" style={{ flex: 1 }}>
        <UserMessage editor={editor} m={user} />
        <div className="ca-chat__bot" data-testid="bot">
          <AssistantBlocks editor={editor} m={m} dockAsks />
          {m.status === 'streaming' && !askQuiet(m) && (
            <div className="ca-chat__thinking" data-testid="footer">
              <span className="ca-chat__thinklabel">{m.blocks.some((b: any) => b.type === 'thinking') ? '' : t('chatMessage.outputting')}</span>
            </div>
          )}
        </div>
      </div>
      {docked.length > 0 && <div className="ca-chat__dock" data-testid="question-dock">{docked.map((b: any, i: number) => renderAsk(b, b.ask_id ?? i))}</div>}
    </div>
  )
}
createRoot(document.getElementById('root')!).render(<App />)
;(window as any).__ready = true
