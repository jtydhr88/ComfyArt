import {
  AssetRecordType,
  DefaultContextMenu,
  TldrawUiMenuGroup,
  TldrawUiMenuItem,
  TldrawUiMenuSubmenu,
  useActions,
  useEditor,
  useValue,
  type Editor,
  type TLImageShape,
  type TLShapeId,
  type TLUiContextMenuProps,
} from 'tldraw'

import { extraRefsAtom } from '../agent'
import { uploadImage, viewUrl } from '../comfy'
import { createGenerator } from '../generate'
import { toMedia } from '../jobs'
import { KIND_LABELS, libraryAtom, updateLibrary, type LibraryKind } from '../library'
import type { GeneratorShape } from '../shapes/GeneratorShape'
import { chatViewAtom } from './AgentPanel'
import { renameAtom } from './BatchRename'
import { importFiles } from './DropHandlers'
import { exportAtom } from './ExportDialog'
import { libraryTabAtom } from './LibraryPanel'
import { framesOnPage } from './FrameToolbar'
import { lightboxAtom } from './Lightbox'
import { slideshowAtom } from './Slideshow'
import { sideAtom } from './SidePanel'
import { t } from '../i18n'
import { uuid } from '../id'

function replaceImage(editor: Editor, shape: TLImageShape) {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file) return
    const ref = await uploadImage(file, file.name)
    const m = await toMedia(ref, 'image')
    const assetId = AssetRecordType.createId()
    editor.createAssets([{ id: assetId, typeName: 'asset', type: 'image', props: { name: file.name, src: viewUrl(ref), w: m.w, h: m.h, mimeType: file.type || 'image/png', isAnimated: false }, meta: {} }])
    editor.updateShape<TLImageShape>({ id: shape.id, type: 'image', props: { assetId, h: shape.props.w * m.h / m.w, crop: null } })
  }
  input.click()
}

function sendToGenerator(editor: Editor, shape: TLImageShape) {
  const src = shape.props.assetId ? editor.getAsset(shape.props.assetId)?.props.src : null
  if (!src) return
  const id = createGenerator(editor)
  editor.updateShape<GeneratorShape>({ id, type: 'generator', meta: { refs: [src] } })
}

function sendToChat(ids: TLShapeId[]) {
  extraRefsAtom.set([...extraRefsAtom.get().filter((id) => !ids.includes(id)), ...ids])
  if (chatViewAtom.get() === 'closed') chatViewAtom.set('open')
}

function imageSrcs(editor: Editor): string[] {
  return editor.getSelectedShapes().flatMap((s) => {
    const asset = s.type === 'image' && (s as TLImageShape).props.assetId ? editor.getAsset((s as TLImageShape).props.assetId!) : null
    return asset?.props.src ? [asset.props.src] : []
  })
}

function addToLibrary(editor: Editor, kind: LibraryKind, target: string | null) {
  const srcs = imageSrcs(editor)
  void updateLibrary((list) => target
    ? list.map((x) => (x.id === target ? { ...x, images: [...x.images, ...srcs.filter((src) => !x.images.includes(src))] } : x))
    : [...list, { id: uuid().slice(0, 8), kind, name: t('canvasMenu.new', KIND_LABELS[kind]), description: '', images: srcs, colors: [], fonts: [] }])
  libraryTabAtom.set(kind)
  sideAtom.set('assets')
}

function LibraryMenu() {
  const editor = useEditor()
  const library = useValue(libraryAtom)
  return (
    <TldrawUiMenuSubmenu id="ca-library" label={t('canvasMenu.addToMyAssets')}>
      {(Object.keys(KIND_LABELS) as LibraryKind[]).map((kind) => (
        <TldrawUiMenuSubmenu key={kind} id={`ca-library-${kind}`} label={t('canvasMenu.addTo', KIND_LABELS[kind])}>
          <TldrawUiMenuGroup id={`ca-library-${kind}-new`}>
            <TldrawUiMenuItem id={`ca-library-${kind}-create`} label={t('canvasMenu.create', KIND_LABELS[kind])} onSelect={() => addToLibrary(editor, kind, null)} />
          </TldrawUiMenuGroup>
          <TldrawUiMenuGroup id={`ca-library-${kind}-items`}>
            {library.filter((x) => x.kind === kind).map((x) => (
              <TldrawUiMenuItem key={x.id} id={`ca-library-item-${x.id}`} label={x.name} onSelect={() => addToLibrary(editor, kind, x.id)} />
            ))}
          </TldrawUiMenuGroup>
        </TldrawUiMenuSubmenu>
      ))}
    </TldrawUiMenuSubmenu>
  )
}

function Item({ id, label }: { id: string; label: string }) {
  const action = useActions()[id]
  if (!action) return null
  return <TldrawUiMenuItem id={id} label={label} kbd={action.kbd} onSelect={action.onSelect} />
}

