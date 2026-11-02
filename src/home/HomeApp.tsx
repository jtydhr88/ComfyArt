import { useEffect, useState, type ReactNode } from 'react'
import { useValue } from 'tldraw'

import { t } from '../i18n'
import { readLocal, writeLocal } from '../localPrefs'
import {
  duplicateProject,
  listProjects,
  newProject,
  openProject,
  openView,
  renameProject,
  setPinned,
  UNTITLED,
  type HomeView,
  type ProjectEntry,
} from '../projects'
import { MemoryChooser, MemoryToast } from '../ui/MemoryChooser'
import { MemoryDialog } from '../ui/MemoryDialog'
import { SkillsDialog } from '../ui/SkillsDialog'
import { showMemoryToast } from '../memory'
import { Confirm } from '../ui/Confirm'
import { BrandMark } from '../ui/BrandMark'
import { Icons } from '../ui/icons'
import { isEnter } from '../ui/keys'
import { KeySettings } from '../ui/KeySettings'
import { Popover } from '../ui/Popover'
import { SettingsMenu } from '../ui/SettingsMenu'
import { UsageDialog } from '../ui/UsageDialog'
import { keyStatusAtom } from '../wavespeedKey'
import '../styles/home.css'
import { Arti } from './Arti'
import { Assets } from './Assets'
import { confirmDelete } from './confirmDelete'
import { Home } from './Home'
import { NotFound } from './NotFound'
import { Projects } from './Projects'
import { Schedules } from './Schedules'
import { Skills } from './Skills'

type View = HomeView | { missing: string }

/** #495 — persist expand/collapse across refresh. */
export const RAIL_COLLAPSE_KEY = 'comfyart.rail.collapsed'
const RECENT_LIMIT = 8
/** #539 PR-A: Assets page shell is on main → rail entry shown. */
const SHOW_ASSETS = true

function RailBtn({
  icon, label, on, onClick, testId, badge, expanded,
}: {
  icon: ReactNode
  label: string
  on?: boolean
  onClick: () => void
  testId?: string
  badge?: string
  expanded?: boolean
}) {
  return (
    <button
      type="button"
      className="ca-rail__btn"
      title={label}
      aria-label={label}
      data-on={on || undefined}
      data-testid={testId}
      onClick={onClick}
    >
      <span className="ca-icon">{icon}</span>
      {expanded ? <span className="ca-rail__label">{label}</span> : null}
      {badge ? <span className="ca-rail__badge" data-testid="rail-arti-beta">{badge}</span> : null}
    </button>
  )
}

/** #498: left-bottom personal entry — icon (+ label when expanded) + real balance when key/balance OK. */
function SettingsRailBtn({ open, toggle, expanded }: { open: boolean; toggle: () => void; expanded: boolean }) {
  const keyStatus = useValue(keyStatusAtom)
  const balance = keyStatus?.configured && keyStatus.balance !== null
    ? `$${keyStatus.balance.toFixed(2)}`
    : null
  return (
    <button
      type="button"
      className="ca-rail__btn"
      title={t('settings.settings')}
      aria-label={t('settings.settings')}
      data-on={open || undefined}
      data-testid="rail-settings"
      onClick={toggle}
    >
      <span className="ca-icon">{Icons.settings}</span>
      {expanded ? <span className="ca-rail__label">{t('settings.settings')}</span> : null}
      {expanded && balance ? <span className="ca-rail__balance" data-testid="rail-settings-balance">{balance}</span> : null}
    </button>
  )
}


function RecentRow({ entry, onChanged }: { entry: ProjectEntry; onChanged: () => void }) {
  const [menu, setMenu] = useState(false)
  const [renaming, setRenaming] = useState(false)
  const name = entry.name || UNTITLED
  const commit = (next: string) => {
    setRenaming(false)
    if (next.trim() && next.trim() !== entry.name) void renameProject(entry.id, next.trim()).then(onChanged)
  }
  return (
    <div className="ca-rail__recent-row" data-testid="rail-recent-row">
      {renaming ? (
        <input
          autoFocus
          className="ca-rail__recent-input"
          defaultValue={entry.name}
          aria-label={t('home.rename')}
          onBlur={(e) => commit(e.target.value)}
          onKeyDown={(e) => {
            if (isEnter(e)) e.currentTarget.blur()
            if (e.key === 'Escape') setRenaming(false)
          }}
        />
      ) : (
        <button
          type="button"
          className="ca-rail__recent-name"
          title={name}
          onClick={() => openProject(entry.id)}
        >
          {name}
        </button>
      )}
      {!renaming && (
        <Popover
          open={menu}
          onOpenChange={setMenu}
          align="end"
          trigger={({ open, toggle }) => (
            <button
              type="button"
              className="ca-rail__recent-more"
              data-open={open || undefined}
              data-testid="rail-recent-more"
              title={t('home.more')}
              aria-label={t('home.more')}
              onClick={toggle}
            >
              <span className="ca-icon">{Icons.more}</span>
            </button>
          )}
        >
          <div className="ca-menu ca-rail__recent-menu" data-testid="rail-recent-menu">
            <button type="button" className="ca-menu__item" data-testid="rail-recent-pin" onClick={() => { setMenu(false); void setPinned(entry.id, !entry.pinned).then(onChanged) }}>{entry.pinned ? t('home.unpin') : t('home.pin')}</button>
            <button type="button" className="ca-menu__item" data-testid="rail-recent-rename" onClick={() => { setMenu(false); setRenaming(true) }}>{t('home.rename')}</button>
            <button type="button" className="ca-menu__item" data-testid="rail-recent-duplicate" onClick={() => { setMenu(false); void duplicateProject(entry.id).then(onChanged) }}>{t('common.duplicate')}</button>
            <button type="button" className="ca-menu__item ca-menu__item--danger" data-testid="rail-recent-delete" onClick={() => { setMenu(false); confirmDelete([entry.id], onChanged) }}>{t('common.delete')}</button>
          </div>
        </Popover>
      )}
    </div>
  )
}

