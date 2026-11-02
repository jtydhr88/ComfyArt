import { ToolbarTips } from './ui/Tip'
import { getAssetUrlsByImport } from '@tldraw/assets/imports.vite'
import { useCallback, useEffect, useRef, useState } from 'react'
import { loadSnapshot, Tldraw, useValue, type Editor, type TLAssetStore, type TLComponents, type TLShape } from 'tldraw'
import 'tldraw/tldraw.css'

import { isViewUrl, thumbSize, thumbUrl, uploadImage, viewUrl } from './comfy'
import { svgRaster } from './vectorize'
import { errorText, resumeJobs } from './jobs'
import { loadWorkflowConfig } from './customWorkflows'
import './layers'
import { kitsAtom } from './agent'
import { defaultKitId, libraryAtom, loadLibrary } from './library'
import { loadMemory } from './memory'
import { loadModels } from './models'
import { loadProject, NEW_PARAM } from './projects'
import { saveStateAtom, startAutosave } from './autosave'
import { restoreHandoff, takeHandoff } from './home/handoff'
import { markDark, themeAtom } from './theme'
import { overrides } from './overrides'
import { CommentShapeUtil, CommentTool } from './shapes/CommentShape'
import { AudioShapeUtil, HtmlShapeUtil, LottieShapeUtil, ModelShapeUtil } from './shapes/EmbedShapes'
import { DoodleShapeUtil, DoodleTool } from './shapes/DoodleShape'
import { GenBlockShapeUtil, QrShapeUtil } from './shapes/ComposeShapes'
import { TextShapeUtil, TextTool } from './shapes/TextShape'
import { PenTool } from './shapes/PenTool'
import { VectorShapeUtil, VectorTool } from './shapes/VectorShape'
import { ArtboardShapeUtil } from './shapes/ArtboardShape'
import { GeneratorShapeUtil } from './shapes/GeneratorShape'
import { MockupShapeUtil } from './shapes/MockupShape'
import { HoverVideoShapeUtil } from './shapes/VideoShape'
import { AdjustPanel } from './ui/AdjustPanel'
import { AgentPanel, chatViewAtom, type ChatView } from './ui/AgentPanel'
import { dockAtom } from './ui/chatDock'
import { BatchRename } from './ui/BatchRename'
import { CanvasMenu } from './ui/CanvasMenu'
import { CanvasTools } from './ui/CanvasTools'
import { CommentPanel } from './ui/CommentPanel'
import { MemoryChooser, MemoryToast } from './ui/MemoryChooser'
import { Confirm } from './ui/Confirm'
import { Dock } from './ui/Dock'
import { DropHandlers } from './ui/DropHandlers'
import { ErrorToasts, reportError } from './ui/ErrorToasts'
import { EmbedToolbar, HtmlPreview } from './ui/EmbedToolbar'
import { Effects } from './ui/Effects'
import { HistoryDialog } from './ui/HistoryDialog'
import { AudioDialog } from './ui/AudioDialog'
import { ExportDialog } from './ui/ExportDialog'
import { MockupPanel } from './ui/MockupPanel'
import { PathEditor } from './ui/PathEditor'
import { FrameToolbar, registerFrameRules } from './ui/FrameToolbar'
import { EditLayers } from './ui/EditLayers'
import { GenPanel } from './ui/GenPanel'
import { CanvasPick } from './ui/CanvasPick'
import { CanvasChat } from './ui/CanvasChat'
import { CropBar } from './ui/CropBar'
import { ImageToolbar, registerCropRule } from './ui/ImageToolbar'
import { InfoDialog } from './ui/InfoDialog'
import { KitEditor } from './ui/KitEditor'
import { NoticeCenter } from './ui/NoticeCenter'
import { loadNotices } from './notices'
import { startScheduler } from './schedules'
import { startProactive } from './proactive'
import { startChatFrames } from './chatFrame'
import { ScheduleDialog } from './ui/ScheduleDialog'
import { startBot } from './bot'
import { registerCommandBus } from './botCommands'
import { BotSettings } from './ui/BotSettings'
import { KeySettings } from './ui/KeySettings'
import { UsageDialog } from './ui/UsageDialog'
import { keySettingsOpenAtom, refreshKeyStatus } from './wavespeedKey'
import { TaskDetails } from './ui/TaskDetails'
import { InpaintPanel } from './ui/InpaintPanel'
import { SkillsDialog } from './ui/SkillsDialog'
import { Slideshow } from './ui/Slideshow'
import { SmudgePanel } from './ui/SmudgePanel'
import { Lightbox } from './ui/Lightbox'
import { Icons } from './ui/icons'
import { MemoryDialog } from './ui/MemoryDialog'
import { WorkflowsDialog } from './ui/WorkflowsDialog'
import { ModePanel } from './ui/ModePanel'
import { MultiToolbar } from './ui/MultiToolbar'
import { ProjectHeader } from './ui/ProjectHeader'
import { SelectionLabel } from './ui/SelectionLabel'
import { Shortcuts } from './ui/Shortcuts'
import { StylePanel } from './ui/StylePanel'
import { SidePanel } from './ui/SidePanel'
import { ShapeToolbar, TextToolbar } from './ui/StyleToolbars'
import { TopBar } from './ui/TopBar'
import { VideoEditor } from './ui/VideoEditor'
import { VideoToolbar } from './ui/VideoToolbar'
import { Zoom } from './ui/Zoom'
import { lang, t } from './i18n'
import { uuid } from './id'

