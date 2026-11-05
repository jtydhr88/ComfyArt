import { useState } from 'react'
import { useValue } from 'tldraw'

import { installedAtom, IMAGE_MODELS, modelPrefsAtom, saveModelPrefs, VIDEO_MODELS } from '../models'
import { Icons } from './icons'
import { Popover } from './Popover'
import { t } from '../i18n'

export function ModelPrefs({ onError, within = '.ca-composer', side = 'top' }: { onError: (msg: string) => void; within?: string; side?: 'top' | 'bottom' }) {
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState<'image' | 'video'>('image')
  const prefs = useValue(modelPrefsAtom)
  const installed = useValue(installedAtom)
  const save = (next: typeof prefs) => void saveModelPrefs(next).catch((e) => onError(String(e)))
  const toggle = (id: string) => save({ ...prefs, enabled: prefs.enabled.includes(id) ? prefs.enabled.filter((x) => x !== id) : [...prefs.enabled, id] })

  return (
    <Popover
      open={open}
      onOpenChange={setOpen}
      side={side}
      viewportCap={side === 'bottom'}
      align="end"
      within={within}
      trigger={({ open: o, toggle: flip }) => (
        <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('modelPrefs.modelPreferences')} data-open={o || undefined} onClick={flip}>
          <span className="ca-icon">{Icons.cube}</span>{/* #763: cube model button */}
        </button>
      )}
    >
      <div className="ca-menu ca-modelprefs">
        <div className="ca-modelprefs__head">
          <span className="ca-menu__grow">{t('modelPrefs.modelPreferences')}</span>
          <span className="ca-chat__hint">{t('common.auto')}</span>
          <button type="button" className="ca-switch" role="switch" aria-checked={prefs.auto} data-on={prefs.auto || undefined} onClick={() => save({ ...prefs, auto: !prefs.auto })}><span /></button>
        </div>
        <div className="ca-panel__chips">
          <button type="button" className="ca-panel__chip" data-on={tab === 'image' || undefined} onClick={() => setTab('image')}>{t('modelPrefs.image')}</button>
          <button type="button" className="ca-panel__chip" data-on={tab === 'video' || undefined} onClick={() => setTab('video')}>{t('modelPrefs.video')}</button>
        </div>
        <div className="ca-chat__hint">{prefs.auto ? t('modelPrefs.theAgentPicksAutomaticallyFrom') : t('modelPrefs.theAgentOnlyUsesChecked')}</div>
        {(tab === 'image' ? IMAGE_MODELS : VIDEO_MODELS).map((m) => {
          const missing = !!installed && !installed.includes(m.id)
          const on = prefs.auto || prefs.enabled.includes(m.id)
          return (
            <label key={m.id} className="ca-menu__item ca-modelprefs__row" data-missing={missing || undefined}>
              <span className="ca-menu__grow ca-model"><span>{m.label}</span><span className="ca-model__desc">{m.desc}</span></span>
              <input type="checkbox" checked={on && !missing} disabled={prefs.auto || missing} onChange={() => toggle(m.id)} />
            </label>
          )
        })}
      </div>
    </Popover>
  )
}
