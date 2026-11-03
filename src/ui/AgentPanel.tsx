import { useEffect, useRef, useState } from 'react'
import { atom, useValue, type Editor, type TLShapeId } from 'tldraw'

import { draftAtom, isRefShape, sendToAgent, uploadRefs, type RefShape } from '../agent'
import { BUILTIN_AGENT, NO_KEY_DETAIL, botEnabledAtom, branchFrom, chatIdAtom, chatsAtom, deleteChat, messagesAtom, openChat, providersAtom, stopTurn, type BotMessage } from '../bot'
import { chatFrameOf, locateChatFrame } from '../chatFrame'
import { errorText } from '../jobs'
import { libraryAtom } from '../library'
import { loadSkills, skillCreatorAtom } from '../skills'
import { botSettingsOpenAtom } from './AgentPicker'
import { dockAtom } from './chatDock'
import { libraryTabAtom } from './LibraryPanel'
import { sideAtom } from './SidePanel'
import { AssistantBlocks, stoppedSubmitted, textOf, UserMessage } from './ChatMessage'
import { Composer, FILE_ACCEPT } from './Composer'
import { Icons, LoomiMono } from './icons'
import { NoticeCenter } from './NoticeCenter'
import { Popover } from './Popover'
import { ProjectHeader } from './ProjectHeader'
import { detailsAtom } from './TaskDetails'
import { CopyButton } from './CopyButton'
import { t } from '../i18n'
import { keyMissing, keySettingsOpenAtom, keyStatusAtom } from '../wavespeedKey'

const NEAR_BOTTOM = 80

function pickFiles(use: (files: File[]) => void) {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = FILE_ACCEPT
  input.multiple = true
  input.onchange = () => use(Array.from(input.files ?? []))
  input.click()
}

export type ChatView = 'open' | 'max' | 'closed'
export const chatViewAtom = atom<ChatView>('chat view', 'open')

function History({ onError }: { onError: (msg: string) => void }) {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const chats = useValue(chatsAtom) ?? []
  const current = useValue(chatIdAtom)
  const providers = useValue(providersAtom) ?? []
  const shown = chats.filter((c) => c.title.toLowerCase().includes(q.toLowerCase()))
  const fail = (e: unknown) => onError(errorText(e))
  return (
    <Popover
      open={open}
      onOpenChange={setOpen}
      trigger={({ open: o, toggle }) => (
        <button type="button" className="ca-bar__btn ca-split__chev" title={t('agentPanel.chatHistory')} data-open={o || undefined} onClick={toggle}>
          <span className="ca-icon">{Icons.chevron}</span>
        </button>
      )}
    >
      <div className="ca-menu ca-history">
        <div className="ca-gen__title">{t('agentPanel.chatHistory')}</div>
        <label className="ca-bg__hex">
          <span className="ca-icon">{Icons.search}</span>
          <input value={q} placeholder={t('agentPanel.enterASearchTerm')} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.stopPropagation()} />
        </label>
        {shown.length === 0 && <div className="ca-menu__empty">{t('agentPanel.noChatsYet')}</div>}
        {shown.map((c) => (
          <div key={c.id} className="ca-menu__item ca-history__item" data-on={c.id === current || undefined} onClick={() => { void openChat(c.id).catch(fail); setOpen(false) }}>
            <span className="ca-menu__grow">{c.title || t('agentPanel.newChat')}</span>
            <span className="ca-menu__key">{c.busy ? t('agentPanel.inProgress') : providers.find((p) => p.id === c.provider)?.label ?? c.provider}</span>
            <button type="button" className="ca-history__del" title={t('common.delete')} onClick={(e) => { e.stopPropagation(); void deleteChat(c.id).catch(fail) }}>{Icons.trash}</button>
          </div>
        ))}
      </div>
    </Popover>
  )
}

function refsOf(editor: Editor, m: BotMessage): RefShape[] {
  return m.blocks.flatMap((b) => {
    const shape = b.shape ? editor.getShape(b.shape as TLShapeId) : undefined
    return shape && isRefShape(shape) ? [shape] : []
  })
}

async function resend(editor: Editor, m: BotMessage) {
  const skillName = m.blocks.find((b) => b.type === 'skill')?.name
  const skill = skillName ? (await loadSkills()).find((s) => s.name === skillName) ?? null : null
  const kits = libraryAtom.get().filter((k) => m.blocks.some((b) => b.type === 'kit' && b.name === k.name))
  const docs = m.blocks.filter((b) => b.type === 'file' && b.url).map((b) => ({ src: b.url!, name: b.name ?? '' }))
  await sendToAgent(editor, textOf(m), refsOf(editor, m), skill, kits, docs)
}

