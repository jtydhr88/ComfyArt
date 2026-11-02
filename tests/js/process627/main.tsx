// #627: full expanded image rail + simple-turn — real AssistantBlocks; $0 mocks.
import { createRoot } from 'react-dom/client'
import { AssistantBlocks } from '../../../src/ui/ChatMessage'
import { setLang } from '../i18n_stub'

const q = new URLSearchParams(location.search)
setLang(q.get('lang') === 'en' ? 'en' : 'zh')
if (q.get('theme') === 'dark') document.documentElement.dataset.theme = 'dark'

const use = (id: string, name: string, input: any = {}) => ({ type: 'tool_use', id, name, input })
const res = (id: string, name: string, text = '{}', status = 'success') => (
  { type: 'tool_result', id, name, status, text }
)

// Runtime model-name slot — example value only (not hard-coded product copy in src/).
const MODEL = 'GPT Image 2.5 Flare'

const full: any = {
  id: 'full-627', role: 'assistant', status: 'done', blocks: [
    { type: 'thinking', text: 'Plan the apple still-life.' },
    use('sk1', 'mcp__comfyart__skill', { action: 'load', name: 'poster' }),
    res('sk1', 'mcp__comfyart__skill', '{"name":"poster"}'),
    { type: 'thinking', text: 'Search Red Fuji cues.' },
    use('w1', 'WebSearch', { query: 'red fuji apple', num_results: 1 }),
    res('w1', 'WebSearch', '{"results":[{"url":"https://www.google.com/search?q=red+fuji"}]}'),
    use('g1', 'mcp__comfyart__generate_image', { model: MODEL, prompt: 'red fuji apple on white', ratio: '1:1' }),
    res('g1', 'mcp__comfyart__generate_image', '{"prompt_id":"p1"}'),
    // post-image review thinking → ref_analysis (参考素材分析结束)
    { type: 'thinking', text: 'Checked the delivered apple against the refs.' },
    { type: 'text', text: '已生成完成：一只红富士苹果，白底方形构图。\n\n下一步建议：可以加投影，或换成透明底。' },
  ],
}

// Simple turn: no think rail — model name + result + prose + thumbs
const simple: any = {
  id: 'simple-627', role: 'assistant', status: 'done', blocks: [
    use('g2', 'mcp__comfyart__generate_image', { model: MODEL, prompt: 'red apple', ratio: '1:1' }),
    res('g2', 'mcp__comfyart__generate_image', '{"prompt_id":"p2"}'),
    { type: 'text', text: '已画好：一只红苹果，纯白底。' },
  ],
}

const scene = q.get('scene') === 'simple' ? simple : full
const id = q.get('scene') === 'simple' ? 'simple' : 'full'

createRoot(document.getElementById('root')!).render(
  <div className="ca-root" style={{ width: 392, padding: 16 }}>
    <div className="ca-chat">
      <div className="ca-chat__bot" id={id} data-testid={`scene-${id}`}>
        <AssistantBlocks editor={null as any} m={scene} />
      </div>
    </div>
  </div>)
;(globalThis as any).__ready = true
