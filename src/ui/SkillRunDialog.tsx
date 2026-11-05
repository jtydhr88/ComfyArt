/** #494-2 — a skill's OWN in-page dialog (card / title / hover 「试用此技能」 all open this). Left: title, author,
 *  description + data-driven media: examples[] → SkillExamples (single / carousel / video); presets[] template grid
 *  only when a preset carries its own image/video (#637 — no cover-fallback 「模板」 inventing Examples-only gold).
 *  When examples/presetTiles are empty but skillCover exists, show a dedicated cover main-preview (not SkillExamples).
 *  Right: header 「开始创作」 / CTA 「开始制作」 (#601) with the current template and that skill's inputs[].
 *  No skill ids are named here. 「详情」 keeps main's #484 edit page (openSkillEditor). */
import { useRef, useState } from 'react'

import { uploadSkillImage, isSkillMediaVideo, loc, loadFavourites, missingInputs, presetImage, presetVideo, recordSkillUse, skillAuthor, skillCover, skillCoverVideoHover, skillMeta, skillMetaLabel, skillDefaults, skillDescription, skillPreset, skillRunParams, skillShareUrl, skillMedia, toggleFavourite, type Skill, type SkillPreset } from '../skills'
import { newProject } from '../projects'
import { BRAND } from '../brand'
import { copyText } from '../clipboard'
import { t } from '../i18n'
import { useEscape } from './escape'
import { Icons } from './icons'
import { openSkillEditor } from './SkillsDialog'
import { SkillExamples } from './SkillExamples'

/** #622 — template tile: still thumb + optional preset.video muted hover/focus loop (no-video unchanged). */
function PresetTile({ skill, preset: p, on, onPick, onZoom }: {
  skill: Skill; preset: SkillPreset; on: boolean
  onPick: () => void; onZoom: (src: string) => void
}) {
  const img = presetImage(skill, p)
  const videoSrc = presetVideo(skill, p)
  const videoRef = useRef<HTMLVideoElement>(null)
  const play = () => skillCoverVideoHover(videoRef.current, 'enter')
  const stop = () => skillCoverVideoHover(videoRef.current, 'leave')
  const zoomSrc = videoSrc || img
  const item = skillMedia(skill).find((m) => m.presetId === p.id)
  const stack = item?.type === 'stack' ? (item.children ?? []).map((c) => c.url) : []
  return (
    <div className="ca-skillrun__tile" data-stack={stack.length ? stack.length : undefined} data-on={on || undefined} data-has-video={videoSrc ? '1' : undefined}>
      <button type="button" role="radio" aria-checked={on} data-on={on || undefined}
        className="ca-skillrun__preset" data-testid="skill-run-preset" data-preset={p.id}
        onClick={onPick}
        onMouseEnter={videoSrc ? play : undefined}
        onMouseLeave={videoSrc ? stop : undefined}
        onFocus={videoSrc ? play : undefined}
        onBlur={videoSrc ? stop : undefined}
      >
        <span className="ca-skillrun__presetimg">
          {img ? <img src={img} alt="" /> : <span className="ca-icon">{Icons.skill}</span>}
          {videoSrc && (
            <video
              ref={videoRef}
              className="ca-skillrun__preset-video"
              src={videoSrc}
              muted
              loop
              playsInline
              preload="metadata"
              data-testid="skill-run-preset-video"
              aria-hidden="true"
            />
          )}
          {/* #748 stack-expand: thumbs fan out on hover, collapse when selected (timings = CSS vars). */}
          {stack.length > 0 && <span className="ca-skillrun__stack" aria-hidden="true" data-testid="skill-run-stack">
            {stack.map((src, i) => <img key={i} src={src} alt="" style={{ '--i': i } as React.CSSProperties} />)}
          </span>}
          <span className="ca-skillrun__pick">{t('skillRun.select')}</span>
          {on && <span className="ca-skillrun__check" aria-hidden="true"><span className="ca-icon">{Icons.check}</span></span>}
        </span>
        <span className="ca-skillrun__presetname">{loc(p.name)}</span>
      </button>
      {zoomSrc && <button type="button" className="ca-skillrun__zoom" data-testid="skill-run-zoom" title={t('skillRun.zoom')} aria-label={t('skillRun.zoom')}
        onClick={() => onZoom(zoomSrc)}><span className="ca-icon">{Icons.expand}</span></button>}
    </div>
  )
}