function main(view: View) {
  if (view === 'home') return <Home />
  if (view === 'projects') return <Projects />
  if (view === 'skills') return <Skills />
  if (view === 'assets') return <Assets />
  if (view === 'schedules') return <Schedules />
  if (view === 'arti') return <Arti />
  return <NotFound id={view.missing} />
}

export function HomeApp({ view }: { view: View }) {
  const [collapsed, setCollapsed] = useState(() => readLocal(RAIL_COLLAPSE_KEY) === '1') // #607: desktop default expanded; only '1' persists collapsed (clears #546 default-collapsed)
  const expanded = !collapsed
  const [recent, setRecent] = useState<ProjectEntry[] | null>(null)

  const reloadRecent = () => {
    void listProjects().then((list) => {
      const sorted = [...list].sort((a, b) => Number(!!b.pinned) - Number(!!a.pinned) || b.updated - a.updated)
      setRecent(sorted.slice(0, RECENT_LIMIT))
    })
  }

  useEffect(() => {
    if (expanded) reloadRecent()
    else setRecent(null)
  }, [expanded])

  const setRailCollapsed = (next: boolean) => {
    setCollapsed(next)
    writeLocal(RAIL_COLLAPSE_KEY, next ? '1' : '0')
  }

  return (
    <div className="ca-home" data-testid="home-shell">
      <nav
        className="ca-rail"
        data-testid="account-rail"
        data-collapsed={collapsed || undefined}
        data-expanded={expanded || undefined}
      >
        <div className="ca-rail__top">
          {collapsed ? (
            <button
              type="button"
              className="ca-rail__logo ca-rail__logo--btn"
              title={t('home.expandSidebar')}
              aria-label={t('home.expandSidebar')}
              data-testid="rail-expand"
              onClick={() => setRailCollapsed(false)}
            >
              <BrandMark />
            </button>
          ) : (
            <>
              <span className="ca-rail__logo"><BrandMark /></span>
              <button
                type="button"
                className="ca-rail__collapse"
                title={t('home.collapseSidebar')}
                aria-label={t('home.collapseSidebar')}
                data-testid="rail-collapse"
                onClick={() => setRailCollapsed(true)}
              >
                <span className="ca-icon">{Icons.panelLeft}</span>
              </button>
            </>
          )}
        </div>

        <RailBtn icon={Icons.plus} label={t('projectHeader.newProject')} onClick={() => newProject()} expanded={expanded} testId="rail-new" />
        <RailBtn icon={Icons.home} label={t('home.home')} on={view === 'home'} onClick={() => openView('home')} testId="rail-home" expanded={expanded} />
        <RailBtn icon={Icons.folder} label={t('home.projects')} on={view === 'projects'} onClick={() => openView('projects')} testId="rail-projects" expanded={expanded} />
        <RailBtn icon={Icons.skill} label={t('home.skills')} on={view === 'skills'} onClick={() => openView('skills')} testId="rail-skills" expanded={expanded} />
        {/* #495/#539: Assets entry → page shell (src/home/Assets.tsx) */}
        {SHOW_ASSETS ? (
          <RailBtn icon={Icons.assets} label={t('home.assets')} on={view === 'assets'} onClick={() => openView('assets')} testId="rail-assets" expanded={expanded} />
        ) : null}
        {/* #367/#495: Schedules = main bell in the competitor design-commission slot; our name */}
        <RailBtn icon={Icons.bell} label={t('home.designSchedules')} on={view === 'schedules'} onClick={() => openView('schedules')} testId="rail-schedules" expanded={expanded} />
        <RailBtn
          icon={Icons.sparkles}
          label={t('home.arti')}
          on={view === 'arti'}
          onClick={() => openView('arti')}
          testId="rail-arti"
          badge={expanded ? t('home.artiBeta') : undefined} /* #552: collapsed rail hides the Beta badge */
          expanded={expanded}
        />

        {expanded && recent && recent.length > 0 ? (
          <div className="ca-rail__recent" data-testid="rail-recent">
            <div className="ca-rail__recent-title">{t('home.recentProjects')}</div>
            {recent.map((e) => <RecentRow key={e.id} entry={e} onChanged={reloadRecent} />)}
          </div>
        ) : null}

        <div className="ca-rail__spacer" />
        {/* #498: Settings entry — Lucide settings + 设置/Settings; real $x.xx when key+balance OK; history lives in the menu */}
        <SettingsMenu trigger={({ open, toggle }) => (
          <SettingsRailBtn open={open} toggle={toggle} expanded={expanded} />
        )} />
      </nav>
      <main className="ca-home__main">{main(view)}</main>
      <Confirm />
      <MemoryChooser />
      <MemoryToast />
      <MemoryDialog onError={(msg) => showMemoryToast(msg)} />
      <SkillsDialog home onError={(msg) => showMemoryToast(msg, 'error')} />
      <KeySettings />
      <UsageDialog />
    </div>
  )
}
