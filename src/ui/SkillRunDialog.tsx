/** #494-2 — a skill's OWN in-page dialog (card / title / hover 「试用此技能」 all open this). Left: title, author,
 *  description + a 2-column template grid from presets[]. Right: 「开始制作」 panel with the current template and
 *  that skill's inputs[] (labels / placeholders / defaults / required from data). No skill ids are named here.
 *  New because main had no form that renders a data schema. 「详情」 keeps main's #484 edit page (openSkillEditor). */
import { useState } from 'react'

import { uploadSkillImage, loc, loadFavourites, missingInputs, presetImage, recordSkillUse, skillAuthor, skillMeta, skillMetaLabel, skillDefaults, skillDescription, skillPreset, skillRunParams, skillShareUrl, toggleFavourite, type Skill } from '../skills'
import { newProject } from '../projects'
import { BRAND } from '../brand'
import { copyText } from '../clipboard'
import { t } from '../i18n'
import { useEscape } from './escape'
import { Icons } from './icons'
import { openSkillEditor } from './SkillsDialog'
import { SkillExamples } from './SkillExamples'

export function SkillRunDialog({ skill, presetId, onClose, run = newProject }: {
  skill: Skill; presetId?: string | null; onClose: () => void
  /** injectable for tests; default leaves for a new project exactly like main's card click */
  run?: (params: Record<string, string | string[]>) => void
}) {
  const [values, setValues] = useState(() => skillDefaults(skill))
  const [preset, setPreset] = useState(() => skillPreset(skill, presetId)?.id ?? null)
  const [uploading, setUploading] = useState<string | null>(null)
  const [fav, setFav] = useState(() => loadFavourites().includes(skill.id))
  const [shared, setShared] = useState(false)
  const missing = missingInputs(skill, values)
  const chosen = skillPreset(skill, preset)
  const author = skillAuthor(skill)
  const desc = skillDescription(skill)
  const meta = skillMeta(skill)
  const [zoom, setZoom] = useState<string | null>(null)
  const set = (key: string, v: string) => setValues((cur) => ({ ...cur, [key]: v }))
  const stop = (e: React.KeyboardEvent) => e.stopPropagation()
  const onShare = () => {
    const link = skillShareUrl(skill.id)
    if (!link) return
    void copyText(link).then(() => { setShared(true); setTimeout(() => setShared(false), 1500) })
  }
  const onFav = () => setFav(toggleFavourite(skill.id).includes(skill.id))
  const onStart = () => { recordSkillUse(skill.id); run(skillRunParams(skill, values, preset)) }
  useEscape(true, onClose)
  return (
    <div className="ca-modal" data-testid="skill-run-modal" onPointerDown={(e) => { e.stopPropagation(); if (e.target === e.currentTarget) onClose() }}>
      <div className="ca-modal__card ca-skillrun" data-testid="skill-run-dialog" data-skill={skill.id}>
        <div className="ca-skillrun__left">
          {/* #494-2 对照结构: title / author / desc stay pinned above the template grid */}
          <header className="ca-skillrun__head" data-testid="skill-run-head">
            <h2 className="ca-skillrun__title" data-testid="skill-run-title">{skill.name}</h2>
            {/* #541/#581 creator row: 28px avatar + name; share (real clipboard) + favourite toggle (no fake count) + 详情 */}
            <div className="ca-skillrun__creator" data-testid="skill-run-creator">
              <div className="ca-skillrun__author" data-testid="skill-run-author" data-kind={author.kind}>
                {author.kind === 'builtin'
                  ? <img className="ca-swall__avatar" src={BRAND.logoPath} alt="" aria-hidden="true" />
                  : <span className="ca-swall__avatar" aria-hidden="true"><span className="ca-icon">{Icons.user}</span></span>}
                {author.label}
              </div>
              <div className="ca-skillrun__actions" data-testid="skill-run-actions">
                <button type="button" className="ca-skillrun__iconbtn" data-testid="skill-run-share"
                  title={shared ? t('common.copied') : t('skillRun.share')}
                  aria-label={t('skillRun.share')}
                  onClick={onShare}>
                  <span className="ca-icon">{shared ? Icons.check : Icons.share}</span>
                </button>
                <button type="button" className="ca-skillrun__iconbtn" data-testid="skill-run-favourite"
                  data-on={fav || undefined}
                  aria-pressed={fav}
                  title={fav ? t('home.skillsUnfavourite') : t('home.skillsFavourite')}
                  onClick={onFav}>
                  <span className="ca-icon">{fav ? Icons.bookmarkFilled : Icons.bookmark}</span>
                </button>
                <button type="button" className="ca-skillrun__action" data-testid="skill-run-detail" onClick={() => { onClose(); openSkillEditor(skill.id) }}>{t('skillRun.detail')}</button>
              </div>
            </div>
            {desc && <p className="ca-skillrun__desc" data-testid="skill-run-desc">{desc}</p>}
            {meta && <p className="ca-skillrun__meta" data-testid="skill-run-meta">{skillMetaLabel(meta)}</p>}
          </header>
          {(!!skill.presets?.length || !!skill.examples?.length) && (
            <div className="ca-skillrun__templates">
              <SkillExamples examples={skill.examples} />
              {!!skill.presets?.length && <div role="radiogroup" data-testid="skill-run-presets">
              <div className="ca-skillrun__section">{t('skillRun.templates')}</div>
              <div className="ca-skillrun__grid">
                {skill.presets.map((p) => {
                  const img = presetImage(skill, p)
                  const on = preset === p.id
                  return (
                    <div key={p.id} className="ca-skillrun__tile" data-on={on || undefined}>
                      <button type="button" role="radio" aria-checked={on} data-on={on || undefined}
                        className="ca-skillrun__preset" data-testid="skill-run-preset" data-preset={p.id} onClick={() => setPreset(p.id)}>
                        <span className="ca-skillrun__presetimg">
                          {img ? <img src={img} alt="" /> : <span className="ca-icon">{Icons.skill}</span>}
                          <span className="ca-skillrun__pick">{t('skillRun.select')}</span>
                          {on && <span className="ca-skillrun__check" aria-hidden="true"><span className="ca-icon">{Icons.check}</span></span>}
                        </span>
                        <span className="ca-skillrun__presetname">{loc(p.name)}</span>
                      </button>
                      {img && <button type="button" className="ca-skillrun__zoom" data-testid="skill-run-zoom" title={t('skillRun.zoom')} aria-label={t('skillRun.zoom')}
                        onClick={() => setZoom(img)}><span className="ca-icon">{Icons.expand}</span></button>}
                    </div>
                  )
                })}
              </div>
              </div>}
            </div>
          )}
        </div>
        <div className="ca-skillrun__right">
          <div className="ca-skillrun__righthead">
            <span>{t('skillRun.start')}</span>
            <button type="button" className="ca-panel__icon" title={t('common.close')} onClick={onClose}>{Icons.close}</button>
          </div>
          <div className="ca-skillrun__body">
            {chosen && (
              <div className="ca-skillrun__current" data-testid="skill-run-current">
                <span className="ca-skillrun__currentlabel">{t('skillRun.currentTemplate')}</span>
                <div className="ca-skillrun__currentrow">
                  <span className="ca-skillrun__currentthumb">
                    {presetImage(skill, chosen) ? <img src={presetImage(skill, chosen)!} alt="" /> : <span className="ca-icon">{Icons.skill}</span>}
                  </span>
                  <span className="ca-skillrun__currentname">{loc(chosen.name)}</span>
                  <span className="ca-skillrun__currenthint">{t('skillRun.pickLeft')}</span>
                </div>
              </div>
            )}
            {/* join existing ca-skillform system; field column mirrors Loomic template-dialog .fields/.field */}
            <div className="ca-skillform" data-testid="skill-run-form">
            {(skill.inputs ?? []).map((f) => {
              const id = `skill-run-${f.key}`
              const label = <label className="ca-skillform__label" htmlFor={id}>{loc(f.label)}{f.required && <span className="ca-skillrun__req" aria-hidden="true"> *</span>}</label>
              const ph = f.placeholder ? loc(f.placeholder) : ''
              const common = { id, 'data-testid': 'skill-run-field', 'data-key': f.key, 'data-type': f.type, required: f.required, 'aria-required': f.required || undefined }
              if (f.type === 'select') return (
                <div key={f.key} className="ca-skillrun__field">
                  {label}
                  <select {...common} className="ca-panel__input" value={values[f.key] ?? ''} onChange={(e) => set(f.key, e.target.value)} onKeyDown={stop}>
                    {f.options?.map((o) => <option key={o.value} value={o.value}>{loc(o.label)}</option>)}
                  </select>
                </div>
              )
              if (f.type === 'textarea') return (
                <div key={f.key} className="ca-skillrun__field">
                  {label}
                  <textarea {...common} className="ca-panel__prompt ca-panel__prompt--boxed" rows={3} placeholder={ph} value={values[f.key] ?? ''} onChange={(e) => set(f.key, e.target.value)} onKeyDown={stop} />
                </div>
              )
              if (f.type === 'image') return (
                <div key={f.key} className="ca-skillrun__field">
                  {label}
                  <div className="ca-gen__refs ca-skillrun__uploadwrap" {...common}>
                    {values[f.key]
                      ? <span className="ca-gen__ref"><img src={values[f.key]} alt="" /><button type="button" title={t('common.remove')} onClick={() => set(f.key, '')}>{Icons.close}</button></span>
                      : <label className="ca-skillrun__upload" data-testid="skill-run-upload"><span className="ca-icon">{Icons.image}</span><span>{uploading === f.key ? t('skillRun.uploading') : t('skillRun.uploadHint')}</span>
                          <input id={id} type="file" accept="image/*" hidden onChange={(e) => {
                            const file = e.target.files?.[0]; e.target.value = ''
                            if (!file) return
                            setUploading(f.key)
                            void uploadSkillImage(file, skill.id).then((src) => set(f.key, src)).finally(() => setUploading(null))
                          }} /></label>}
                  </div>
                </div>
              )
              return (
                <div key={f.key} className="ca-skillrun__field">
                  {label}
                  <input {...common} className="ca-panel__input" placeholder={ph} value={values[f.key] ?? ''} onChange={(e) => set(f.key, e.target.value)} onKeyDown={stop} />
                </div>
              )
            })}
            </div>
          </div>
          <div className="ca-skillrun__foot">
            <button type="button" className="ca-panel__primary ca-skillrun__go" data-testid="skill-run-go" disabled={missing.length > 0 || !!uploading}
              onClick={onStart}>{t('skillRun.start')}</button>
          </div>
        </div>
        {zoom && (
          <button type="button" className="ca-skillrun__zoomview" data-testid="skill-run-zoomview" title={t('common.close')} onClick={() => setZoom(null)}>
            <img src={zoom} alt="" />
          </button>
        )}
      </div>
    </div>
  )
}