function Content() {
  const editor = useEditor()
  const s = useValue('canvas menu', () => {
    const shapes = editor.getSelectedShapes()
    return {
      count: shapes.length,
      group: shapes.some((x) => x.type === 'group'),
      frame: shapes.some((x) => x.type === 'frame'),
      media: shapes.some((x) => x.type === 'image' || x.type === 'video'),
      image: shapes.length === 1 && shapes[0].type === 'image' ? (shapes[0] as TLImageShape) : null,
      images: shapes.filter((x) => x.type === 'image').map((x) => x.id),
      ids: shapes.map((x) => x.id),
      locked: editor.getCurrentPageShapes().some((x) => x.isLocked),
      frames: framesOnPage(editor).length,
    }
  }, [editor])

  if (!s.count) {
    return (
      <>
        <TldrawUiMenuGroup id="ca-upload">
          <TldrawUiMenuItem id="ca-upload-image" label={t('canvasMenu.uploadImage')} onSelect={() => importFiles(editor, 'image/*')} />
          <TldrawUiMenuItem id="ca-upload-video" label={t('canvasMenu.uploadVideo')} onSelect={() => importFiles(editor, 'video/*')} />
        </TldrawUiMenuGroup>
        <TldrawUiMenuGroup id="ca-clipboard">
          <Item id="paste" label={t('canvasMenu.paste')} />
          <Item id="select-all" label={t('canvasMenu.selectAll')} />
        </TldrawUiMenuGroup>
        <TldrawUiMenuGroup id="ca-view">
          <Item id="zoom-in" label={t('common.zoomIn')} />
          <Item id="zoom-out" label={t('common.zoomOut')} />
          <Item id="zoom-to-fit" label={t('canvasMenu.zoomToFitAll')} />
          <Item id="zoom-to-100" label={t('shortcuts.zoomTo100')} />
          {s.frames > 0 && <TldrawUiMenuItem id="ca-slideshow" label={t('canvasMenu.playArtboardsFullscreen')} onSelect={() => { slideshowAtom.set({ ids: framesOnPage(editor), index: 0 }) }} />}
          {s.locked && <Item id="unlock-all" label={t('canvasMenu.unlockAll')} />}
        </TldrawUiMenuGroup>
      </>
    )
  }

  return (
    <>
      <TldrawUiMenuGroup id="ca-clipboard">
        <Item id="copy" label={t('common.copy')} />
        <Item id="cut" label={t('common.cut')} />
        <Item id="paste" label={t('canvasMenu.paste')} />
        <Item id="duplicate" label={t('common.duplicate')} />
      </TldrawUiMenuGroup>
      <TldrawUiMenuGroup id="ca-group">
        {s.count > 1 && <Item id="group" label={t('canvasMenu.group')} />}
        {s.group && <Item id="ungroup" label={t('canvasMenu.ungroup')} />}
        {s.frame && <Item id="remove-frame" label={t('canvasMenu.removeArtboard')} />}
        {s.count > 1 && <Item id="flatten-to-image" label={t('canvasMenu.mergeLayers')} />}
        {s.count > 1 && <Item id="ca-tidy" label={t('multiToolbar.tidyUp')} />}
      </TldrawUiMenuGroup>
      <TldrawUiMenuGroup id="ca-order">
        <Item id="bring-to-front" label={t('canvasMenu.bringToFront')} />
        <Item id="bring-forward" label={t('canvasMenu.bringForward')} />
        <Item id="send-backward" label={t('canvasMenu.sendBackward')} />
        <Item id="send-to-back" label={t('canvasMenu.sendToBack')} />
      </TldrawUiMenuGroup>
      <TldrawUiMenuGroup id="ca-transform">
        <Item id="flip-horizontal" label={t('common.flipHorizontal')} />
        <Item id="flip-vertical" label={t('common.flipVertical')} />
        <Item id="rotate-cw" label={t('canvasMenu.rotate90')} />
        <Item id="ca-hide" label={`${t('sidePanel.show')} / ${t('sidePanel.hide')}`} />
        <Item id="toggle-lock" label={t('canvasMenu.lockUnlock')} />
      </TldrawUiMenuGroup>
      {s.count === 1 && !s.media && <TldrawUiMenuGroup id="ca-raster"><Item id="flatten-to-image" label={t('canvasMenu.convertToImage')} /></TldrawUiMenuGroup>}
      <TldrawUiMenuGroup id="ca-assets">
        {s.images.length > 0 && <TldrawUiMenuItem id="ca-to-chat" label={t('canvasMenu.sendToChat')} onSelect={() => sendToChat(s.images)} />}
        {s.media && <LibraryMenu />}
      </TldrawUiMenuGroup>
      {(s.image || s.count > 1) && (
        <TldrawUiMenuGroup id="ca-extra">
          {s.image && <TldrawUiMenuItem id="ca-replace" label={t('canvasMenu.replace')} onSelect={() => replaceImage(editor, s.image!)} />}
          {s.image && <TldrawUiMenuItem id="ca-send" label={t('canvasMenu.useAsReference')} onSelect={() => sendToGenerator(editor, s.image!)} />}
          {s.count > 1 && <Item id="flatten-to-image" label={t('canvasMenu.flatten')} />}
          {s.count > 1 && <TldrawUiMenuItem id="ca-rename" label={t('batchRename.batchRename')} onSelect={() => { renameAtom.set(s.ids) }} />}
        </TldrawUiMenuGroup>
      )}
      <TldrawUiMenuGroup id="ca-export">
        {s.media && s.count === 1 && <TldrawUiMenuItem id="ca-preview" label={t('canvasMenu.viewLarger')} onSelect={() => { lightboxAtom.set(s.ids[0]) }} />}
        {s.media && <Item id="download-original" label={t('common.download')} />}
        <TldrawUiMenuItem id="ca-export" label={t('canvasMenu.export')} onSelect={() => { exportAtom.set(s.ids) }} />
        <Item id="export-as-png" label={t('canvasMenu.exportAsPng')} />
        <Item id="copy-as-png" label={t('canvasMenu.copyAsPng')} />
      </TldrawUiMenuGroup>
      <TldrawUiMenuGroup id="ca-delete">
        <Item id="delete" label={t('common.delete')} />
      </TldrawUiMenuGroup>
    </>
  )
}

export function CanvasMenu(props: TLUiContextMenuProps) {
  return (
    <DefaultContextMenu {...props}>
      <Content />
    </DefaultContextMenu>
  )
}
