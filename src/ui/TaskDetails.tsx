import { atom, useValue, type Editor } from 'tldraw'

import { chatIdAtom, chatsAtom, messagesAtom, outputsOf, providersAtom, toolLabel, type BotBlock } from '../bot'
import { fileSrc } from '../jobs'
import { Icons } from './icons'
import { Modal } from './Modal'
import { t } from '../i18n'
import { stepState } from './stepState'

const AUDIO_FILES = ['flac', 'mp3', 'wav', 'ogg', 'opus', 'm4a']

export const detailsAtom = atom<string | null>('task details', null)

export function reveal(editor: Editor, src: string) {
  for (const page of editor.getPages()) {
    for (const id of editor.getPageShapeIds(page.id)) {
      if (fileSrc(editor, editor.getShape(id)) !== src) continue
      editor.setCurrentPage(page.id)
      editor.select(id)
      editor.zoomToSelection({ animation: { duration: 200 } })
      return
    }
  }
}

export function Thumb({ editor, src, onOpen }: { editor: Editor; src: string; onOpen?: () => void }) {
  const ext = /\.(\w+)(&|$)/.exec(src)?.[1]?.toLowerCase() ?? ''
  const icon = AUDIO_FILES.includes(ext) ? Icons.music : ext === 'glb' ? Icons.cube : null
  return (
    <span className="ca-chat__thumbwrap">
      <button type="button" className="ca-chat__thumb" data-icon={!!icon || undefined} onClick={() => { onOpen?.(); reveal(editor, src) }}>
        {icon ? <span className="ca-icon">{icon}</span> : ['mp4', 'webm', 'mov'].includes(ext) ? <video src={src} muted preload="metadata" /> : <img src={src} alt="" />}
      </button>
      <a className="ca-chat__dl" href={src} download={new URL(src, location.origin).searchParams.get('filename') ?? ''} title={t('common.download')}>{Icons.download}</a>
    </span>
  )
}

interface Step { label: string; detail: string; state: string; result?: string }

function steps(blocks: BotBlock[]): Step[] {
  const results = new Map(blocks.filter((b) => b.type === 'tool_result' && b.id).map((b) => [b.id, b]))
  return blocks.flatMap((b, i) => {
    if (b.type === 'text' && b.text?.trim()) return [{ label: t('taskDetails.reply'), detail: b.text.trim(), state: '' }]
    if (b.type === 'ask') return [{ label: t('bot.askYou'), detail: b.prompt ?? '', state: b.status === 'answered' ? t('taskDetails.answered') : b.status ?? '' }]
    if (b.type === 'notice') return [{ label: b.level === 'error' ? t('taskDetails.error') : t('taskDetails.prompt'), detail: b.text ?? '', state: '' }]
    if (b.type === 'task') return [{ label: b.label ?? t('common.generate'), detail: b.detail?.prompt ?? '', state: b.error ? t('chatMessage.failed') : b.srcs ? t('common.done') : t('taskDetails.generating') }]
    if (b.type !== 'tool_use') return []
    const r = b.id ? results.get(b.id) : blocks[i + 1]?.type === 'tool_result' ? blocks[i + 1] : undefined
    const kind = stepState(r)
    const state = !r ? t('agentPanel.inProgress') : kind === 'cancelled' ? t('chatMessage.cancelled') : kind === 'error' ? t('chatMessage.failed') : r.duration_ms != null ? `${(r.duration_ms / 1000).toFixed(1)}s` : t('common.done')
    return [{ label: toolLabel(b.name), detail: JSON.stringify(b.input ?? {}), state, result: r?.status === 'error' ? r.text : undefined }]
  })
}

export function TaskDetails({ editor }: { editor: Editor }) {
  const id = useValue(detailsAtom)
  const messages = useValue(messagesAtom)
  const providers = useValue(providersAtom)
  const chat = useValue('current chat', () => (chatsAtom.get() ?? []).find((c) => c.id === chatIdAtom.get()) ?? null, [])
  const index = messages.findIndex((m) => m.id === id)
  if (index < 0) return null
  const m = messages[index]
  const request = messages.slice(0, index).reverse().find((x) => x.role === 'user')
  const close = () => detailsAtom.set(null)
  const outputs = outputsOf(m.blocks)
  const requestText = request?.blocks.filter((b) => b.type === 'text').map((b) => b.text).join('')

  return (
    <Modal title={t('agentPanel.taskDetails')} className="ca-details" onClose={close}>
      <div className="ca-details__body">
        {request && (
          <section>
            <div className="ca-gen__label">{t('taskDetails.originalRequest')}</div>
            {requestText && <div className="ca-info__prompt">{requestText}</div>}
            <div className="ca-chat__thumbs">
              {request.blocks.filter((b) => b.type === 'image' || b.type === 'video').map((b) => <Thumb key={b.url} editor={editor} src={b.url!} onOpen={close} />)}
            </div>
            {request.blocks.filter((b) => b.type === 'skill' || b.type === 'kit').map((b) => (
              <span key={b.name} className="ca-chip"><span className="ca-icon">{b.type === 'skill' ? Icons.skill : Icons.assets}</span>{b.name}</span>
            ))}
          </section>
        )}
        <section>
          <div className="ca-gen__label">{t('taskDetails.process', chat ? ` · ${providers.find((p) => p.id === chat.provider)?.label ?? chat.provider}` : '')}</div>
          <ol className="ca-details__steps">
            {steps(m.blocks).map((s, i) => (
              <li key={i}>
                <span className="ca-details__step"><b>{s.label}</b><span className="ca-menu__grow" /><span>{s.state}</span></span>
                {s.detail && <div className="ca-details__detail">{s.detail}</div>}
                {s.result && <div className="ca-details__detail" data-error>{s.result}</div>}
              </li>
            ))}
          </ol>
        </section>
        {outputs.length > 0 && (
          <section>
            <div className="ca-gen__label">{t('taskDetails.output')}</div>
            <div className="ca-chat__thumbs">{outputs.map((s) => <Thumb key={s} editor={editor} src={s} onOpen={close} />)}</div>
          </section>
        )}
        {m.usage && (
          <section>
            <div className="ca-gen__label">{t('taskDetails.usageThisTurn')}</div>
            <div className="ca-keys__row"><span>{t('taskDetails.input')}</span><span className="ca-menu__key">{(m.usage.input_tokens ?? 0) + (m.usage.cache_read_input_tokens ?? 0)} tokens</span></div>
            <div className="ca-keys__row"><span>{t('taskDetails.outputs')}</span><span className="ca-menu__key">{m.usage.output_tokens ?? 0} tokens</span></div>
            {m.usage.cost_usd != null && <div className="ca-keys__row"><span>{t('taskDetails.cost')}</span><span className="ca-menu__key">${m.usage.cost_usd}</span></div>}
          </section>
        )}
      </div>
    </Modal>
  )
}