const CHANNEL = 'comfyart-projects'
const TAB = uuid()
const assetUrls = getAssetUrlsByImport()
const shapeUtils = [ArtboardShapeUtil, GeneratorShapeUtil, CommentShapeUtil, DoodleShapeUtil, TextShapeUtil, VectorShapeUtil, LottieShapeUtil, ModelShapeUtil, HtmlShapeUtil, AudioShapeUtil, MockupShapeUtil, GenBlockShapeUtil, QrShapeUtil, HoverVideoShapeUtil]
const tools = [CommentTool, DoodleTool, TextTool, VectorTool, PenTool]
const getShapeVisibility = (shape: TLShape) => (shape.meta.hidden ? 'hidden' as const : 'inherit' as const)

const components: TLComponents = {
  ContextMenu: CanvasMenu,
  Toolbar: null,
  StylePanel: null,
  MainMenu: null,
  PageMenu: null,
  NavigationPanel: null,
  HelpMenu: null,
  ActionsMenu: null,
  QuickActions: null,
  ImageToolbar: null,
  VideoToolbar: null,
  MenuPanel: null,
  TopPanel: null,
  SharePanel: null,
  HelperButtons: null,
  DebugPanel: null,
  DebugMenu: null,
  Minimap: null,
}

const assets: TLAssetStore = {
  async upload(_asset, file) {
    const ref = await uploadImage(file, file.name || 'image.png')
    return { src: viewUrl(ref) }
  },
  resolve(asset, ctx) {
    const src = asset.props.src
    if (!src || ctx.shouldResolveToOriginal || asset.type !== 'image') return src
    if (asset.props.mimeType === 'image/svg+xml') return svgRaster(src, asset.props.w, asset.props.h, ctx.steppedScreenScale * ctx.dpr)
    const size = thumbSize(Math.max(asset.props.w, asset.props.h) * ctx.steppedScreenScale * ctx.dpr)
    return size && isViewUrl(src) && !asset.props.isAnimated ? thumbUrl(src, size) : src
  },
}

