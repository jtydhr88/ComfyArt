import { useRef, useState } from 'react'
import { createShapeId, useValue, type Editor, type TLImageShape } from 'tldraw'

import { draftAtom, extraRefsAtom, srcOf } from '../agent'
import { imageUrl, refFromUrl, uploadImage, viewUrl } from '../comfy'
import { createGenerator, generate } from '../generate'
import { type ErrorSink, errorText, placeMedia, toMedia } from '../jobs'
import { ask, stripThink } from '../llm'
import { downloadUrl } from '../psd'
import type { GeneratorShape } from '../shapes/GeneratorShape'
import { AssetGrid } from './AssetPicker'
import { Icons } from './icons'
import { Popover } from './Popover'
import { Chips } from './Chips'
import { t } from '../i18n'
import { uuid } from '../id'
import { isEnter } from './keys'

type Source = 'upload' | 'canvas' | 'assets'
interface Reference { src: string; notes?: string; name?: string; source?: Source; time?: number; key?: string }

const SOURCES: [Source | 'all', string][] = [['all', t('common.all')], ['upload', t('assetPicker.upload')], ['canvas', t('referencePanel.canvas')], ['assets', t('referencePanel.library')]]
const SORTS: [string, string][] = [['time', t('referencePanel.newest')], ['name', t('referencePanel.name')]]
const keyOf = (r: Reference) => r.key ?? r.src
const nameOf = (r: Reference) => r.name ?? decodeURIComponent(new URL(r.src, location.origin).searchParams.get('filename') ?? t('common.reference'))

async function copyImage(src: string) {
  if (!navigator.clipboard) throw new Error(t('referencePanel.copyNeedsSecureContext'))
  const blob = await (await fetch(src)).blob()
  const png = blob.type === 'image/png' ? blob : await new Promise<Blob>((resolve) => {
    const img = new Image()
    img.onload = () => {
      const c = document.createElement('canvas')
      c.width = img.naturalWidth
      c.height = img.naturalHeight
      c.getContext('2d')!.drawImage(img, 0, 0)
      c.toBlob((b) => resolve(b!), 'image/png')
    }
    img.src = URL.createObjectURL(blob)
  })
  await navigator.clipboard.write([new ClipboardItem({ 'image/png': png })])
}

const MOOD_GAP = 24
const MOOD_COLS = 3
const MOOD_W = 360
const ANALYSES: [string, string][] = [
  [t('referencePanel.styleAnalysis'), 'Analyze the visual style of this image for a designer: palette (with hex), lighting, texture, typography, mood and medium. Answer in concise Chinese bullet points.'],
  [t('referencePanel.compositionAnalysis'), 'Analyze the composition of this image for a designer: layout grid, focal point, balance, depth, negative space and camera angle. Answer in concise Chinese bullet points.'],
]

export function refsOf(editor: Editor): Reference[] {
  return (editor.getDocumentSettings().meta.references as Reference[] | undefined) ?? []
}

function setRefs(editor: Editor, refs: Reference[]) {
  const doc = editor.getDocumentSettings()
  editor.updateDocumentSettings({ meta: { ...doc.meta, references: refs as any } })
}

async function moodboard(editor: Editor, refs: Reference[]) {
  const media = await Promise.all(refs.map((r) => toMedia(refFromUrl(r.src), 'image')))
  const heights = media.map((m) => MOOD_W * m.h / m.w)
  const cols = Array.from({ length: Math.min(MOOD_COLS, media.length) }, () => MOOD_GAP)
  const spots = media.map((_, i) => {
    const c = cols.indexOf(Math.min(...cols))
    const spot = { x: MOOD_GAP + c * (MOOD_W + MOOD_GAP), y: cols[c] }
    cols[c] += heights[i] + MOOD_GAP
    return spot
  })
  const frameId = createShapeId()
  const center = editor.getViewportPageBounds().center
  const w = cols.length * (MOOD_W + MOOD_GAP) + MOOD_GAP
  const h = Math.max(...cols)
  editor.run(() => {
    editor.createShape({ id: frameId, type: 'frame', x: center.x - w / 2, y: center.y - h / 2, props: { w, h, name: t('referencePanel.moodBoard') } })
    media.forEach((m, i) => placeMedia(editor, m, t('common.reference'), spots[i].x, spots[i].y, MOOD_W, frameId))
  })
  editor.select(frameId)
  editor.zoomToSelection({ animation: { duration: 200 } })
}

