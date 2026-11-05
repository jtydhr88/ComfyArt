import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useValue, type Editor, type TLShapeId } from 'tldraw'

import { agentModeAtom, DOC_ACCEPT, docsAtom, draftAtom, eachLine, eachRuns, extraRefsAtom, looseRefsAtom, generateDirect, isRefShape, kitsAtom, refKindOf, sendToAgent, srcOf, uploadRefs, type RefShape } from '../agent'

import { keyMissing, keySettingsOpenAtom, keyStatusAtom, refreshKeyStatus } from '../wavespeedKey'
import { EachButton, EachRole, useEach } from './EachToggle'
import { RefFrameButton } from './RefFrameButton'
import { listAssets, placeAsset, type AssetItem } from '../assets'
import { imageUrl } from '../comfy'
import { botEnabledAtom, loadProviders, loadSettings, messagesAtom, providerLabel, providersStateAtom, stopTurn } from '../bot'
import { errorText } from '../jobs'
import { KIND_LABELS, libraryAtom } from '../library'
import type { AudioShape } from '../shapes/EmbedShapes'
import { loadListedSkills, saveSkill, skillAtom, skillCreatorAtom, skillNoticeAtom, type Skill } from '../skills'
import { AssetGrid } from './AssetPicker'
import { schedulesOpenAtom } from '../schedules'
import { AgentExtras, AgentItems, shortLabel, useCurrentAgent } from './AgentPicker'
import { AgentLogo } from './agentLogos'
import { Icons } from './icons'
import { SkillChip, chipBackspace } from './SkillChip'
import { ModelPrefs } from './ModelPrefs'
import { DirectPills } from './DirectPills'
import { ComposerSlot, useSlot } from './ComposerSlot'
import { ArtiMascot } from './ArtiMascot'
import { SkillForm, skillsOpenAtom } from './SkillsDialog'
import { MODE_OPTIONS, modeOf } from './modeOptions'
import { Popover } from './Popover'
import { t } from '../i18n'
import { mergeRefIds, removeRefId } from '../refDedupe'
import { uuid } from '../id'
import { isEnter } from './keys'

const REVIEW_PROMPT = t('composer.canvasReviewUseGetCanvas')
const SKILL_PROMPT = t('composer.turnTheApproachCompletedIn')

export const FILE_ACCEPT = `image/*,video/*,audio/*,${DOC_ACCEPT}`

/** #362: @ menu shows ≤N rows per group before … More (reference density). */
const AT_GROUP_LIMIT = 5
/** #362 SHOULD: collapse individual capsules when selection exceeds this. */
const CAPSULE_SUMMARY_AT = 10


function imageName(editor: Editor, s: RefShape) {
  if (refKindOf(s) === 'audio') return (s as AudioShape).props.name || t('composer.audio')
  const v = s as Exclude<RefShape, AudioShape>
  const asset = v.props.assetId ? editor.getAsset(v.props.assetId) : null
  return (asset?.type === v.type && asset.props.name) || (v.type === 'video' ? t('common.video') : t('common.image'))
}

function truncateLabel(name: string, max = 8) {
  const chars = [...name]
  return chars.length > max ? `${chars.slice(0, max).join('')}…` : name
}

function RefThumb({ editor, s }: { editor: Editor; s: RefShape }) {
  const kind = refKindOf(s)
  if (kind === 'audio') return <span className="ca-icon">{Icons.music}</span>
  return kind === 'video' ? <video src={srcOf(editor, s) ?? ''} muted preload="metadata" /> : <img src={imageUrl(srcOf(editor, s) ?? '')} alt="" />
}

/** #250: how far the composer bar has to fold so +, voice and send stay inside it.
 *  0 full · 1 settings drops its tail ("1K · 1:1") · 2 settings icon only · 3 model icon only (the mode button always keeps its text).
 *  The group never squeezes its buttons (no cut-off text); it folds one step at a time until nothing overflows. */
