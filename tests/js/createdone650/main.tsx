// #650 follow-up: Skill Creator creation-complete turn — real UserMessage + AssistantBlocks; $0 mocks.
import { createRoot } from 'react-dom/client'
import { AssistantBlocks, UserMessage } from '../../../src/ui/ChatMessage'
import { setLang } from '../i18n_stub'

const q = new URLSearchParams(location.search)
const en = q.get('lang') === 'en'
setLang(en ? 'en' : 'zh')

const use = (id: string, name: string, input: any = {}) => ({ type: 'tool_use', id, name, input })
const res = (id: string, name: string, text = '{}', status = 'success') => ({ type: 'tool_result', id, name, status, text })

const user: any = {
  id: 'u650', role: 'user', status: 'done', blocks: [
    { type: 'skill', name: en ? 'Skill Creator' : '技能创建器' },
    { type: 'text', text: 'Create a minimal test skill named zz-test-delete. Description: throwaway test. Use any simple content, no questions.' },
  ],
}
const bot: any = {
  id: 'b650', role: 'assistant', status: 'done', blocks: [
    use('s1', 'mcp__comfyart__skill', { action: 'read', name: 'skill-creator' }),
    res('s1', 'mcp__comfyart__skill', '{"name":"skill-creator"}'),
    use('s2', 'mcp__comfyart__skill', { action: 'save', name: 'zz-test-delete', description: 'A throwaway test skill', instructions: 'Say hi.' }),
    res('s2', 'mcp__comfyart__skill', '{"saved":"zz-test-delete","id":"zz-test-delete","description":"A throwaway test skill"}'),
    { type: 'text', text: 'Created the minimal test skill named zz-test-delete. It\'s now saved and ready to use.' },
  ],
}

createRoot(document.getElementById('root')!).render(
  <div className="ca-root">
    <div className="ca-chat" data-testid="chat" style={{ flex: '0 0 480px', width: 480, margin: '100px auto 0', overflow: 'visible' }}>
      <UserMessage editor={null as any} m={user} />
      <div className="ca-chat__bot" id="done"><AssistantBlocks editor={null as any} m={bot} /></div>
    </div>
  </div>)
;(globalThis as any).__ready = true
