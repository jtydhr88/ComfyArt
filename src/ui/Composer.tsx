import { useEffect, useRef, useState } from 'react'
import { useValue, type Editor, type TLShapeId } from 'tldraw'

import { agentModeAtom, directSettingsAtom, DOC_ACCEPT, docsAtom, draftAtom, eachLine, eachRuns, extraRefsAtom, generateDirect, isRefShape, kitsAtom, refKindOf, sendToAgent, srcOf, uploadRefs, type AgentMode, type DirectSettings, type RefShape } from '../agent'
import { EachButton, EachRole, useEach } from './EachToggle'
import { RefFrameButton } from './RefFrameButton'
import { placeAsset } from '../assets'
import { botEnabledAtom, messagesAtom } from '../bot'
import { imageUrl } from '../comfy'
import { VIDEO_RATIOS } from '../genOptions'
import { errorText } from '../jobs'
import { KIND_LABELS, libraryAtom } from '../library'
import { agentModels, installedModels, modelOf } from '../models'
import { GENERATOR, type GeneratorShape, type GeneratorShapeUtil } from '../shapes/GeneratorShape'
import type { AudioShape } from '../shapes/EmbedShapes'
import { loadSkills, saveSkill, skillAtom, type Skill } from '../skills'
import { AssetGrid } from './AssetPicker'
import { ModelPill, SettingsPill } from './GenSettings'
import { schedulesOpenAtom } from '../schedules'
import { AgentPicker } from './AgentPicker'
import { Icons } from './icons'
import { ModelPrefs } from './ModelPrefs'
import { VoiceButton } from './VoiceButton'
import { SkillForm, skillsOpenAtom } from './SkillsDialog'
import { Popover } from './Popover'
import { t } from '../i18n'
import { uuid } from '../id'
import { isEnter } from './keys'

const MODES: [AgentMode, string, keyof typeof Icons][] = [['agent', 'Agent', 'agent'], ['image', t('composer.image'), 'genImage'], ['video', t('common.video'), 'genVideo']]
const REVIEW_PROMPT = t('composer.canvasReviewUseGetCanvas')
const SKILL_PROMPT = t('composer.turnTheApproachCompletedIn')

export const FILE_ACCEPT = `image/*,video/*,audio/*,${DOC_ACCEPT}`

function imageName(editor: Editor, s: RefShape) {
  if (refKindOf(s) === 'audio') return (s as AudioShape).props.name || t('composer.audio')
  const v = s as Exclude<RefShape, AudioShape>
  const asset = v.props.assetId ? editor.getAsset(v.props.assetId) : null
  return (asset?.type === v.type && asset.props.name) || (v.type === 'video' ? t('common.video') : t('common.image'))
}

function RefThumb({ editor, s }: { editor: Editor; s: RefShape }) {
  const kind = refKindOf(s)
  if (kind === 'audio') return <span className="ca-icon">{Icons.music}</span>
  return kind === 'video' ? <video src={srcOf(editor, s) ?? ''} muted preload="metadata" /> : <img src={imageUrl(srcOf(editor, s) ?? '')} alt="" />
}

function DirectPills({ editor, video }: { editor: Editor; video: boolean }) {
  const key = video ? 'video' : 'image'
  const settings = useValue('direct settings', () => directSettingsAtom.get()[key], [key])
  const models = useValue('direct models', () => installedModels(video), [video])
  const workflow = settings.workflow || agentModels(video)[0].id
  const p: GeneratorShape['props'] = { ...editor.getShapeUtil<GeneratorShapeUtil>(GENERATOR).getDefaultProps(), ratio: video ? VIDEO_RATIOS[0] : '1:1', ...settings, workflow }
  const model = modelOf(workflow)!
  const update = (patch: DirectSettings) => {
    const all = directSettingsAtom.get()
    directSettingsAtom.set({ ...all, [key]: { ...all[key], ...patch } })
  }
  return (
    <>
      <SettingsPill p={p} video={video} quality={!!model.steps} update={update} />
      <ModelPill models={models} model={model} onPick={(id) => update({ workflow: id })} />
    </>
  )
}

