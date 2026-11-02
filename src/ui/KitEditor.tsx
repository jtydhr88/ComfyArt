import { useEffect, useRef, useState, type ReactNode } from 'react'
import { atom, useValue } from 'tldraw'

import { uploadImage, viewUrl } from '../comfy'
import { t } from '../i18n'
import { errorText } from '../jobs'
import { COLOR_ROLES, KIND_LABELS, kitDisplayName, libraryAtom, saveLibrary, type FontFile, type LibraryItem } from '../library'
import { ask, parseJson } from '../llm'
import { isPdf, uploadPdf } from '../pdf'
import { newProject } from '../projects'
import { AssetGrid } from './AssetPicker'
import { ColorPicker } from './ColorPicker'
import { confirmAtom } from './Confirm'
import { FieldSelect } from './FieldSelect'
import { FontPicker } from './FontPicker'
import { Icons } from './icons'
import { isEnter } from './keys'
import { Popover } from './Popover'
import '../styles/kit.css'

export const kitEditAtom = atom<string | null>('kit edit', null)

const SAVE_DELAY = 400
/** #539 PR-C: Assets upload zone limit (copy says 最大 20MB / up to 20MB). */
export const MAX_UPLOAD = 20 * 1024 * 1024
/** #539 PR-C: URL import check, ported from the reference group upload flow — http/https only. */
/** #539 PR-C product ruling: Assets accepts PNG/JPG/PDF only (no webp/gif). */
const OK_EXT = /\.(png|jpe?g|pdf)$/i
const OK_TYPES = ['image/png', 'image/jpeg', 'application/pdf']
export const okUploadFile = (f: File) => OK_TYPES.includes(f.type) || OK_EXT.test(f.name)
/** URL passes if its extension OR its content-type confirms PNG/JPG/PDF; HEAD/CORS failure = unconfirmed. */
export async function confirmedImportUrl(raw: string) {
  if (OK_EXT.test(new URL(raw.trim()).pathname)) return true
  try {
    const r = await fetch(raw.trim(), { method: 'HEAD' })
    return OK_TYPES.includes((r.headers.get('content-type') ?? '').split(';')[0].trim().toLowerCase())
  } catch {
    return false
  }
}
export function validImportUrl(raw: string) {
  try {
    const parsed = new URL(raw.trim())
    return ['http:', 'https:'].includes(parsed.protocol)
  } catch {
    return false
  }
}
const GUIDE_PAGES = 6
const GUIDE_TEXT = 12000
const BRAND_SYSTEM = t('libraryPanel.youReadBrandGuidelinesReply')

