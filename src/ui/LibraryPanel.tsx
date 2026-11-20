import { useState } from 'react'
import { atom, useValue, type Editor } from 'tldraw'

import { kitsAtom } from '../agent'
import { placeAsset } from '../assets'
import { KIND_LABELS, libraryAtom, updateLibrary, type LibraryItem, type LibraryKind } from '../library'
import { newProject } from '../projects'
import { AssetGrid } from './AssetPicker'
import { confirmAtom } from './Confirm'
import { Icons } from './icons'
import { kitEditAtom } from './KitEditor'
import { Popover } from './Popover'
import { t } from '../i18n'
import { uuid } from '../id'

type Tab = 'files' | LibraryKind
export const libraryTabAtom = atom<Tab>('library tab', 'files')
const TABS: [Tab, string][] = [['files', t('libraryPanel.files')], ['brand', t('library.brandKit')], ['character', t('library.character')], ['product', t('library.product')], ['custom', t('common.custom')]]

function LibCard({ item, save }: { item: LibraryItem; save: (fn: (list: LibraryItem[]) => LibraryItem[]) => void }) {
  const [menu, setMenu] = useState(false)
  const kits = useValue(kitsAtom)
  const brand = item.kind === 'brand'
  const cover = item.cover ?? item.logos?.[0] ?? item.images[0]
  const name = item.name || t('kitEditor.untitled', KIND_LABELS[item.kind])
  const act = (fn: () => void) => () => { setMenu(false); fn() }
  return (
    <div className="ca-lib__card" onClick={() => kitEditAtom.set(item.id)}>
      <div className="ca-lib__row">
        <span className="ca-lib__name">{name}</span>
        {item.isDefault && <span className="ca-model__tag">{t('common.default')}</span>}
        <span onClick={(e) => e.stopPropagation()}>
          <Popover open={menu} onOpenChange={setMenu} align="end" trigger={({ open, toggle }) => <button type="button" className="ca-lib__more" data-open={open || undefined} title={t('home.more')} onClick={toggle}><span className="ca-icon">{Icons.more}</span></button>}>
            <div className="ca-menu ca-lib__menu">
              <button type="button" className="ca-menu__item" disabled={kits.some((k) => k.id === item.id)} onClick={act(() => kitsAtom.set([...kitsAtom.get(), item]))}>{t('libraryPanel.addToChat')}</button>
              {brand && <button type="button" className="ca-menu__item" onClick={act(() => newProject({ kit: item.id }))}>{t('libraryPanel.designWithThisKitNew')}</button>}
              {brand && (
                <button type="button" className="ca-menu__item" onClick={act(() => save((list) => list.map((x) => (x.kind === 'brand' ? { ...x, isDefault: x.id === item.id ? !item.isDefault : false } : x))))}>
                  <span className="ca-menu__grow">{t('libraryPanel.setAsDefaultForNew')}</span>{item.isDefault && <span className="ca-icon">{Icons.check}</span>}
                </button>
              )}
              <button type="button" className="ca-menu__item" onClick={act(() => save((list) => [...list, { ...item, id: uuid().slice(0, 8), name: t('libraryPanel.copy', name), isDefault: false }]))}>{t('common.duplicate')}</button>
              <button type="button" className="ca-menu__item ca-menu__item--danger" onClick={act(() => confirmAtom.set({ danger: true, title: t('libraryPanel.deleteItem', KIND_LABELS[item.kind]), desc: t('libraryPanel.itemWillBeRemoved', name), ok: t('common.delete'), run: () => save((list) => list.filter((x) => x.id !== item.id)) }))}>{t('common.delete')}</button>
            </div>
          </Popover>
        </span>
      </div>
      <div className="ca-lib__cover">{cover ? <img src={cover} alt="" /> : <span className="ca-icon">{Icons.assets}</span>}</div>
    </div>
  )
}

export function LibraryPanel({ editor, onError }: { editor: Editor; onError: (msg: string) => void }) {
  const tab = useValue(libraryTabAtom)
  const setTab = (t: Tab) => libraryTabAtom.set(t)
  const library = useValue(libraryAtom)
  const items = library.filter((i) => i.kind === tab)
  const save = (fn: (list: LibraryItem[]) => LibraryItem[]) => void updateLibrary(fn).catch((e) => onError(String(e)))
  const create = (kind: LibraryKind) => {
    const id = uuid().slice(0, 8)
    save((list) => [...list, { id, kind, name: '', description: '', images: [], colors: [], fonts: [] }])
    kitEditAtom.set(id)
  }

  return (
    <div className="ca-lib">
      <div className="ca-utabs" role="tablist">
        {TABS.map(([t, label]) => <button key={t} type="button" role="tab" aria-selected={tab === t} className="ca-utabs__tab" data-on={tab === t || undefined} onClick={() => setTab(t)}>{label}</button>)}
      </div>
      {tab === 'files' && <AssetGrid onPick={(item) => void placeAsset(editor, item)} />}
      {tab !== 'files' && (
        <>
          <button type="button" className="ca-lib__new" onClick={() => create(tab)}>
            <span className="ca-icon">{Icons.plus}</span>{t('libraryPanel.newItem', KIND_LABELS[tab])}
          </button>
          {items.length === 0 && <div className="ca-side__empty">{t('libraryPanel.emptyHint', KIND_LABELS[tab])}</div>}
          {items.map((item) => <LibCard key={item.id} item={item} save={save} />)}
        </>
      )}
    </div>
  )
}