export function Composer({ editor, busy, onError }: { editor: Editor; busy: boolean; onError: (msg: string) => void }) {
  const started = useValue('chat started', () => messagesAtom.get().length > 0, [])
  const draft = useValue(draftAtom)
  const mode = useValue(agentModeAtom)
  const enabled = useValue(botEnabledAtom)
  const agentOff = mode === 'agent' && enabled === false
  const skill = useValue(skillAtom)
  const extra = useValue(extraRefsAtom)
  const kits = useValue(kitsAtom)
  const library = useValue(libraryAtom)
  const docs = useValue(docsAtom)
  const selected = useValue('selected media', () => editor.getSelectedShapes().filter(isRefShape), [editor])
  const images = useValue('canvas media', () => editor.getCurrentPageShapes().filter(isRefShape), [editor])
  const [menu, setMenu] = useState<'plus' | 'skills' | 'assets' | 'mode' | 'create' | null>(null)
  const [skills, setSkills] = useState<Skill[]>([])
  const file = useRef<HTMLInputElement>(null)
  const [hidden, setHidden] = useState<TLShapeId[]>([])
  const [drop, setDrop] = useState(false)
  const each = useEach()

  const shown = selected.filter((s) => !hidden.includes(s.id))
  const refs = [...shown, ...extra.map((id) => editor.getShape(id)).filter((s): s is RefShape => !!s && isRefShape(s) && !shown.some((x) => x.id === s.id))]
  const slash = /^\/(\S*)$/.exec(draft)
  const at = /(?:^|\s)@(\S*)$/.exec(draft)

  useEffect(() => {
    if (menu === 'skills' || slash) void loadSkills().then(setSkills)
  }, [menu, !!slash])

  useEffect(() => {
    setHidden((h) => h.filter((id) => selected.some((s) => s.id === id)))
  }, [selected])

  const addRef = (id: TLShapeId) => {
    setHidden((h) => h.filter((x) => x !== id))
    extraRefsAtom.set([...extraRefsAtom.get().filter((x) => x !== id), id])
  }
  const removeRef = (id: TLShapeId) => {
    extraRefsAtom.set(extraRefsAtom.get().filter((x) => x !== id))
    if (selected.some((s) => s.id === id)) setHidden((h) => [...h, id])
  }
  const useSkill = (s: Skill) => { skillAtom.set(s); setMenu(null); if (slash) draftAtom.set('') }

  const fail = (e: unknown) => onError(errorText(e))
  const upload = (files: FileList | null) => uploadRefs(editor, Array.from(files ?? [])).catch(fail)
  const imageFiles = (list: DataTransfer) => Array.from(list.files)
  const send = () => {
    const text = draft.trim()
    if (!text || agentOff) return
    draftAtom.set('')
    extraRefsAtom.set([])
    kitsAtom.set([])
    if (mode === 'agent') {
      skillAtom.set(null)
      docsAtom.set([])
    }
    const targets = refs.length > 1 ? each.targets(refs) : []
    each.reset()
    void (mode === 'agent'
      ? sendToAgent(editor, text, refs, skill, kits, docs, targets.length ? eachLine(refs, targets) : '')
      : generateDirect(editor, text, eachRuns(refs, targets, () => text), mode === 'video', onError)).catch(fail)
  }

  const filtered = slash ? skills.filter((s) => s.name.includes(slash[1])) : skills
  const mentions = at ? images.filter((s) => imageName(editor, s).toLowerCase().includes(at[1].toLowerCase())).slice(0, 8) : []
  const kitMentions = at ? library.filter((k) => k.name.toLowerCase().includes(at[1].toLowerCase()) && !kits.some((x) => x.id === k.id)).slice(0, 8) : []
  const clearAt = () => draftAtom.set(draft.slice(0, at!.index) + (at!.index ? ' ' : ''))
  const modeInfo = MODES.find(([m]) => m === mode)!

  return (
    <div
      className="ca-composer"
      data-drop={drop || undefined}
      onDragOver={(e) => { if (e.dataTransfer.types.includes('Files')) { e.preventDefault(); setDrop(true) } }}
      onDragLeave={() => setDrop(false)}
      onDrop={(e) => { setDrop(false); const files = imageFiles(e.dataTransfer); if (files.length) { e.preventDefault(); void uploadRefs(editor, files).catch(fail) } }}
    >
      {(slash && filtered.length > 0) && (
        <div className="ca-menu ca-composer__suggest">
          {filtered.slice(0, 8).map((s) => (
            <button key={s.id} type="button" className="ca-menu__item" onClick={() => useSkill(s)}>
              <span className="ca-icon">{Icons.skill}</span><span className="ca-menu__grow">{s.name}</span>
            </button>
          ))}
        </div>
      )}
      {(mentions.length > 0 || kitMentions.length > 0) && (
        <div className="ca-menu ca-composer__suggest">
          {kitMentions.map((k) => (
            <button key={k.id} type="button" className="ca-menu__item" onClick={() => { kitsAtom.set([...kits, k]); clearAt() }}>
              {k.images[0] ? <img className="ca-composer__mini" src={k.images[0]} alt="" /> : <span className="ca-icon">{Icons.assets}</span>}
              <span className="ca-menu__grow">{k.name}</span><span className="ca-menu__key">{KIND_LABELS[k.kind]}</span>
            </button>
          ))}
          {mentions.map((s) => (
            <button key={s.id} type="button" className="ca-menu__item" onClick={() => { addRef(s.id); clearAt() }}>
              {s.type === 'image' ? <img className="ca-composer__mini" src={imageUrl(srcOf(editor, s) ?? '')} alt="" /> : <span className="ca-icon">{s.type === 'video' ? Icons.video : Icons.music}</span>}<span className="ca-menu__grow">{imageName(editor, s)}</span>
            </button>
          ))}
        </div>
      )}
      {(refs.length > 0 || skill || kits.length > 0 || (mode === 'agent' && docs.length > 0)) && (
        <div className="ca-composer__chips">
          {kits.map((k) => (
            <span key={k.id} className="ca-chip">
              <span className="ca-icon">{Icons.assets}</span>{k.name}
              <button type="button" title={t('common.remove')} onClick={() => kitsAtom.set(kits.filter((x) => x.id !== k.id))}>{Icons.close}</button>
            </span>
          ))}
          {skill && (
            <span className="ca-chip">
              <span className="ca-icon">{Icons.skill}</span>{skill.name}
              <button type="button" title={t('common.remove')} onClick={() => skillAtom.set(null)}>{Icons.close}</button>
            </span>
          )}
          {mode === 'agent' && docs.map((d) => (
            <span key={d.src} className="ca-chip" title={d.name}>
              <span className="ca-icon">{Icons.page}</span><span className="ca-chip__name">{d.name}</span>
              <button type="button" title={t('common.remove')} onClick={() => docsAtom.set(docs.filter((x) => x.src !== d.src))}>{Icons.close}</button>
            </span>
          ))}
          {refs.map((r) => (
            <span key={r.id} className="ca-chip ca-chip--image" data-audio={refKindOf(r) === 'audio' || undefined} title={imageName(editor, r)}>
              <RefThumb editor={editor} s={r} />
              <button type="button" title={t('common.remove')} onClick={() => removeRef(r.id)}>{Icons.close}</button>
              {each.on && refs.length > 1 && <EachRole shared={each.isShared(r.id)} onToggle={() => each.toggleShared(r.id)} />}
            </span>
          ))}
        </div>
      )}
      <textarea
        className="ca-composer__input"
        value={draft}
        placeholder={t('composer.describeYourDesignNeedsFor')}
        onChange={(e) => draftAtom.set(e.target.value)}
        onPaste={(e) => { const files = imageFiles(e.clipboardData); if (!files.length) return; e.preventDefault(); e.stopPropagation(); void uploadRefs(editor, files).catch(fail) }}
        onKeyDown={(e) => {
          e.stopPropagation()
          if (isEnter(e) && !e.shiftKey && !slash && !mentions.length && !kitMentions.length) {
            e.preventDefault()
            send()
          }
        }}
      />
      <div className="ca-composer__foot">
        <input ref={file} type="file" accept={FILE_ACCEPT} multiple hidden onChange={(e) => { void upload(e.target.files); e.target.value = '' }} />
        <Popover
          open={menu === 'plus' || menu === 'skills' || menu === 'assets' || menu === 'create'}
          onOpenChange={(o) => setMenu(o ? 'plus' : null)}
          side="top"
          contentKey={menu ?? ''}
          trigger={({ open, toggle }) => (
            <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('common.add')} data-open={open || undefined} onClick={toggle}>
              <span className="ca-icon">{Icons.plus}</span>
            </button>
          )}
        >
          {menu === 'plus' && (
            <div className="ca-menu">
              <button type="button" className="ca-menu__item" onClick={() => { setMenu(null); file.current?.click() }}>
                <span className="ca-icon">{Icons.upload}</span><span className="ca-menu__grow">{t('common.uploadFile')}</span>
              </button>
              <div className="ca-menu__sep" />
              <button type="button" className="ca-menu__item" onClick={() => { setMenu(null); void sendToAgent(editor, REVIEW_PROMPT, [], null).catch(fail) }}>
                <span className="ca-icon">{Icons.search}</span><span className="ca-menu__grow">{t('composer.canvasReview')}</span>
              </button>
              <button type="button" className="ca-menu__item" onClick={() => { setMenu(null); schedulesOpenAtom.set(draft.trim() ? { prompt: draft.trim() } : {}) }}>
                <span className="ca-icon">{Icons.bell}</span><span className="ca-menu__grow">{t('composer.scheduledTask')}</span>
              </button>
              <button type="button" className="ca-menu__item" onClick={() => setMenu('skills')}>
                <span className="ca-icon">{Icons.skill}</span><span className="ca-menu__grow">Skill</span><span className="ca-icon">{Icons.next}</span>
              </button>
              <button type="button" className="ca-menu__item" onClick={() => setMenu('assets')}>
                <span className="ca-icon">{Icons.files}</span><span className="ca-menu__grow">{t('composer.addAssets')}</span><span className="ca-icon">{Icons.next}</span>
              </button>
            </div>
          )}
          {menu === 'skills' && (
            <div className="ca-menu ca-skills">
              <button type="button" className="ca-menu__item" onClick={() => setMenu('create')}>
                <span className="ca-icon">{Icons.plus}</span><span className="ca-menu__grow">{t('composer.skillCreator')}</span>
              </button>
              <button type="button" className="ca-menu__item" disabled={!started} onClick={() => { setMenu(null); void sendToAgent(editor, SKILL_PROMPT, [], null).catch(fail) }}>
                <span className="ca-icon">{Icons.agent}</span><span className="ca-menu__grow">{t('composer.createSkillFromThisChat')}</span>
              </button>
              <button type="button" className="ca-menu__item" onClick={() => { setMenu(null); skillsOpenAtom.set(true) }}>
                <span className="ca-icon">{Icons.files}</span><span className="ca-menu__grow">{t('composer.manageSkills')}</span>
              </button>
              <div className="ca-menu__sep" />
              {skills.map((s) => (
                <button key={s.id} type="button" className="ca-menu__item" title={s.instructions} onClick={() => useSkill(s)}>
                  <span className="ca-menu__grow">{s.name}</span>
                  {s.custom && <span className="ca-menu__key">{t('composer.personal')}</span>}
                </button>
              ))}
            </div>
          )}
          {menu === 'assets' && (
            <div className="ca-menu ca-assets-pop">
              <AssetGrid only="image" onPick={(item) => { setMenu(null); void placeAsset(editor, item).then((id) => id && addRef(id)) }} />
            </div>
          )}
          {menu === 'create' && (
            <div className="ca-menu ca-skilled">
              <div className="ca-gen__title">{t('composer.skillCreator')}</div>
              <SkillForm
                initial={{ id: uuid().slice(0, 8), name: '', instructions: '', custom: true }}
                onDone={(s) => {
                  setMenu(null)
                  if (!s) return
                  void saveSkill(s).then(() => skillAtom.set(s)).catch((e) => onError(String(e)))
                }}
              />
            </div>
          )}
        </Popover>
        <Popover
          open={menu === 'mode'}
          onOpenChange={(o) => setMenu(o ? 'mode' : null)}
          side="top"
          trigger={({ open, toggle }) => (
            <button type="button" className="ca-bar__btn ca-composer__mode" data-open={open || undefined} onClick={toggle}>
              <span className="ca-icon">{Icons[modeInfo[2]]}</span><span>{modeInfo[1]}</span><span className="ca-icon">{Icons.chevron}</span>
            </button>
          )}
        >
          <div className="ca-menu">
            {MODES.map(([m, label, icon]) => (
              <button key={m} type="button" className="ca-menu__item" onClick={() => { agentModeAtom.set(m); setMenu(null) }}>
                <span className="ca-icon">{Icons[icon]}</span><span className="ca-menu__grow">{label}</span>
                {m === mode && <span className="ca-icon">{Icons.check}</span>}
              </button>
            ))}
          </div>
        </Popover>
        {mode !== 'agent' && <DirectPills editor={editor} video={mode === 'video'} />}
        {refs.length > 1 && <EachButton compact on={each.on} onChange={each.setOn} />}
        {mode === 'agent' && !agentOff && <AgentPicker onError={onError} />}
        {mode === 'agent' && !agentOff && <RefFrameButton editor={editor} />}
        {mode === 'agent' && <ModelPrefs onError={onError} />}
        <div className="ca-gen__spacer" />
        <VoiceButton onError={onError} onText={(t) => draftAtom.set(`${draftAtom.get()}${draftAtom.get() ? ' ' : ''}${t}`)} />
        <button type="button" className="ca-gen__send" disabled={!draft.trim() || agentOff} title={busy && mode === 'agent' ? t('composer.sendQueuedAfterTheCurrent') : t('composer.send')} onClick={send}>
          <span className="ca-icon">{Icons.send}</span>
        </button>
      </div>
    </div>
  )
}
