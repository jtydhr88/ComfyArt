import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useValue, type Editor } from 'tldraw'

import { clearCache, unloadModels } from '../comfy'
import { DOCS_SITE } from '../docsConfig'
import { errorText } from '../jobs'
import { lang, setLang, t, type Lang } from '../i18n'
import { showMemoryToast } from '../memory'
import { pushEnabled, setPush } from '../notices'
import { saveTheme, setTheme, themeAtom, THEMES, type Theme } from '../theme'
import { loadCloudModels } from '../wavespeed'
import { dockAtom, setDock } from './chatDock'
import { reportError, reportSuccess } from './ErrorToasts'
import { Icons } from './icons'
import { Popover } from './Popover'
import { shortcutsAtom } from './Shortcuts'
import { keySettingsOpenAtom, keyStatusAtom, WAVESPEED_HISTORY_URL } from '../wavespeedKey'
import { usageOpenAtom } from './UsageDialog'

/** #35: the docs site (Mintlify, URL in docsConfig.ts); English at the root, Chinese under /zh. */
export function docsUrl(l: Lang = lang): string {
  return l === 'zh' ? `${DOCS_SITE}/zh` : DOCS_SITE
}

// #408: canvas -> tldraw success toast; home has no tldraw toast host, so use the existing home toast (ca-mem-toast).
const done = (text: string, onCanvas: boolean) => (onCanvas ? reportSuccess(text) : showMemoryToast(text))

const LANGS: [Lang, string][] = [['zh', t('settings.langZh')], ['en', t('settings.langEn')]]
const SIDES: ['left' | 'right', string][] = [['left', t('settings.chatLeft')], ['right', t('settings.chatRight')]]

const EDGE = 8

function Choice({ label, on, onPick, testId }: { label: string; on: boolean; onPick: () => void; testId?: string }) {
  return (
    <button type="button" className="ca-menu__item" data-testid={testId} onClick={onPick}>
      <span className="ca-menu__grow">{label}</span>{on && <span className="ca-icon">{Icons.check}</span>}
    </button>
  )
}

