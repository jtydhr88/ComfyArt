import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useEditor, useValue, type TLShapeId } from 'tldraw'

import { eachLine, eachRuns, generateDirect, isRefShape, refKindOf, sendToAgent, srcOf, type RefShape } from '../agent'
import { botEnabledAtom } from '../bot'
import { imageUrl } from '../comfy'
import { canvasChatAtom, promptFor, renumber, tagOf } from '../canvasChat'
import { errorText } from '../jobs'
import { EachButton, EachRole, useEach } from './EachToggle'
import { Icons } from './icons'
import { isEnter } from './keys'
import { t } from '../i18n'

const WIDTH = 440
const GAP = 16
const EDGE = 8

function Thumb({ s, src }: { s: RefShape; src: string }) {
  const kind = refKindOf(s)
  if (kind === 'audio') return <span className="ca-icon">{Icons.music}</span>
  return kind === 'video' ? <video src={src} muted preload="metadata" /> : <img src={imageUrl(src)} alt="" />
}

export function CanvasChat({ onError }: { onError: (msg: string) => void }) {
  const editor = useEditor()
  const chat = useValue(canvasChatAtom)
  const selected = useValue('chat selection', () => editor.getSelectedShapeIds(), [editor])
  const pos = useValue('chat anchor', () => (chat ? editor.pageToViewport(chat.anchor) : null), [editor, chat])
  const bot = useValue(botEnabledAtom)
  const [text, setText] = useState('')
  const [ids, setIds] = useState<TLShapeId[]>([])
  const input = useRef<HTMLTextAreaElement>(null)
  const caret = useRef(0)
  const each = useEach()

  useEffect(() => {
    if (!chat) return
    const start = chat.refs.map((_, i) => tagOf(i + 1)).join('') + (chat.refs.length ? ' ' : '')
    setIds(chat.refs)
    setText(start)
    caret.current = start.length
    each.reset()
    requestAnimationFrame(() => { input.current?.focus(); input.current?.setSelectionRange(start.length, start.length) })
  }, [chat])

  useEffect(() => {
    if (!chat) return
    const added = selected.filter((id) => !ids.includes(id) && isRefShape(editor.getShape(id)!))
    if (!added.length) return
    const tags = added.map((_, i) => tagOf(ids.length + i + 1)).join('')
    const at = Math.min(caret.current, text.length)
    setIds([...ids, ...added])
    setText(text.slice(0, at) + tags + text.slice(at))
    caret.current = at + tags.length
  }, [selected])

  useLayoutEffect(() => {
    if (!chat) return
    input.current?.focus()
    input.current?.setSelectionRange(caret.current, caret.current)
  }, [ids])

  if (!chat || !pos) return null
  const refs = ids.map((id) => editor.getShape(id)).filter((s): s is RefShape => !!s && isRefShape(s))
  const close = () => canvasChatAtom.set(null)
  const remove = (id: TLShapeId) => {
    const gone = ids.indexOf(id) + 1
    setIds(ids.filter((x) => x !== id))
    setText(renumber(text, (n) => (n === gone ? null : n > gone ? n - 1 : n)))
  }
  const ready = !!renumber(text, () => null).trim()
  const run = (agent: boolean) => {
    if (!ready) return
    const targets = refs.length > 1 ? each.targets(refs) : []
    const log = promptFor(text, refs, refs)
    close()
    editor.selectNone()
    const job = agent
      ? sendToAgent(editor, log, refs, null, [], [], targets.length ? eachLine(refs, targets) : '')
      : generateDirect(editor, log, eachRuns(refs, targets, (runRefs) => promptFor(text, refs, runRefs.filter((r) => r.type === 'image'))).map((r) => ({ ...r, near: r.near ?? refs.at(-1)?.id })), false, onError)
    void job.catch((e) => onError(errorText(e)))
  }

  const host = editor.getContainer().getBoundingClientRect()
  const left = Math.min(Math.max(pos.x - WIDTH / 2, EDGE), host.width - WIDTH - EDGE)
  const top = Math.min(pos.y + GAP, host.height - 220)

  return (
    <div className="ca-cchat" style={{ left, top, width: WIDTH }} onPointerDown={(e) => e.stopPropagation()} onWheel={(e) => e.stopPropagation()}>
      {refs.length > 0 && (
        <div className="ca-cchat__refs">
          {refs.map((s, i) => (
            <span key={s.id} className="ca-chip ca-chip--image" data-audio={refKindOf(s) === 'audio' || undefined}>
              <Thumb s={s} src={srcOf(editor, s) ?? ''} />
              <span className="ca-cchat__num">{i + 1}</span>
              <button type="button" title={t('common.remove')} onClick={() => remove(s.id)}>{Icons.close}</button>
              {each.on && refs.length > 1 && <EachRole shared={each.isShared(s.id)} onToggle={() => each.toggleShared(s.id)} />}
            </span>
          ))}
        </div>
      )}
      <textarea
        ref={input}
        className="ca-cchat__input"
        value={text}
        placeholder={t('canvasChat.placeholder')}
        onChange={(e) => { setText(e.target.value); caret.current = e.target.selectionStart }}
        onSelect={(e) => { caret.current = e.currentTarget.selectionStart }}
        onKeyDown={(e) => {
          e.stopPropagation()
          if (e.key === 'Escape') close()
          if (isEnter(e) && !e.shiftKey) { e.preventDefault(); run(false) }
        }}
      />
      <div className="ca-cchat__foot">
        <div className="ca-gen__spacer" />
        {refs.length > 1 && <EachButton on={each.on} onChange={each.setOn} />}
        {bot && <button type="button" className="ca-panel__secondary" disabled={!ready} onClick={() => run(true)}>{t('canvasChat.sendToAgent')}</button>}
        <button type="button" className="ca-panel__primary" disabled={!ready} onClick={() => run(false)}>{t('canvasChat.generate')}</button>
        <button type="button" className="ca-panel__icon" title={t('common.close')} onClick={close}>{Icons.close}</button>
      </div>
    </div>
  )
}