async function extractBrand(srcs: string[], text: string): Promise<Partial<LibraryItem>> {
  const prompt = `Extract the brand identity from this brand guide (${srcs.length} page image(s) attached).${text.trim() ? `\n\nText of the guide:\n${text.slice(0, GUIDE_TEXT)}` : ''}`
  const json = parseJson(await ask(prompt, BRAND_SYSTEM, srcs))
  if (!json) throw new Error(t('libraryPanel.couldNotExtractBrandInfo'))
  const colors = ((json.colors as { hex?: string; role?: string }[] | undefined) ?? []).filter((c) => /^#[0-9a-f]{6}$/i.test(c.hex ?? ''))
  return {
    name: typeof json.name === 'string' ? json.name : undefined,
    colors: colors.map((c) => c.hex!.toUpperCase()),
    roles: colors.map((c) => (c.role && c.role in COLOR_ROLES ? c.role : '')),
    fonts: Array.isArray(json.fonts) ? json.fonts.map(String) : [],
    description: typeof json.guidelines === 'string' ? json.guidelines : '',
  }
}

const uploadAll = async (files: File[]) => Promise.all(files.map(async (f) => viewUrl(await uploadImage(f, f.name))))

async function filesToImages(files: File[]): Promise<string[]> {
  const out: string[] = []
  for (const f of files) {
    if (isPdf(f)) out.push(...(await uploadPdf(f)).map((p) => p.src))
    else if (f.type.startsWith('image/')) out.push(...(await uploadAll([f])))
  }
  return out
}

function textColor(hex: string) {
  const n = parseInt(hex.slice(1), 16)
  return ((n >> 16) * 299 + ((n >> 8) & 255) * 587 + (n & 255) * 114) / 1000 > 150 ? '#000' : '#fff'
}

function Section({ title, onAdd, add, children }: { title: string; onAdd?: () => void; add?: ReactNode; children: ReactNode }) {
  return (
    <section className="ca-kit__section">
      <div className="ca-kit__head">
        <h3>{title}</h3>
        {add ?? (onAdd && <button type="button" className="ca-kit__add" onClick={onAdd}><span className="ca-icon">{Icons.plus}</span>{t('common.add')}</button>)}
      </div>
      {children}
    </section>
  )
}

function Tile({ src, onRemove, badge }: { src: string; onRemove: () => void; badge?: ReactNode }) {
  return (
    <span className="ca-kit__tile">
      <img src={src} alt="" />
      <button type="button" className="ca-kit__remove" title={t('common.remove')} onClick={onRemove}>{Icons.close}</button>
      {badge}
    </span>
  )
}

/** #539 PR-B: `embedded` = home Assets detail pane (in-flow, title + 「…」 menu, bottom bar). Canvas overlay path unchanged. */
export function KitEditor({ onError, embedded }: { onError: (msg: string) => void; embedded?: boolean }) {
  const id = useValue(kitEditAtom)
  const stored = useValue('kit item', () => libraryAtom.get().find((x) => x.id === id) ?? null, [id])
  const timer = useRef(0)
  const pending = useRef<LibraryItem[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [drag, setDrag] = useState(false)
  const [pick, setPick] = useState(false)
  const [more, setMore] = useState(false)
  const [uploadErr, setUploadErr] = useState('')
  const [urlOpen, setUrlOpen] = useState(false)
  const [url, setUrl] = useState('')
  const [urlErr, setUrlErr] = useState('')
  const [checking, setChecking] = useState(false)
  const [fontMenu, setFontMenu] = useState<'menu' | 'library' | null>(null)
  const files = useRef<HTMLInputElement>(null)
  const logos = useRef<HTMLInputElement>(null)
  const refs = useRef<HTMLInputElement>(null)
  const guide = useRef<HTMLInputElement>(null)
  const fontFiles = useRef<HTMLInputElement>(null)

  const flush = () => {
    clearTimeout(timer.current)
    if (pending.current) void saveLibrary(pending.current).catch((e) => onError(errorText(e)))
    pending.current = null
  }
  useEffect(() => flush, [id])

  // #539 P1: title shows the card's display name; draft only while typing so clearing falls back to the default on blur
  const [titleDraft, setTitleDraft] = useState<string | null>(null)
  if (!id || !stored) return null
  const item = stored
  const brand = item.kind === 'brand'
  const update = (fn: (x: LibraryItem) => LibraryItem) => {
    const next = libraryAtom.get().map((x) => (x.id === item.id ? fn(x) : x))
    libraryAtom.set(next)
    pending.current = next
    clearTimeout(timer.current)
    timer.current = window.setTimeout(flush, SAVE_DELAY)
  }
  const set = (patch: Partial<LibraryItem>) => update((x) => ({ ...x, ...patch }))
  const fail = (e: unknown) => onError(errorText(e))
  const close = () => { flush(); kitEditAtom.set(null) }
  const roles = item.colors.map((_, i) => item.roles?.[i] ?? '')
  const addImages = (srcs: string[]) => update((x) => ({ ...x, images: [...x.images, ...srcs.filter((s) => !x.images.includes(s))] }))
  const dropFiles = (list: File[]) => {
    // #539 PR-C: embedded upload zone rejects files over 20MB before any upload
    const bad = embedded ? list.filter((f) => !okUploadFile(f)) : []
    const big = embedded ? list.filter((f) => okUploadFile(f) && f.size > MAX_UPLOAD) : []
    const msg = bad.length ? t('assets.badFormat', bad.map((f) => f.name).join(', ')) : big.length ? t('assets.tooLarge', big.map((f) => f.name).join(', ')) : ''
    // #539 P2: inline error only (no toast); a new upload/drop replaces any stale error
    setUploadErr(msg); setUrlErr('')
    const ok = list.filter((f) => !big.includes(f) && !bad.includes(f))
    if (ok.length) void filesToImages(ok).then(addImages).catch(fail)
  }
  const saveUrl = async () => {
    setUploadErr(''); setUrlErr('')
    if (!validImportUrl(url)) { setUrlErr(t('assets.urlInvalid')); return }
    setChecking(true)
    const ok = await confirmedImportUrl(url).finally(() => setChecking(false))
    if (!ok) { setUrlErr(t('assets.urlFormat')); return }
    addImages([url.trim()])
    setUrl(''); setUrlErr(''); setUploadErr(''); setUrlOpen(false)
  }
  const createProject = () => { flush(); newProject({ kit: item.id }) }
  const fromGuide = async (file: File) => {
    setBusy(true)
    try {
      const pages = isPdf(file) ? await uploadPdf(file, GUIDE_PAGES) : null
      const srcs = pages ? pages.map((p) => p.src) : await uploadAll([file])
      const found = await extractBrand(srcs, pages ? pages.map((p) => p.text).join('\n') : '')
      update((x) => ({
        ...x,
        name: x.name || found.name || '',
        colors: [...x.colors, ...(found.colors ?? [])],
        roles: [...x.colors.map((_, i) => x.roles?.[i] ?? ''), ...(found.roles ?? [])],
        fonts: [...new Set([...x.fonts, ...(found.fonts ?? [])])],
        description: x.description || found.description || '',
        images: [...x.images, srcs[0]],
      }))
    } finally {
      setBusy(false)
    }
  }
  const addFontFiles = async (list: File[]) => {
    const added: FontFile[] = await Promise.all(list.map(async (f) => ({ family: f.name.replace(/\.(ttf|otf|woff2?)$/i, ''), src: viewUrl(await uploadImage(f, f.name)) })))
    update((x) => ({ ...x, fontFiles: [...(x.fontFiles ?? []), ...added], fonts: [...new Set([...x.fonts, ...added.map((a) => a.family)])] }))
  }
  const removeFont = (family: string) => update((x) => ({ ...x, fonts: x.fonts.filter((f) => f !== family), fontFiles: (x.fontFiles ?? []).filter((f) => f.family !== family) }))
  const remove = () => confirmAtom.set({
    danger: true,
    title: t('libraryPanel.deleteItem', KIND_LABELS[item.kind]),
    desc: t('libraryPanel.itemWillBeRemoved', item.name || t('kitEditor.untitled', KIND_LABELS[item.kind])),
    ok: t('common.delete'),
    run: () => { clearTimeout(timer.current); pending.current = null; kitEditAtom.set(null); void saveLibrary(libraryAtom.get().filter((x) => x.id !== item.id)).catch(fail) },
  })
  const picked = (input: HTMLInputElement, use: (list: File[]) => void) => { use(Array.from(input.files ?? [])); input.value = '' }

  return (
    <div className="ca-kit" data-embedded={embedded || undefined} data-testid={embedded ? 'assets-detail' : undefined} onPointerDown={(e) => e.stopPropagation()} onKeyDown={(e) => { e.stopPropagation(); if (!embedded && e.key === 'Escape') close() }}>
      {!embedded && <div className="ca-kit__bar">
        <span className="ca-model__tag">{KIND_LABELS[item.kind]}</span>
        <div className="ca-kit__spacer" />
        <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('common.delete')} onClick={remove}><span className="ca-icon">{Icons.trash}</span></button>
        <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('common.close')} onClick={close}><span className="ca-icon">{Icons.close}</span></button>
      </div>}
      <div className="ca-kit__scroll">
        <div className="ca-kit__page">
          {embedded ? (
            <div className="ca-kit__titlerow">
              <input className="ca-kit__title" data-testid="assets-detail-name" value={titleDraft ?? kitDisplayName(item)} placeholder={kitDisplayName({ ...item, name: '' })} onChange={(e) => { setTitleDraft(e.target.value); set({ name: e.target.value }) }} onBlur={() => { setTitleDraft(null); flush() }} onKeyDown={(e) => { if (isEnter(e)) e.currentTarget.blur() }} />
              <Popover open={more} onOpenChange={setMore} align="end" trigger={({ open, toggle }) => <button type="button" className="ca-lib__more" data-open={open || undefined} data-testid="assets-detail-more" title={t('home.more')} aria-label={t('home.more')} onClick={toggle}><span className="ca-icon">{Icons.more}</span></button>}>
                <div className="ca-menu ca-lib__menu">
                  <button type="button" className="ca-menu__item ca-menu__item--danger" onClick={() => { setMore(false); remove() }}>{t('common.delete')}</button>
                </div>
              </Popover>
            </div>
          ) : <input className="ca-kit__title" value={item.name} placeholder={t('kitEditor.untitled', KIND_LABELS[item.kind])} onChange={(e) => set({ name: e.target.value })} onKeyDown={(e) => { if (isEnter(e)) e.currentTarget.blur() }} />}
          <div
            className="ca-kit__drop"
            data-on={drag || undefined}
            onClick={() => { setUploadErr(''); files.current?.click() }}
            onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); dropFiles(Array.from(e.dataTransfer.files)) }}
          >
            <span className="ca-icon">{embedded ? Icons.uploadArrow : Icons.upload}</span>
            {embedded ? (
              /* #539 PR-C: 20MB validation + 「导入 URL」 */
              <div><div>{t('assets.dropHint')}<button type="button" className="ca-kit__url" data-testid="assets-import-url" onClick={(e) => { e.stopPropagation(); setUrlOpen(true); setUploadErr(''); setUrlErr('') }}>{t('assets.importUrl')}</button></div><div className="ca-kit__muted">{t('assets.dropFormats')}</div>{uploadErr && <div className="ca-kit__err" role="alert" data-testid="assets-upload-error">{uploadErr}</div>}</div>
            ) : <div><div>{t('kitEditor.dropHint')}</div><div className="ca-kit__muted">{t('kitEditor.dropFormats')}</div></div>}
          </div>
          {embedded && urlOpen && (
            <div className="ca-kit__urlrow" data-testid="assets-url-row">
              <input className="ca-kit__urlinput" data-testid="assets-url-input" autoFocus value={url} placeholder="https://" onChange={(e) => { setUrl(e.target.value); setUrlErr(''); setUploadErr('') }} onKeyDown={(e) => { if (isEnter(e) && url.trim() && !checking) void saveUrl(); if (e.key === 'Escape') { setUrlOpen(false); setUrlErr(''); setUploadErr('') } }} />
              <button type="button" className="ca-kit__urlsave" data-testid="assets-url-save" disabled={!url.trim() || checking} onClick={() => void saveUrl()}>{t('common.add')}</button>
              <button type="button" className="ca-assets-page__new" data-testid="assets-url-cancel" onClick={() => { setUrlOpen(false); setUrlErr(''); setUploadErr('') }}>{t('common.cancel')}</button>
              {urlErr && <div className="ca-kit__err" role="alert" data-testid="assets-url-error">{urlErr}</div>}
            </div>
          )}
          <input ref={files} type="file" accept={embedded ? '.png,.jpg,.jpeg,.pdf' : 'image/*,.pdf'} multiple hidden onChange={(e) => picked(e.target, dropFiles)} />
          {brand && !embedded && (
            <button type="button" className="ca-kit__link" disabled={busy} onClick={() => guide.current?.click()}>
              <span className="ca-icon">{Icons.agent}</span>{busy ? t('libraryPanel.extracting') : t('libraryPanel.extractFromFileBrandGuide')}
            </button>
          )}
          <input ref={guide} type="file" accept="image/*,.pdf" hidden onChange={(e) => picked(e.target, (l) => l[0] && void fromGuide(l[0]).catch(fail))} />

          <Section title={brand ? t('libraryPanel.designGuidelines') : t('kitEditor.description')}>
            <textarea className="ca-kit__text" rows={embedded ? 1 : undefined} data-testid={embedded ? 'assets-guide' : undefined} value={item.description} placeholder={brand ? t('libraryPanel.describeTheBrandsPersonality') : t('libraryPanel.describeTheLookStyleUse')} onChange={(e) => set({ description: e.target.value })} />
          </Section>

          {brand && (
            <Section title="Logo" onAdd={() => logos.current?.click()}>
              <div className="ca-kit__tiles">{(item.logos ?? []).map((src) => <Tile key={src} src={src} onRemove={() => set({ logos: item.logos!.filter((x) => x !== src) })} />)}</div>
              <input ref={logos} type="file" accept="image/*" multiple hidden onChange={(e) => picked(e.target, (l) => void uploadAll(l).then((srcs) => update((x) => ({ ...x, logos: [...(x.logos ?? []), ...srcs] }))).catch(fail))} />
            </Section>
          )}

          {brand && (
            <Section title={t('common.color')} onAdd={() => set({ colors: [...item.colors, '#000000'], roles: [...roles, ''] })}>
              <div className="ca-kit__colors">
                {item.colors.map((c, i) => (
                  <div key={i} className="ca-kit__color">
                    <ColorPicker
                      value={c}
                      title={t('common.color')}
                      allowNone
                      onChange={(v) => set(v ? { colors: item.colors.map((x, j) => (j === i ? v : x)) } : { colors: item.colors.filter((_, j) => j !== i), roles: roles.filter((_, j) => j !== i) })}
                      trigger={({ toggle }) => <button type="button" className="ca-kit__swatch" style={{ background: c, color: textColor(c) }} onClick={toggle}>{c}</button>}
                    />
                    <FieldSelect
                      value={roles[i]}
                      options={[
                        { id: '', label: t('libraryPanel.uncategorized') },
                        ...Object.entries(COLOR_ROLES).map(([key, label]) => ({ id: key, label })),
                      ]}
                      onChange={(id) => set({ roles: roles.map((r, j) => (j === i ? id : r)) })}
                      triggerClassName="ca-kit__role"
                    />
                  </div>
                ))}
              </div>
            </Section>
          )}

          {brand && (
            <Section
              title={t('libraryPanel.fonts')}
              add={(
                <Popover open={!!fontMenu} onOpenChange={(o) => setFontMenu(o ? 'menu' : null)} align="end" contentKey={fontMenu ?? ''} trigger={({ toggle }) => <button type="button" className="ca-kit__add" onClick={toggle}><span className="ca-icon">{Icons.plus}</span>{t('common.add')}</button>}>
                  {fontMenu === 'library'
                    ? <FontPicker value={item.fonts} multiple onError={onError} onCancel={() => setFontMenu(null)} onPick={(list) => { setFontMenu(null); update((x) => ({ ...x, fonts: [...new Set([...x.fonts, ...list])] })) }} />
                    : (
                      <div className="ca-menu">
                        <button type="button" className="ca-menu__item" onClick={() => setFontMenu('library')}><span className="ca-icon">{Icons.textTool}</span><span className="ca-menu__grow">{t('kitEditor.fromFontLibrary')}</span></button>
                        <button type="button" className="ca-menu__item" onClick={() => { setFontMenu(null); fontFiles.current?.click() }}><span className="ca-icon">{Icons.upload}</span><span className="ca-menu__grow">{t('libraryPanel.uploadFontFile')}</span></button>
                      </div>
                    )}
                </Popover>
              )}
            >
              <div className="ca-kit__fonts">
                {item.fonts.map((f) => (
                  <div key={f} className="ca-kit__font">
                    <span className="ca-kit__sample" style={{ fontFamily: `"${f}"` }}>Aa</span>
                    <span className="ca-kit__fontname">{f}</span>
                    <button type="button" className="ca-history__del" title={t('common.remove')} onClick={() => removeFont(f)}>{Icons.trash}</button>
                  </div>
                ))}
              </div>
              <input ref={fontFiles} type="file" accept=".ttf,.otf,.woff,.woff2" multiple hidden onChange={(e) => picked(e.target, (l) => void addFontFiles(l).catch(fail))} />
            </Section>
          )}

          <Section
            title={t('kitEditor.reference')}
            add={(
              <Popover open={pick} onOpenChange={setPick} align="end" trigger={({ toggle }) => <button type="button" className="ca-kit__add" onClick={toggle}><span className="ca-icon">{Icons.plus}</span>{t('common.add')}</button>}>
                <div className="ca-menu ca-assets-pop">
                  <button type="button" className="ca-menu__item" onClick={() => { setPick(false); refs.current?.click() }}><span className="ca-icon">{Icons.upload}</span><span className="ca-menu__grow">{t('common.uploadFile')}</span></button>
                  <AssetGrid only="image" onPick={(a) => { setPick(false); addImages([a.src]) }} />
                </div>
              </Popover>
            )}
          >
            <div className="ca-kit__tiles">
              {item.images.map((src) => (
                <Tile key={src} src={src} onRemove={() => set({ images: item.images.filter((x) => x !== src), ...(item.cover === src ? { cover: undefined } : {}) })} badge={(
                  <button type="button" className="ca-kit__cover" data-on={item.cover === src || undefined} onClick={() => set({ cover: item.cover === src ? undefined : src })}>
                    {item.cover === src ? t('libraryPanel.cover') : t('libraryPanel.setAsCover')}
                  </button>
                )} />
              ))}
            </div>
            <input ref={refs} type="file" accept="image/*" multiple hidden onChange={(e) => picked(e.target, (l) => void uploadAll(l).then(addImages).catch(fail))} />
          </Section>
        </div>
      </div>
      {embedded ? (
        /* #539 PR-C: full-width bar, button at the right edge of an 800 centred container; reuses #555 newProject */
        <div className="ca-kit__foot" data-testid="assets-detail-foot">
          <div className="ca-kit__footin"><button type="button" className="ca-panel__primary ca-kit__cta" data-testid="assets-create-project" onClick={createProject}>{t('kitEditor.createProject')} →</button></div>
        </div>
      ) : brand && (
        <div className="ca-kit__foot">
          <button type="button" className="ca-panel__primary ca-kit__cta" onClick={() => { flush(); newProject({ kit: item.id }) }}>{t('kitEditor.createProject')} →</button>
        </div>
      )}
    </div>
  )
}