function useFootFit(dep: unknown) {
  const ref = useRef<HTMLDivElement>(null)
  const [fit, setFit] = useState(0)
  const [width, setWidth] = useState(0)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(() => setWidth(Math.round(el.clientWidth)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  useLayoutEffect(() => { setFit(0) }, [width, dep])
  useLayoutEffect(() => {
    const mid = ref.current?.querySelector('.ca-composer__mid')
    if (mid && fit < 3 && mid.scrollWidth > mid.clientWidth) setFit(fit + 1)
  })
  return { ref, fit }
}

export function Composer({ editor, busy, onError }: { editor: Editor; busy: boolean; onError: (msg: string) => void }) {
  const started = useValue('chat started', () => messagesAtom.get().length > 0, [])
  const draft = useValue(draftAtom)
  const mode = useValue(agentModeAtom)
  const enabled = useValue(botEnabledAtom)
  const agentOff = mode === 'agent' && enabled === false
  const listLoading = useValue('agent list loading', () => providersStateAtom.get().state === 'loading', [])
  const agentLoading = mode === 'agent' && listLoading  // #294: no sending to an Agent until the list has arrived
  const skill = useValue(skillAtom)
  const skillNotice = useValue(skillNoticeAtom)  // #673
  const skillCreator = useValue(skillCreatorAtom)
  const extra = useValue(extraRefsAtom)
  const loose = useValue(looseRefsAtom)  // #644: composer-only refs, no canvas shape
  const kits = useValue(kitsAtom)
  const library = useValue(libraryAtom)
  const docs = useValue(docsAtom)
  const selected = useValue('selected media', () => editor.getSelectedShapes().filter(isRefShape), [editor])
  const images = useValue('canvas media', () => editor.getCurrentPageShapes().filter(isRefShape), [editor])
  const [menu, setMenu] = useState<'plus' | 'skills' | 'assets' | 'mode' | 'create' | null>(null)
  const [skills, setSkills] = useState<Skill[]>([])
  const [atAssets, setAtAssets] = useState<AssetItem[]>([])
  const file = useRef<HTMLInputElement>(null)
  const [hidden, setHidden] = useState<TLShapeId[]>([])
  const [drop, setDrop] = useState(false)
  const each = useEach()
  // #250 v2: one action slot on the right. Empty input → voice (waveform); text or an attached image → send (↑).
  // Whitespace-only counts as empty. The slot does not flip while an IME is composing, and stays on voice while recording.
  const [composing, setComposing] = useState(false)
  const content = !!draft.trim()
  const foot = useFootFit(`${mode}|${draft.length > 0}`)

  // #389: selected + @-mentioned → one chip per shape id
  const refs = mergeRefIds(selected.map((s) => s.id), hidden, extra)
    .map((id) => selected.find((s) => s.id === id) ?? editor.getShape(id))
    .filter((s): s is RefShape => !!s && isRefShape(s))
  const slash = /^\/(\S*)$/.exec(draft)
  const at = /(?:^|\s)@(\S*)$/.exec(draft)

  useEffect(() => {
    if (menu === 'skills' || slash) void loadListedSkills().then(setSkills)
  }, [menu, !!slash])

  // #362: load 素材 for @ menu (no model group). Fail soft → empty 素材 group.
  useEffect(() => {
    if (!at) { setAtAssets([]); return }
    let alive = true
    void listAssets('input,output', at[1] || '')
      .then((page) => { if (alive) setAtAssets(page.items) })
      .catch(() => { if (alive) setAtAssets([]) })
    return () => { alive = false }
  }, [!!at, at?.[1]])

  useEffect(() => {
    setHidden((h) => h.filter((id) => selected.some((s) => s.id === id)))
  }, [selected])

  const addRef = (id: TLShapeId) => {
    setHidden((h) => h.filter((x) => x !== id))
    extraRefsAtom.set([...extraRefsAtom.get().filter((x) => x !== id), id])
  }
  const removeRef = (id: TLShapeId) => {
    const next = removeRefId(id, selected.map((s) => s.id), hidden, extraRefsAtom.get())
    extraRefsAtom.set(next.extra)
    setHidden(next.hidden)
  }
  const useSkill = (s: Skill) => { skillNoticeAtom.set(null); skillAtom.set(s); setMenu(null); if (slash) draftAtom.set('') }

  const fail = (e: unknown) => onError(errorText(e))
  const upload = (files: FileList | null) => uploadRefs(editor, Array.from(files ?? [])).catch(fail)
  const imageFiles = (list: DataTransfer) => Array.from(list.files)
  const { showSend, setVoice } = useSlot(content || refs.length > 0 || loose.length > 0, composing)
  const send = () => {
    const text = draft.trim()
    if ((!text && !refs.length && !loose.length) || agentOff || agentLoading) return  // #268: an image with no text counts as content
    // #294: after a failed Agent-list load, every agent-mode send re-loads the list once first.
    // Still failing → toast the real error and keep the draft; succeeded → send as normal.
    if (mode === 'agent' && providersStateAtom.get().state === 'error') {
      void loadProviders().then(send, (e) => onError(t('bot.agentListLoadFailed', errorText(e))))
      return
    }
    // #305: guide once without wiping the draft when Key is missing
    const go = async () => {
      let key = keyStatusAtom.get()
      if (!key) key = await refreshKeyStatus()
      if (keyMissing(key)) {
        keySettingsOpenAtom.set(true)
        return
      }
      const keptRefs = refs
      const keptSkill = skill
      const keptKits = kits
      const keptDocs = docs
      const keptLoose = loose
      const creating = skillCreatorAtom.get().on
      // #491 A3: the user's words go in the bubble; the creator instruction rides in the hidden context
      const creatorContext = creating && text ? t('composer.skillCreatorPrefill', text) : ''
      const creatorChip = creating ? t(skillCreatorAtom.get().chip ?? 'composer.skillCreator') : ''
      draftAtom.set('')
      extraRefsAtom.set([])
      looseRefsAtom.set([])
      kitsAtom.set([])
      if (creating) skillCreatorAtom.set({ on: false })
      if (mode === 'agent') {
        skillAtom.set(null)
        docsAtom.set([])
      }
      const targets = keptRefs.length > 1 ? each.targets(keptRefs) : []
      each.reset()
      try {
        if (mode === 'agent') await sendToAgent(editor, text, keptRefs, creating ? null : keptSkill, keptKits, keptDocs, [targets.length ? eachLine(keptRefs, targets) : '', creatorContext].filter(Boolean).join('\n'), { ...(creatorChip ? { chip: creatorChip } : undefined), loose: keptLoose })
        else await generateDirect(editor, text, eachRuns(keptRefs, targets, () => text).map((run) => ({ ...run, loose: keptLoose.map((l) => l.src) })), mode === 'video', onError)
      } catch (e) {
        // restore composer content if the send never reached the chat / job
        draftAtom.set(text || draftAtom.get())
        if (keptLoose.length) looseRefsAtom.set(keptLoose)
        fail(e)
      }
    }
    void go()
  }

  const filtered = slash ? skills.filter((s) => s.name.toLowerCase().includes(slash[1].toLowerCase())) : skills  // #673: '/ppt' finds PPT
  // #362 @ menu: exactly 参考 → 本项目 → 素材. NO model group (voids old Assets/Model fake-align).
  const atQ = (at?.[1] ?? '').toLowerCase()
  const atRefs = at ? library.filter((k) => k.name.toLowerCase().includes(atQ) && !kits.some((x) => x.id === k.id)) : []
  const atProject = at ? images.filter((s) => imageName(editor, s).toLowerCase().includes(atQ)) : []
  const atMats = at ? atAssets.filter((a) => a.name.toLowerCase().includes(atQ)) : []
  const atOpen = !!at
  const clearAt = () => draftAtom.set(draft.slice(0, at!.index) + (at!.index ? ' ' : ''))
  const clearAllCapsules = () => {
    extraRefsAtom.set([])
    looseRefsAtom.set([])
    setHidden(selected.map((s) => s.id))
  }
  const modeInfo = modeOf(mode)
  const agent = useCurrentAgent()

  // #371: typing = non-empty draft (CN --typing); play = busy after send
  const typing = content

  return (
    <>
    {/* #644: the #673 notice sits in normal flow ABOVE the composer (clear of the mascot peek), so it never overlaps the chat's start buttons */}
    {skillNotice && (
        <div className="ca-chat__hint ca-composer__notice" role="status" data-testid="skill-hidden-notice">
          <span className="ca-menu__grow">{skillNotice}</span>
          <button type="button" className="ca-history__del" title={t('common.close')} data-testid="skill-hidden-notice-close" onClick={() => skillNoticeAtom.set(null)}>{Icons.close}</button>
        </div>
      )}
    <div
      className="ca-composer"
      data-drop={drop || undefined}
      onDragOver={(e) => { if (e.dataTransfer.types.includes('Files')) { e.preventDefault(); setDrop(true) } }}
      onDragLeave={() => setDrop(false)}
      onDrop={(e) => { setDrop(false); const files = imageFiles(e.dataTransfer); if (files.length) { e.preventDefault(); void uploadRefs(editor, files).catch(fail) } }}
    >
      {/* #371 P1-mascot: left-top peek; idle static frame 0; --play/--typing animate */}
      <ArtiMascot busy={busy} typing={typing} />
      {(slash && filtered.length > 0) && (
        <div className="ca-menu ca-composer__suggest" data-testid="slash-menu">
          {filtered.slice(0, 8).map((s) => (
            <button key={s.id} data-skill={s.id} type="button" className="ca-menu__item" onClick={() => useSkill(s)}>
              <span className="ca-icon">{Icons.skill}</span><span className="ca-menu__grow">{s.name}</span>
            </button>
          ))}
        </div>
      )}
      {/* #362: @ popup — groups 参考 → 本项目 → 素材 only; never a model group */}
      {atOpen && (
        <div className="ca-menu ca-composer__suggest ca-at-menu" data-testid="at-menu" data-at-capsule="362">
          <div className="ca-at-menu__filter" data-testid="at-menu-filter">
            {atQ ? `@${at![1]}` : t('composer.atFilterPlaceholder')}
          </div>
          <div className="ca-at-menu__group" data-at-group="reference">
            <div className="ca-at-menu__title">{t('composer.atGroupReference')}</div>
            {atRefs.slice(0, AT_GROUP_LIMIT).map((k) => (
              <button key={k.id} type="button" className="ca-menu__item ca-at-menu__row" onClick={() => { kitsAtom.set([...kits, k]); clearAt() }}>
                {k.images[0]
                  ? <img className="ca-at-menu__thumb" src={k.images[0]} alt="" />
                  : <span className="ca-at-menu__thumb ca-at-menu__thumb--empty"><span className="ca-icon">{Icons.assets}</span></span>}
                <span className="ca-menu__grow">{k.name}</span>
              </button>
            ))}
            {atRefs.length > AT_GROUP_LIMIT && (
              <button type="button" className="ca-menu__item ca-at-menu__more" onClick={() => setMenu('assets')}>
                <span className="ca-at-menu__more-mark">…</span><span className="ca-menu__grow">{t('composer.atMore')}</span>
              </button>
            )}
          </div>
          <div className="ca-at-menu__group" data-at-group="project">
            <div className="ca-at-menu__title">{t('composer.atGroupProject')}</div>
            {atProject.slice(0, AT_GROUP_LIMIT).map((s) => (
              <button key={s.id} type="button" className="ca-menu__item ca-at-menu__row" onClick={() => { addRef(s.id); clearAt() }}>
                <span className="ca-at-menu__thumb">
                  {s.type === 'image' || s.type === 'video'
                    ? (s.type === 'video'
                      ? <><video src={srcOf(editor, s) ?? ''} muted preload="metadata" /><span className="ca-at-menu__play">{Icons.play}</span></>
                      : <img src={imageUrl(srcOf(editor, s) ?? '')} alt="" />)
                    : <span className="ca-icon">{Icons.music}</span>}
                </span>
                <span className="ca-menu__grow">{imageName(editor, s)}</span>
              </button>
            ))}
            {atProject.length > AT_GROUP_LIMIT && (
              <div className="ca-menu__item ca-at-menu__more"><span className="ca-at-menu__more-mark">…</span><span className="ca-menu__grow">{t('composer.atMore')}</span></div>
            )}
          </div>
          <div className="ca-at-menu__group" data-at-group="assets">
            <div className="ca-at-menu__title">{t('composer.atGroupAssets')}</div>
            {atMats.slice(0, AT_GROUP_LIMIT).map((a) => (
              <button key={a.id} type="button" className="ca-menu__item ca-at-menu__row" onClick={() => {
                clearAt()
                void placeAsset(editor, a).then((id) => id && addRef(id)).catch(fail)
              }}>
                <span className="ca-at-menu__thumb">
                  {a.kind === 'video'
                    ? <><img src={a.src} alt="" /><span className="ca-at-menu__play">{Icons.play}</span></>
                    : <img src={imageUrl(a.src)} alt="" />}
                </span>
                <span className="ca-menu__grow">{a.name || t('common.image')}</span>
              </button>
            ))}
            {atMats.length > AT_GROUP_LIMIT && (
              <button type="button" className="ca-menu__item ca-at-menu__more" onClick={() => setMenu('assets')}>
                <span className="ca-at-menu__more-mark">…</span><span className="ca-menu__grow">{t('composer.atMore')}</span>
              </button>
            )}
          </div>
        </div>
      )}
      {(refs.length > 0 || loose.length > 0 || skill || skillCreator.on || kits.length > 0 || (mode === 'agent' && docs.length > 0)) && (
        <div className="ca-composer__chips">
          {kits.map((k) => (
            <span key={k.id} className="ca-chip">
              <span className="ca-icon">{Icons.assets}</span>{k.name || t('kitEditor.untitled', KIND_LABELS[k.kind])}
              <button type="button" title={t('common.remove')} onClick={() => kitsAtom.set(kits.filter((x) => x.id !== k.id))}>{Icons.close}</button>
            </span>
          ))}
          {skill && (
            <SkillChip name={skill.name} testId="composer-skill-chip" />
          )}
          {skillCreator.on && (
            <SkillChip name={t(skillCreator.chip ?? 'composer.skillCreator')} testId="skill-creator-chip" />
          )}
          {mode === 'agent' && docs.map((d) => (
            <span key={d.src} className="ca-chip" title={d.name}>
              <span className="ca-icon">{Icons.page}</span><span className="ca-chip__name">{d.name}</span>
              <button type="button" title={t('common.remove')} onClick={() => docsAtom.set(docs.filter((x) => x.src !== d.src))}>{Icons.close}</button>
            </span>
          ))}
          {/* #644: composer-only refs (old hidden-skill link) — same capsule look, never a canvas shape */}
          {loose.map((l, i) => (
            <span key={`loose-${i}`} className="ca-chip ca-chip--capsule" data-testid="composer-capsule" data-loose title={l.name}>
              <span className="ca-chip__thumb"><img src={l.src} alt="" /></span>
              <span className="ca-chip__name">{truncateLabel(l.name)}</span>
              <button type="button" title={t('common.remove')} onClick={() => looseRefsAtom.set(loose.filter((_, j) => j !== i))}>{Icons.close}</button>
            </span>
          ))}
          {/* #362: canvas multi-select → composer capsules (thumb + truncated label); removable; no auto-send */}
          {refs.length > CAPSULE_SUMMARY_AT ? (
            <span className="ca-chip ca-chip--capsule ca-chip--summary" data-testid="capsule-summary" title={t('composer.selectedCount', refs.length)}>
              <span className="ca-chip__name">{t('composer.selectedCount', refs.length)}</span>
              <button type="button" title={t('common.remove')} onClick={clearAllCapsules}>{Icons.close}</button>
            </span>
          ) : refs.map((r) => (
            <span
              key={r.id}
              className="ca-chip ca-chip--capsule"
              data-testid="composer-capsule"
              data-audio={refKindOf(r) === 'audio' || undefined}
              title={imageName(editor, r)}
            >
              <span className="ca-chip__thumb"><RefThumb editor={editor} s={r} /></span>
              <span className="ca-chip__name">{truncateLabel(imageName(editor, r))}</span>
              <button type="button" title={t('common.remove')} onClick={() => removeRef(r.id)}>{Icons.close}</button>
              {each.on && refs.length > 1 && <EachRole shared={each.isShared(r.id)} onToggle={() => each.toggleShared(r.id)} />}
            </span>
          ))}
        </div>
      )}
      <textarea
        className="ca-composer__input"
        value={draft}
        placeholder={skillCreator.on ? '' : t('composer.describeYourDesignNeedsFor')} /* #650: gold creator input is empty */
        onChange={(e) => draftAtom.set(e.target.value)}
        onCompositionStart={() => setComposing(true)}
        onCompositionEnd={() => setComposing(false)}
        onPaste={(e) => { const files = imageFiles(e.clipboardData); if (!files.length) return; e.preventDefault(); e.stopPropagation(); void uploadRefs(editor, files).catch(fail) }}
        onKeyDown={(e) => {
          e.stopPropagation()
          // #491: chips have no ×; Backspace at the start of the input removes them (Skill Creator first, then the skill)
          if ((skillCreator.on || skill) && chipBackspace(e)) {
            e.preventDefault()
            if (skillCreator.on) skillCreatorAtom.set({ on: false })
            else skillAtom.set(null)
            return
          }
          if (isEnter(e) && !e.shiftKey && !slash && !atOpen) {
            e.preventDefault()
            send()
          }
        }}
      />
      <div ref={foot.ref} className="ca-composer__foot" data-fit={foot.fit || undefined}>
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
              <button type="button" className="ca-menu__item" data-testid="skill-creator-start" onClick={() => { setMenu(null); skillCreatorAtom.set({ on: true }); agentModeAtom.set('agent') }}>
                <span className="ca-icon">{Icons.plus}</span><span className="ca-menu__grow">{t('composer.skillCreator')}</span>
              </button>
              <button type="button" className="ca-menu__item" disabled={!started} onClick={() => { setMenu(null); void sendToAgent(editor, SKILL_PROMPT, [], null).catch(fail) }}>
                <span className="ca-icon">{Icons.agent}</span><span className="ca-menu__grow">{t('composer.createSkillFromThisChat')}</span>
              </button>
              <button type="button" className="ca-menu__item" onClick={() => setMenu('create')}>
                <span className="ca-icon">{Icons.files}</span><span className="ca-menu__grow">{t('composer.skillCreatorForm')}</span>
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
            <div className="ca-menu ca-skilled" data-testid="skill-creator-form-fallback">
              <div className="ca-gen__title">{t('composer.skillCreator')} · {t('composer.skillCreatorForm')}</div>
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
        {/* #250: mode / settings / model share one shrinkable group, so +, voice and send always stay inside the bar */}
        <div className="ca-composer__mid">
        <Popover
          open={menu === 'mode'}
          onOpenChange={(o) => { setMenu(o ? 'mode' : null); if (o) void Promise.all([loadProviders(), loadSettings()]).catch(fail) }}
          side="top"
          within=".ca-composer"
          trigger={({ open, toggle }) => (
            <button type="button" className="ca-bar__btn ca-composer__mode" title={mode === 'agent' && agent ? providerLabel(agent) : modeInfo[1]} data-agent={mode === 'agent' && agent ? agent.id : undefined} data-open={open || undefined} onClick={toggle}>
              {/* Ashley: agent pill shows product shortLabel (e.g. ComfyArt); image/video keep mode name. Home matches. */}
              {mode === 'agent' && agent ? <><AgentLogo id={agent.id} /><span className="ca-composer__modetext">{shortLabel(agent)}</span></> : <><span className="ca-icon">{Icons[modeInfo[2]]}</span><span className="ca-composer__modetext">{modeInfo[1]}</span></>}<span className="ca-icon">{Icons.chevron}</span>
            </button>
          )}
        >
          <div className="ca-menu ca-agentpick">
            <AgentItems onError={onError} current={mode === 'agent'} close={() => setMenu(null)} onChosen={() => agentModeAtom.set('agent')} />
            <div className="ca-menu__sep" />
            {MODE_OPTIONS.filter(([m]) => m !== 'agent').map(([m, label, icon]) => (
              <button key={m} type="button" className="ca-menu__item" onClick={() => { agentModeAtom.set(m); setMenu(null) }}>
                <span className="ca-icon">{Icons[icon]}</span><span className="ca-menu__grow">{label}</span>
                {m === mode && <span className="ca-icon">{Icons.check}</span>}
              </button>
            ))}
            {mode === 'agent' && <><div className="ca-menu__sep" /><AgentExtras onError={onError} close={() => setMenu(null)} /></>}
          </div>
        </Popover>
        {mode !== 'agent' && <DirectPills video={mode === 'video'} />}
        </div>
        {/* #268: right group = reference / preferences (agent) or settings, next to voice/send */}
        <div className="ca-gen__spacer" />
        {refs.length > 1 && <EachButton compact on={each.on} onChange={each.setOn} />}
        {mode === 'agent' && !agentOff && <RefFrameButton editor={editor} />}
        {mode === 'agent' && <ModelPrefs onError={onError} />}
        <ComposerSlot showSend={showSend} setVoice={setVoice} canSend={(content || refs.length > 0) && !agentOff && !agentLoading} onSend={send}
          title={agentLoading ? t('bot.agentListLoading') : busy && mode === 'agent' ? t('composer.sendQueuedAfterTheCurrent') : t('composer.send')} onError={onError}
          onStop={busy ? () => void stopTurn().catch((e) => onError(errorText(e))) : undefined}
          onText={(t) => draftAtom.set(`${draftAtom.get()}${draftAtom.get() ? ' ' : ''}${t}`)} />
      </div>
    </div>
    </>
  )
}