export function App({ id, onCanvasReady }: { id: string; onCanvasReady?: () => void }) {
  const [editor, setEditor] = useState<Editor | null>(null)
  const setError = reportError
  const chat = useValue(chatViewAtom)
  const setChat = (view: ChatView) => chatViewAtom.set(view)
  const [stale, setStale] = useState(false)
  const staleRef = useRef(false)
  const dock = useValue(dockAtom)
  const dark = useValue('dark mode', () => editor?.user.getIsDarkMode() ?? false, [editor])

  useEffect(() => {
    // first run without a key: open the key guide once
    void refreshKeyStatus().then((s) => { if (s && !s.configured) keySettingsOpenAtom.set(true) })
  }, [])

  useEffect(() => {
    if (editor) markDark(dark)
  }, [editor, dark])

  useEffect(() => {
    void Promise.all([loadMemory(), loadWorkflowConfig(), loadModels(), loadNotices()]).catch((e) => setError(String(e)))
  }, [])

  const onMount = useCallback((ed: Editor) => {
    ed.user.updateUserPreferences({ colorScheme: themeAtom.get(), locale: lang === 'zh' ? 'zh-cn' : 'en' })
    setEditor(ed)
    ;(window as unknown as { __caEditor?: Editor }).__caEditor = ed // #282: e2e tests drive the canvas
    const stopFrames = registerFrameRules(ed)
    const stopCrop = registerCropRule(ed)
    return () => { stopFrames(); stopCrop() }
  }, [])

  useEffect(() => {
    if (!editor) return
    let alive = true
    let stopJobs = () => { }
    let stopScheduler = () => { }
    let stopProactive = () => { }
    let stopChatFrames = () => { }
    let stopCommands = () => { }
    let stopAutosave = () => { }
    const stopBot = startBot(id, () => staleRef.current)
    Promise.all([loadProject(id), loadLibrary()])
      .then(([snap]) => {
        if (!alive) return
        if (snap) {
          loadSnapshot(editor.store, snap)
          saveStateAtom.set({ state: 'saved', time: Date.now() })  // #305: loaded from disk = real persist
        }
        const doc = editor.getDocumentSettings()
        const kit = new URL(location.href).searchParams.get('kit')
        // #539 PR-C: a character/product/custom kit rides `?kit=` too and is attached like LibraryPanel 「添加到对话」; brand kits unchanged
        const other = libraryAtom.get().find((x) => x.id === kit && x.kind !== 'brand')
        if (!snap && !('brandKit' in doc.meta)) editor.updateDocumentSettings({ meta: { ...doc.meta, brandKit: (other ? null : kit) ?? defaultKitId() } })
        if (other && !kitsAtom.get().some((k) => k.id === other.id)) kitsAtom.set([...kitsAtom.get(), other])
        if (kit) {
          const url = new URL(location.href)
          url.searchParams.delete('kit')
          history.replaceState(null, '', url)
        }
        for (const page of editor.getPages()) {
          if (/^Page \d+$/.test(page.name)) editor.renamePage(page.id, page.name.replace('Page', t('app.page')))
        }
        const content = editor.getCurrentPageBounds()
        if (content) editor.zoomToBounds(content, { targetZoom: 1 })
        editor.clearHistory()
        onCanvasReady?.()
        stopJobs = resumeJobs(editor, setError)
        stopScheduler = startScheduler(editor, setError)
        stopProactive = startProactive(editor, setError)
        stopChatFrames = startChatFrames(editor)
        stopCommands = registerCommandBus(editor, id, () => staleRef.current, setError)
        const autosave = startAutosave(editor, id, () => !staleRef.current, () => channel.postMessage({ project: id, tab: TAB }))
        stopAutosave = autosave.stop
        const url = new URL(location.href)
        const created = url.searchParams.has(NEW_PARAM) ? autosave.save().then(() => saveStateAtom.get()) : Promise.resolve(null)
        if (url.searchParams.has(NEW_PARAM)) {
          url.searchParams.delete(NEW_PARAM)
          history.replaceState(null, '', url)
        }
        // #286: creating the project is the first save; if it fails, give the prompt back instead of sending it
        void created.then((s) => {
          if (!alive) return
          if (s?.state === 'error') restoreHandoff(setError, [t('app.createFailed'), s.error].filter(Boolean).join(' '))
          else takeHandoff(editor, setError).catch((e) => setError(errorText(e)))
        })
      })
      .catch((e) => {
        if (!alive) return
        onCanvasReady?.()
        if (new URL(location.href).searchParams.has('ask')) restoreHandoff(setError, [t('app.createFailed'), String(e)].join(' '))
        else setError(String(e))
      })
    const channel = new BroadcastChannel(CHANNEL)
    channel.onmessage = (e: MessageEvent<{ project: string; tab: string }>) => {
      if (e.data.project !== id || e.data.tab === TAB) return
      staleRef.current = true
      setStale(true)
    }
    return () => {
      alive = false
      stopJobs()
      stopScheduler()
      stopProactive()
      stopChatFrames()
      stopCommands()
      stopBot()
      channel.close()
      stopAutosave()
    }
  }, [editor, id, onCanvasReady])

  return (
    <div className="ca-root" data-chat={chat} data-dock={dock}>
      {editor && chat !== 'closed' && (
        <AgentPanel
          editor={editor}
          projectId={id}
          max={chat === 'max'}
          onMax={() => setChat(chat === 'max' ? 'open' : 'max')}
          onCollapse={() => setChat('closed')}
          onError={setError}
        />
      )}
      <div className="ca-main">
        {editor && (
          <TopBar
            editor={editor}
            left={chat === 'closed' && (
              <ProjectHeader editor={editor} projectId={id}>
                <NoticeCenter editor={editor} />
                <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('app.expandChat')} onClick={() => setChat('open')}>
                  <span className="ca-icon">{dock === 'left' ? Icons.panel : Icons.panelRight}</span>
                </button>
              </ProjectHeader>
            )}
          />
        )}
        <div className="ca-body">
          {editor && <SidePanel editor={editor} left onError={setError} />}
          <div className="ca-canvas">
            <Tldraw
              assets={assets}
              assetUrls={assetUrls}
              shapeUtils={shapeUtils}
              tools={tools}
              components={components}
              overrides={overrides}
              getShapeVisibility={getShapeVisibility}
              onMount={onMount}
            >
              <ErrorToasts />
              <DropHandlers onError={setError} />
              <SelectionLabel />
              <EditLayers />
              <ImageToolbar onError={setError} />
              <CropBar />
              <MockupPanel onError={setError} />
              <PathEditor />
              <ModePanel onError={setError} />
              <AdjustPanel onError={setError} />
              <InpaintPanel onError={setError} />
              <SmudgePanel onError={setError} />
              <StylePanel onError={setError} />
              <Effects />
              <VideoToolbar onError={setError} />
              <GenPanel onError={setError} />
              <CanvasPick onError={setError} />
              <CanvasChat onError={setError} />
              <CommentPanel onError={setError} />
              <MultiToolbar onError={setError} />
              <TextToolbar onError={setError} />
              <ShapeToolbar />
              <ToolbarTips />
              <FrameToolbar onError={setError} />
              <EmbedToolbar onError={setError} />
              <Dock onError={setError} />
              <CanvasTools zoom={<Zoom />} />
            </Tldraw>
          </div>
          {editor && <SidePanel editor={editor} onError={setError} />}
        </div>
      </div>
      <Shortcuts />
      <KitEditor onError={setError} />
      <Confirm />
      <MemoryChooser />
      <MemoryToast />
      {editor && <BatchRename editor={editor} />}
      {editor && <Lightbox editor={editor} />}
      {editor && <Slideshow editor={editor} />}
      <HtmlPreview />
      {editor && <InfoDialog editor={editor} onError={setError} />}
      {editor && <TaskDetails editor={editor} />}
      {editor && <ScheduleDialog editor={editor} onError={setError} />}
      <BotSettings onError={setError} />
      <KeySettings />
      <UsageDialog />
      {editor && <VideoEditor editor={editor} onError={setError} />}
      <MemoryDialog onError={setError} />
      <WorkflowsDialog onError={setError} />
      <SkillsDialog onError={setError} />
      {editor && <HistoryDialog editor={editor} projectId={id} onError={setError} />}
      {editor && <ExportDialog editor={editor} onError={setError} />}
      {editor && <AudioDialog editor={editor} onError={setError} />}
      {stale && (
        <div className="ca-stale">
          <span>{t('app.yourFileVersionIsOut')}</span>
          <button type="button" className="ca-panel__primary" onClick={() => location.reload()}>{t('app.refresh')}</button>
        </div>
      )}
    </div>
  )
}