export function ReferencePanel({ editor, onError }: { editor: Editor; onError: ErrorSink }) {
  const refs = useValue('references', () => refsOf(editor), [editor])
  const selected = useValue('selected for refs', () => editor.getSelectedShapes().filter((s): s is TLImageShape => s.type === 'image'), [editor])
  const [pick, setPick] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const file = useRef<HTMLInputElement>(null)
  const [source, setSource] = useState<Source | 'all'>('all')
  const [sort, setSort] = useState('time')
  const [menu, setMenu] = useState<string | null>(null)
  const [renaming, setRenaming] = useState<string | null>(null)
  const add = (srcs: string[], from: Source) => setRefs(editor, [...refs, ...srcs.filter((s) => !refs.some((r) => r.src === s)).map((src) => ({ src, source: from, time: Date.now() }))])
  const update = (key: string, patch: Partial<Reference>) => setRefs(editor, refsOf(editor).map((r) => (keyOf(r) === key ? { ...r, ...patch } : r)))
  const removeRef = (key: string) => setRefs(editor, refsOf(editor).filter((r) => keyOf(r) !== key))
  const shown = refs.filter((r) => source === 'all' || (r.source ?? 'upload') === source)
    .sort((a, b) => (sort === 'name' ? nameOf(a).localeCompare(nameOf(b)) : (b.time ?? 0) - (a.time ?? 0)))
  const act = (fn: () => unknown) => () => { setMenu(null); void Promise.resolve(fn()).catch((e) => onError(errorText(e))) }
  const upload = async (files: FileList | null) => {
    const srcs: string[] = []
    for (const f of Array.from(files ?? [])) srcs.push(viewUrl(await uploadImage(f, f.name)))
    add(srcs, 'upload')
  }
  const analyze = async (r: Reference, [label, prompt]: [string, string]) => {
    setBusy(`${r.src}${label}`)
    try {
      const text = await ask(prompt, 'You are a senior art director.', [r.src])
      update(keyOf(r), { notes: `${label}\n${stripThink(text)}` })
    } catch (e) {
      onError(errorText(e))
    } finally {
      setBusy(null)
    }
  }
  const variant = (r: Reference) => {
    const id = createGenerator(editor, false, { prompt: 'A fresh variation of the reference image: same style, palette and subject, new composition and details.', ratio: '1:1', count: 2 }, true)
    editor.updateShape<GeneratorShape>({ id, type: 'generator', meta: { refs: [r.src] } })
    void generate(editor, editor.getShape<GeneratorShape>(id)!, onError)
  }
  const toChat = async (r: Reference) => {
    const m = await toMedia(refFromUrl(r.src), 'image')
    const c = editor.getViewportPageBounds().center
    const id = placeMedia(editor, m, t('common.reference'), c.x - 200, c.y - 200 * m.h / m.w, 400)
    extraRefsAtom.set([...extraRefsAtom.get(), id])
    if (r.notes) draftAtom.set(t('referencePanel.referenceNotes', draftAtom.get(), draftAtom.get() ? '\n' : '', r.notes.split('\n').slice(1).join(' ')))
  }

  return (
    <div className="ca-lib">
      <div className="ca-style__row">
        <Popover
          open={pick}
          onOpenChange={setPick}
          trigger={({ toggle }) => <button type="button" className="ca-lib__new ca-ref__add" onClick={toggle}><span className="ca-icon">{Icons.plus}</span>{t('referencePanel.addReference')}</button>}
        >
          <div className="ca-menu ca-assets-pop">
            <button type="button" className="ca-menu__item" onClick={() => { setPick(false); file.current?.click() }}><span className="ca-icon">{Icons.upload}</span><span className="ca-menu__grow">{t('common.uploadFile')}</span></button>
            {selected.length > 0 && (
              <button type="button" className="ca-menu__item" onClick={() => { setPick(false); add(selected.map((s) => srcOf(editor, s)).filter((s): s is string => !!s), 'canvas') }}>
                <span className="ca-icon">{Icons.select}</span><span className="ca-menu__grow">{t('referencePanel.addSelected', selected.length)}</span>
              </button>
            )}
            <AssetGrid only="image" onPick={(i) => { setPick(false); add([i.src], 'assets') }} />
          </div>
        </Popover>
        <button type="button" className="ca-lib__new ca-ref__add" disabled={refs.length < 2} onClick={() => void moodboard(editor, refs).catch((e) => onError(String(e)))}>
          <span className="ca-icon">{Icons.grid}</span>{t('referencePanel.moodboard')}
        </button>
        <input ref={file} type="file" accept="image/*" multiple hidden onChange={(e) => { void upload(e.target.files).catch((err) => onError(String(err))); e.target.value = '' }} />
      </div>
      {refs.length > 0 && (
        <div className="ca-style__row">
          <Chips value={source} options={SOURCES} onPick={setSource} />
          <span className="ca-menu__grow" />
          <Chips value={sort} options={SORTS} onPick={setSort} />
        </div>
      )}
      {refs.length === 0 && <div className="ca-side__empty">{t('referencePanel.startFromReferencesUploadImages')}</div>}
      {shown.map((r) => (
        <div key={keyOf(r)} className="ca-ref">
          <div className="ca-ref__img">
            <img src={imageUrl(r.src)} alt="" />
            <Popover
              open={menu === keyOf(r)}
              onOpenChange={(o) => setMenu(o ? keyOf(r) : null)}
              align="end"
              trigger={({ toggle }) => <button type="button" className="ca-ref__remove" title={t('imageToolbar.more')} onClick={toggle}>{Icons.more}</button>}
            >
              <div className="ca-menu">
                <button type="button" className="ca-menu__item" onClick={act(() => window.open(r.src, '_blank'))}><span className="ca-menu__grow">{t('referencePanel.open')}</span></button>
                <button type="button" className="ca-menu__item" onClick={act(() => setRenaming(keyOf(r)))}><span className="ca-menu__grow">{t('batchRename.rename')}</span></button>
                <button type="button" className="ca-menu__item" onClick={act(() => copyImage(r.src))}><span className="ca-menu__grow">{t('common.copy')}</span></button>
                <button type="button" className="ca-menu__item" onClick={act(async () => { await copyImage(r.src); removeRef(keyOf(r)) })}><span className="ca-menu__grow">{t('common.cut')}</span></button>
                <button type="button" className="ca-menu__item" onClick={act(() => setRefs(editor, [...refsOf(editor), { ...r, key: uuid().slice(0, 8), name: t('referencePanel.copy', nameOf(r)), time: Date.now() }]))}><span className="ca-menu__grow">{t('common.duplicate')}</span></button>
                <button type="button" className="ca-menu__item" onClick={act(() => downloadUrl(r.src, nameOf(r)))}><span className="ca-menu__grow">{t('common.export')}</span></button>
                <div className="ca-menu__sep" />
                <button type="button" className="ca-menu__item" onClick={act(() => removeRef(keyOf(r)))}><span className="ca-menu__grow">{t('common.delete')}</span></button>
              </div>
            </Popover>
          </div>
          {renaming === keyOf(r)
            ? <input autoFocus className="ca-panel__input" defaultValue={nameOf(r)} onBlur={(e) => { setRenaming(null); if (e.target.value.trim()) update(keyOf(r), { name: e.target.value.trim() }) }} onKeyDown={(e) => { e.stopPropagation(); if (isEnter(e)) e.currentTarget.blur() }} />
            : <div className="ca-ref__name" onDoubleClick={() => setRenaming(keyOf(r))}>{nameOf(r)}<span className="ca-model__tag">{SOURCES.find(([k]) => k === (r.source ?? 'upload'))![1]}</span></div>}
          <div className="ca-panel__chips">
            {ANALYSES.map((a) => (
              <button key={a[0]} type="button" className="ca-panel__chip" disabled={!!busy} onClick={() => void analyze(r, a)}>{busy === `${r.src}${a[0]}` ? t('referencePanel.analyzing') : a[0]}</button>
            ))}
            <button type="button" className="ca-panel__chip" onClick={() => variant(r)}>{t('referencePanel.generateVariations')}</button>
            <button type="button" className="ca-panel__chip" onClick={() => void toChat(r).catch((e) => onError(String(e)))}>{t('libraryPanel.addToChat')}</button>
          </div>
          {r.notes && <div className="ca-ref__notes">{r.notes}</div>}
        </div>
      ))}
    </div>
  )
}