export function SkillRunDialog({ skill, presetId, onClose, run = newProject }: {
  skill: Skill; presetId?: string | null; onClose: () => void
  /** injectable for tests; default leaves for a new project exactly like main's card click */
  run?: (params: Record<string, string | string[]>) => void
}) {
  const [values, setValues] = useState(() => skillDefaults(skill))
  const [preset, setPreset] = useState(() => skillPreset(skill, presetId)?.id ?? null)
  const [uploading, setUploading] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [runError, setRunError] = useState(false)
  // #687: required-field errors appear only after 开始制作 is clicked, never on open
  const [tried, setTried] = useState(false)
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
  const onStart = () => {
    if (uploading) return
    if (missing.length) { setTried(true); document.getElementById(`skill-run-${missing[0]}`)?.focus(); return }
    setRunError(false)
    recordSkillUse(skill.id)
    try { run(skillRunParams(skill, values, preset)) } catch { setRunError(true) }
  }
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
                {/* #687 P0: builtin skills never reach openSkillEditor / SKILL.md — 「详情」 only for user-created (custom) skills. */}
                {skill.custom === true && <button type="button" className="ca-skillrun__action" data-testid="skill-run-detail" onClick={() => { onClose(); openSkillEditor(skill.id) }}>{t('skillRun.detail')}</button>}
              </div>
            </div>
            {desc && <p className="ca-skillrun__desc" data-testid="skill-run-desc">{desc}</p>}
            {meta && <p className="ca-skillrun__meta" data-testid="skill-run-meta">{skillMetaLabel(meta)}</p>}
          </header>
          {(() => {
            const examples = skill.examples ?? []
            const presetTiles = skillMedia(skill).map((m) => skill.presets?.find((p) => p.id === m.presetId)).filter((p): p is SkillPreset => !!p)
            // #641: thumbnail (presetChips) with an explicit empty list still shows 「暂无示例」.
            const showEmptyExamples = !!skill.presetChips && Array.isArray(skill.examples) && skill.examples.length === 0
            const coverSrc = skillCover(skill)?.src ?? null
            // #637: Examples-only left when examples drive the gold shape; 「模板」 grid only for real preset media
            // (never invent Examples / 模板 from cover). Cover alone → dedicated main-preview hero.
            if (!examples.length && !presetTiles.length && !showEmptyExamples) {
              if (!coverSrc) return null
              return (
                <div className="ca-skillrun__templates" data-left="cover" data-testid="skill-run-cover-preview">
                  <div
                    className="ca-skillrun__stage ca-skillrun__coverstage"
                    data-testid="skill-run-cover-stage"
                    data-media="image"
                  >
                    <img src={coverSrc} alt="" data-testid="skill-run-cover-img" />
                  </div>
                </div>
              )
            }
            return (
              <div className="ca-skillrun__templates" data-left={examples.length ? (presetTiles.length ? 'both' : 'examples') : 'templates'}>
                <SkillExamples examples={skill.examples} />
                {!!presetTiles.length && (
                  <div role="radiogroup" data-testid="skill-run-presets">
                    <div className="ca-skillrun__section">{t('skillRun.templates')}</div>
                    <div className="ca-skillrun__grid">
                      {presetTiles.map((p) => (
                        <PresetTile key={p.id} skill={skill} preset={p} on={preset === p.id}
                          onPick={() => setPreset(p.id)} onZoom={setZoom} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )
          })()}
        </div>
        <div className="ca-skillrun__right">
          <div className="ca-skillrun__righthead">
            <span data-testid="skill-run-header">{t('skillRun.header')}</span>
            <button type="button" className="ca-panel__icon" data-testid="skill-run-close" title={t('common.close')} onClick={onClose}>{Icons.close}</button>
          </div>
          <div className="ca-skillrun__body">
            {chosen && (() => {
              const presetTiles = skillMedia(skill).map((m) => skill.presets?.find((p) => p.id === m.presetId)).filter((p): p is SkillPreset => !!p)
              const pickOnLeft = presetTiles.length > 0
              // #636 PRODUCT HARD LOCK: C5 nearMiss Examples-only → remove entire 「当前模板」 row.
              // Presets are default params only; never expose as select. FieldSelect+custom chevron
              // only when left has real preset media tiles (template switch). Never native system arrow.
              if (!pickOnLeft) return null
              return (
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
              )
            })()}
            {!!skill.presetChips && !!skill.presets?.length && (
              <div className="ca-skillrun__presets" data-testid="skill-run-preset-chips">
                <div className="ca-skillrun__section">{t('skillRun.presets')}</div>
                <div className="ca-skillrun__chips" role="radiogroup" aria-label={t('skillRun.presets')}>
                  {skill.presets.map((p) => (
                    <button key={p.id} type="button" role="radio" aria-checked={preset === p.id}
                      className="ca-skillrun__chip" data-testid="skill-run-preset-chip" data-preset={p.id}
                      data-on={preset === p.id || undefined}
                      onClick={() => setPreset(p.id)}>{loc(p.name)}</button>
                  ))}
                </div>
              </div>
            )}
            {/* join existing ca-skillform system; field column mirrors Loomic template-dialog .fields/.field */}
            <div className="ca-skillform" data-testid="skill-run-form">
            {(skill.inputs ?? []).map((f) => {
              const id = `skill-run-${f.key}`
              const label = <label className="ca-skillform__label" htmlFor={id}>{loc(f.label)}{f.required && <span className="ca-skillrun__req" aria-hidden="true"> *</span>}</label>
              const ph = f.placeholder ? loc(f.placeholder) : ''
              const invalid = tried && missing.includes(f.key)
              const common = { id, 'data-testid': 'skill-run-field', 'data-key': f.key, 'data-type': f.type, required: f.required, 'aria-required': f.required || undefined, 'aria-invalid': invalid || undefined, ...(f.maxLength ? { 'data-maxlength': f.maxLength } : {}) }
              const max = f.maxLength ? { maxLength: f.maxLength } : {}
              const fieldError = invalid ? (
                <p className="ca-skillrun__fielderr" role="alert" data-testid="skill-run-field-error" data-key={f.key}>{t('skillRun.fieldRequired', loc(f.label))}</p>
              ) : uploadError === f.key ? (
                <p className="ca-skillrun__fielderr" role="alert" data-testid="skill-run-upload-error" data-key={f.key}>
                  {t('skillRun.uploadFailed')}{' '}
                  <button type="button" data-testid="skill-run-upload-retry" onClick={() => setUploadError(null)}>{t('skillRun.retry')}</button>
                </p>
              ) : null
              if (f.type === 'select') return (
                <div key={f.key} className="ca-skillrun__field">
                  {label}
                  <select {...common} className="ca-panel__input" value={values[f.key] ?? ''} onChange={(e) => set(f.key, e.target.value)} onKeyDown={stop}>
                    {f.options?.map((o) => <option key={o.value} value={o.value}>{loc(o.label)}</option>)}
                  </select>
                  {fieldError}
                </div>
              )
              if (f.type === 'textarea') return (
                <div key={f.key} className="ca-skillrun__field">
                  {label}
                  <textarea {...common} className="ca-panel__prompt ca-panel__prompt--boxed" rows={3} placeholder={ph} {...max} value={values[f.key] ?? ''} onChange={(e) => set(f.key, e.target.value)} onKeyDown={stop} />
                  {fieldError}
                </div>
              )
              if (f.type === 'image') return (
                <div key={f.key} className="ca-skillrun__field">
                  {label}
                  <div className="ca-gen__refs ca-skillrun__uploadwrap" {...common} data-accept={f.accept ?? 'image'}>
                    {values[f.key]
                      ? <span className="ca-gen__ref">{f.accept === 'video' ? <video src={values[f.key]} muted playsInline /> : <img src={values[f.key]} alt="" />}<button type="button" title={t('common.remove')} onClick={() => set(f.key, '')}>{Icons.close}</button></span>
                      : <label className="ca-skillrun__upload" data-testid="skill-run-upload"><span className="ca-icon">{Icons.uploadArrow}</span><span>{uploading === f.key ? t('skillRun.uploading') : t('skillRun.uploadHint')}</span>
                          <input id={id} type="file" accept={f.accept === 'video' ? 'video/*' : 'image/*'} hidden onChange={(e) => {
                            const file = e.target.files?.[0]; e.target.value = ''
                            if (!file) return
                            setUploading(f.key)
                            setUploadError(null)
                            void uploadSkillImage(file, skill.id).then((src) => set(f.key, src)).catch(() => setUploadError(f.key)).finally(() => setUploading(null))
                          }} /></label>}
                  </div>
                  {fieldError}
                </div>
              )
              return (
                <div key={f.key} className="ca-skillrun__field">
                  {label}
                  <input {...common} className="ca-panel__input" placeholder={ph} {...max} value={values[f.key] ?? ''} onChange={(e) => set(f.key, e.target.value)} onKeyDown={stop} />
                  {fieldError}
                </div>
              )
            })}
            </div>
          </div>
          <div className="ca-skillrun__foot">
            {runError && <p className="ca-skillrun__fielderr" role="alert" data-testid="skill-run-run-error">{t('skillRun.startFailed')}</p>}
            <button type="button" className="ca-panel__primary ca-skillrun__go" data-testid="skill-run-go" disabled={!!uploading} aria-disabled={missing.length > 0 || undefined} data-missing={missing.length || undefined}
              onClick={onStart}>{t('skillRun.start')}</button>
          </div>
        </div>
        {zoom && (
          <button type="button" className="ca-skillrun__zoomview" data-testid="skill-run-zoomview" title={t('common.close')} onClick={() => setZoom(null)}>
            {isSkillMediaVideo(zoom)
              ? <video src={zoom} muted loop playsInline autoPlay controls data-testid="skill-run-zoomview-video" />
              : <img src={zoom} alt="" />}
          </button>
        )}
      </div>
    </div>
  )
}