/** #498: › flyout submenu (language / theme). Opens beside the row; closes on leave. */
function FlySub({
  label, testId, children,
}: { label: string; testId: string; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [fly, setFly] = useState<{ left: number; top: number } | null>(null)
  const host = useRef<HTMLDivElement>(null)

  const place = () => {
    const r = host.current?.getBoundingClientRect()
    if (!r) return
    const w = 140
    const left = r.right + w > window.innerWidth - EDGE ? r.left - w : r.right
    setFly({ left, top: r.top - 4 })
    setOpen(true)
  }

  return (
    <div
      className="ca-menu__flyhost"
      ref={host}
      onMouseEnter={place}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        className="ca-menu__item ca-menu__sub"
        aria-expanded={open}
        data-open={open || undefined}
        data-testid={testId}
        onClick={() => (open ? setOpen(false) : place())}
      >
        <span className="ca-menu__grow">{label}</span>
        <span className="ca-icon ca-menu__chev-right">{Icons.next}</span>
      </button>
      {open && fly && (
        <div
          className="ca-menu ca-menu__nested ca-menu__flyout ca-settings__fly"
          style={fly}
          ref={(el) => {
            if (el && fly) el.style.top = `${Math.max(EDGE, Math.min(fly.top, window.innerHeight - el.offsetHeight - EDGE))}px`
          }}
          data-testid={`${testId}-fly`}
        >
          {children}
        </div>
      )}
    </div>
  )
}

export function SettingsMenu({ editor, trigger }: { editor?: Editor; trigger: (props: { open: boolean; toggle: () => void }) => ReactNode }) {
  const [open, setOpen] = useState(false)
  const [push, setPushOn] = useState(pushEnabled)
  const theme = useValue(themeAtom)
  const dock = useValue(dockAtom)
  const keyStatus = useValue(keyStatusAtom)
  const toggle = (next: boolean) => setOpen(next)

  // Refresh balance when the menu opens so `$x.xx ›` matches TopBar.
  useEffect(() => {
    if (open) void import('../wavespeedKey').then((m) => m.refreshKeyStatus())
  }, [open])

  const balanceText = keyStatus?.configured && keyStatus.balance !== null
    ? `$${keyStatus.balance.toFixed(2)}`
    : null

  const applyTheme = (value: Theme) => {
    if (editor) setTheme(editor, value)
    else saveTheme(value)
  }

  return (
    <Popover open={open} onOpenChange={toggle} side={editor ? 'bottom' : 'top'} align={editor ? 'end' : 'start'} trigger={trigger}>
      <div className="ca-menu ca-settings" data-testid="settings-menu">
        {/* #498 locked order: balance › → language › → theme › → key → unload → cache → history ↗ → (editor extras) → guide */}
        {balanceText && (
          <button
            type="button"
            className="ca-menu__item"
            data-testid="settings-usage"
            onClick={() => { setOpen(false); usageOpenAtom.set(true) }}
          >
            <span className="ca-menu__grow">{balanceText}</span>
            <span className="ca-icon ca-menu__chev-right">{Icons.next}</span>
          </button>
        )}
        <FlySub label={t('settings.language')} testId="settings-lang">
          {LANGS.map(([value, label]) => (
            <Choice key={value} label={label} on={lang === value} onPick={() => value !== lang && setLang(value)} testId={`settings-lang-${value}`} />
          ))}
        </FlySub>
        <FlySub label={t('projectHeader.theme')} testId="settings-theme">
          {THEMES.map(([value, label]) => (
            <Choice key={value} label={label} on={theme === value} onPick={() => applyTheme(value)} testId={`settings-theme-${value}`} />
          ))}
        </FlySub>
        <div className="ca-menu__sep" />
        <button type="button" className="ca-menu__item" data-testid="settings-ws-key" onClick={() => { setOpen(false); keySettingsOpenAtom.set(true) }}>
          <span className="ca-icon">{Icons.settings}</span><span className="ca-menu__grow">{t('wsKey.menu')}</span>
        </button>
        <button type="button" className="ca-menu__item" data-testid="settings-unload" onClick={() => { setOpen(false); void unloadModels().then((r) => { done(t('settings.unloadModelsDone', r.models, r.prices), !!editor); void loadCloudModels() }, (e) => reportError(errorText(e))) }}>
          <span className="ca-icon">{Icons.erase}</span><span className="ca-menu__grow">{t('settings.unloadModels')}</span>
        </button>
        <button type="button" className="ca-menu__item" data-testid="settings-clear-cache" onClick={() => { setOpen(false); void clearCache().then((r) => done(t('settings.clearCacheDone', r.entries, r.thumbs), !!editor), (e) => reportError(errorText(e))) }}>
          <span className="ca-icon">{Icons.trash}</span><span className="ca-menu__grow">{t('settings.clearCache')}</span>
        </button>
        <button
          type="button"
          className="ca-menu__item"
          data-testid="settings-ws-history"
          onClick={() => { setOpen(false); window.open(WAVESPEED_HISTORY_URL, '_blank', 'noopener,noreferrer') }}
        >
          <span className="ca-icon">{Icons.exit}</span>
          <span className="ca-menu__grow">{t('settings.waveSpeedTaskHistory')}</span>
        </button>
        {editor && (
          <>
            <div className="ca-menu__sep" />
            <div className="ca-gen__label">{t('settings.chatPosition')}</div>
            {SIDES.map(([value, label]) => <Choice key={value} label={label} on={dock === value} onPick={() => setDock(value)} />)}
            <div className="ca-menu__sep" />
            <button type="button" className="ca-menu__item" onClick={() => { setOpen(false); shortcutsAtom.set(true) }}>
              <span className="ca-icon">{Icons.keyboard}</span><span className="ca-menu__grow">{t('shortcuts.keyboardShortcuts')}</span><span className="ca-menu__key">?</span>
            </button>
            <label className="ca-menu__item">
              <span className="ca-icon">{Icons.bell}</span><span className="ca-menu__grow">{t('settings.systemNotifications')}</span>
              <input type="checkbox" checked={push} onChange={(e) => void setPush(e.target.checked).then(setPushOn)} />
            </label>
          </>
        )}
        <div className="ca-menu__sep" />
        <button type="button" className="ca-menu__item" data-testid="settings-guide" onClick={() => { setOpen(false); window.open(docsUrl(), '_blank', 'noopener,noreferrer') }}>
          <span className="ca-icon">{Icons.link}</span><span className="ca-menu__grow">{t('settings.userGuide')}</span>
        </button>
      </div>
    </Popover>
  )
}