/** #419: right after a user stop the partial output turns grey for ~1.5s, then returns to normal; no label. */
const STOP_FADE_MS = 1500
function useStopFade(messages: BotMessage[]): Set<string> {
  const prev = useRef(new Map<string, string>())
  const [fading, setFading] = useState<Set<string>>(() => new Set())
  useEffect(() => {
    for (const m of messages) {
      if (prev.current.get(m.id) === 'streaming' && m.status === 'aborted') {
        setFading((s) => new Set(s).add(m.id))
        setTimeout(() => setFading((s) => { const n = new Set(s); n.delete(m.id); return n }), STOP_FADE_MS)
      }
      prev.current.set(m.id, m.status)
    }
  }, [messages])
  return fading
}

export function AgentPanel({ editor, projectId, max, onMax, onCollapse, onError }: {
  editor: Editor
  projectId: string
  max: boolean
  onMax: () => void
  onCollapse: () => void
  onError: (msg: string) => void
}) {
  const messages = useValue(messagesAtom)
  const chat = useValue('current chat', () => (chatsAtom.get() ?? []).find((c) => c.id === chatIdAtom.get()) ?? null, [])
  const providers = useValue(providersAtom) ?? []
  const keyStatus = useValue(keyStatusAtom)
  const enabled = useValue(botEnabledAtom)
  const dock = useValue(dockAtom)
  const creating = useValue(skillCreatorAtom).on  // #542: creator landing copy
  const hasFrame = useValue('chat frame', () => !!(chat && chatFrameOf(editor, chat.id, true)), [editor, chat?.id])
  const list = useRef<HTMLDivElement>(null)
  const busy = !!chat?.busy
  const canBranch = providers.find((p) => p.id === chat?.provider)?.branch ?? false
  const fail = (e: unknown) => onError(errorText(e))

  const fading = useStopFade(messages)
  const [away, setAway] = useState(false)
  const count = useRef(0)
  const toBottom = () => list.current?.scrollTo({ top: list.current.scrollHeight })
  const onScroll = () => {
    const el = list.current!
    setAway(el.scrollHeight - el.scrollTop - el.clientHeight > NEAR_BOTTOM)
  }

  useEffect(() => {
    const sent = messages.length > count.current && messages[messages.length - 1]?.role === 'user'
    count.current = messages.length
    if (sent || !away) toBottom()
  }, [messages])

  useEffect(() => {
    count.current = 0
    setAway(false)
    toBottom()
  }, [chat?.id])

  const lastUser = messages.map((m) => m.role).lastIndexOf('user')

  return (
    <aside className="ca-agent" data-max={max || undefined}>
      <ProjectHeader editor={editor} projectId={projectId}>
        <div className="ca-split">
          <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('agentPanel.createChat')} onClick={() => void openChat(null)}>
            <span className="ca-icon">{Icons.page}</span>
          </button>
          <History onError={onError} />
        </div>
        {chat && hasFrame && (
          <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('chatFrame.locateFrame')} onClick={() => locateChatFrame(editor, chat.id)}>
            <span className="ca-icon">{Icons.frame}</span>
          </button>
        )}
        <NoticeCenter editor={editor} />
        <button type="button" className="ca-bar__btn ca-bar__btn--icon ca-wide-only" title={max ? t('agentPanel.restoreChat') : t('agentPanel.maximizeChat')} data-on={max || undefined} onClick={onMax}>
          <span className="ca-icon">{Icons.expandPanel}</span>
        </button>
        <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('agentPanel.collapseChat')} onClick={onCollapse}>
          <span className="ca-icon">{dock === 'left' ? Icons.panel : Icons.panelRight}</span>
        </button>
      </ProjectHeader>
      <div ref={list} className="ca-chat" onScroll={onScroll}>
        {enabled === false && (
          <div className="ca-chat__empty">
            <span className="ca-chat__hello"><LoomiMono /></span>
            <div>{t('agentPanel.agentIsNotEnabledYet')}</div>
            <div className="ca-chat__hint">{t('agentPanel.enableMcpAndAgentIn')}</div>
            <button type="button" className="ca-panel__primary" onClick={() => botSettingsOpenAtom.set(true)}>{t('agentPanel.openAgentSettings')}</button>
          </div>
        )}
        {enabled !== false && messages.length === 0 && providers.find((p) => p.id === (chat?.provider ?? BUILTIN_AGENT))?.detail === NO_KEY_DETAIL && keyMissing(keyStatus) && (  // #229/#305: hide while loading or once a Key is saved

          <div className="ca-chat__notice" data-level="error">
            {t('agentPanel.noWavespeedKey')}{' '}
            <a href="#" onClick={(e) => { e.preventDefault(); keySettingsOpenAtom.set(true) }}>{t('agentPanel.setWavespeedKey')}</a>
          </div>
        )}
        {enabled !== false && messages.length === 0 && (
          <div className="ca-chat__empty" data-creator={creating || undefined} data-testid="chat-empty">
            {creating
              ? <div className="ca-chat__title" data-testid="creator-landing-title">{t('agentPanel.creatorStartTitle')}</div>
              : (
                <>
                  <span className="ca-chat__hello"><LoomiMono /></span>
                  <div>{t('agentPanel.describeWhatYouWantTo')}</div>
                  <div className="ca-chat__hint">{t('agentPanel.selectImagesOnTheCanvas')}</div>
                </>
              )}
            <div className="ca-chat__starts">
              <button type="button" className="ca-chat__start" onClick={() => pickFiles((files) => void uploadRefs(editor, files).catch(fail))}><span className="ca-icon">{Icons.upload}</span>{t('agentPanel.uploadReference')}</button>
              <button type="button" className="ca-chat__start" onClick={() => { draftAtom.set('/'); (document.querySelector('.ca-composer__input') as HTMLTextAreaElement | null)?.focus() }}><span className="ca-icon">{Icons.skill}</span>{t('agentPanel.startFromSkill')}</button>
              <button type="button" className="ca-chat__start" onClick={() => { if (max) onMax(); libraryTabAtom.set('brand'); sideAtom.set('assets') }}><span className="ca-icon">{Icons.assets}</span>{t('agentPanel.useBrandKit')}</button>
            </div>
          </div>
        )}
        {messages.map((m, i) => (m.role === 'user'
          ? <UserMessage key={m.id} editor={editor} m={m} onBranch={canBranch && !busy ? () => void branchFrom(m.id).catch(fail) : undefined} />
          : (
            <div key={m.id} className={fading.has(m.id) ? 'ca-chat__bot ca-chat__bot--stopping' : 'ca-chat__bot'}>
              <AssistantBlocks editor={editor} m={m} />
              {m.status === 'streaming' && (
                <div className="ca-chat__thinking">
                  <span className="ca-chat__thinkicon"><span className="ca-icon">{Icons.think}</span></span>
                  <span className="ca-chat__thinklabel">{/* #437: a plain-text reply in progress only reads 输出中…; a reasoning turn's own Thought row carries the live label */}
                  {m.blocks.some((b) => b.type !== 'text' && b.type !== 'thinking') ? t('agentPanel.working') : m.blocks.some((b) => b.type === 'thinking') ? '' : t('chatMessage.outputting')}</span>
                  <button type="button" className="ca-panel__chip" onClick={() => void stopTurn().catch(fail)}>{t('agentPanel.stop')}</button>
                </div>
              )}
              {m.status === 'aborted' && stoppedSubmitted(m) > 0 && (
                <div className="ca-chat__hint" data-stopped="submitted">{t('chatMessage.stoppedSubmittedNote')}</div>
              )}
              {m.status !== 'streaming' && (
                <div className="ca-chat__acts ca-chat__acts--bot">
                  {!busy && i === messages.length - 1 && lastUser === i - 1 && (
                    <button type="button" className="ca-history__del" title={t('common.regenerate')} onClick={() => void resend(editor, messages[i - 1]).catch(fail)}>{Icons.resetCcw}</button>
                  )}
                  <CopyButton text={textOf(m)} />
                  <button type="button" className="ca-history__del" title={t('agentPanel.taskDetails')} onClick={() => detailsAtom.set(m.id)}>{Icons.files}</button>
                </div>
              )}
            </div>
          )))}
      </div>
      {away && <button type="button" className="ca-chat__jump" title={t('agentPanel.jumpToLatest')} onClick={toBottom}><span className="ca-icon">{Icons.chevron}</span></button>}
      <Composer editor={editor} busy={busy} onError={onError} />
    </aside>
  )
}
