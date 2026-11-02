import { useCallback, useEffect, useState } from 'react'
import { atom, useValue } from 'tldraw'

import { api } from '../comfy'
import { lang, t } from '../i18n'
import { keyStatusAtom, refreshKeyStatus } from '../wavespeedKey'
import { Icons } from './icons'
import { Modal } from './Modal'

/** #498 Usage modal open state (left-bottom Settings › balance). */
export const usageOpenAtom = atom('usage open', false)

type UsageRow = { id: string; detail: string; tool: string; amount_usd: number; created_at: number }

type UsagePage = { items: UsageRow[]; total: number; page: number; page_size: number }

const PAGE_SIZE = 10

function formatWhen(ts: number): string {
  if (!ts) return '—'
  const d = new Date(ts * 1000)
  const opts: Intl.DateTimeFormatOptions = { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }
  return d.toLocaleString(lang === 'zh' ? 'zh-CN' : 'en-US', opts)
}

function formatSpend(n: number): string {
  return `-$${Number(n).toFixed(2)}`
}

export function UsageDialog() {
  const open = useValue(usageOpenAtom)
  const keyStatus = useValue(keyStatusAtom)
  const [page, setPage] = useState(1)
  const [data, setData] = useState<UsagePage | null>(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async (p: number) => {
    setLoading(true)
    try {
      const res = await api(`/comfyart/usage?page=${p}&page_size=${PAGE_SIZE}`).catch(() => null)
      if (!res?.ok) { setData({ items: [], total: 0, page: p, page_size: PAGE_SIZE }); return }
      setData(await res.json() as UsagePage)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!open) return
    setPage(1)
    void refreshKeyStatus()
    void load(1)
  }, [open, load])

  useEffect(() => {
    if (!open || page === 1) return
    void load(page)
  }, [page, open, load])

  if (!open) return null

  const balance = keyStatus?.configured && keyStatus.balance !== null
    ? `$${keyStatus.balance.toFixed(2)}`
    : null
  const total = data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const items = data?.items ?? []

  return (
    <Modal title={t('settings.usage')} className="ca-usage" onClose={() => usageOpenAtom.set(false)}>
      <div className="ca-usage__body">
        <div className="ca-usage__top" data-testid="usage-balance">
          <span className="ca-usage__bal-label">{t('wsKey.balanceTitle')}</span>
          <span className="ca-usage__bal-value">{balance ?? '—'}</span>
        </div>
        <div className="ca-usage__table-wrap">
          <table className="ca-usage__table">
            <thead>
              <tr>
                <th>{t('settings.usageDetail')}</th>
                <th>{t('settings.usageDate')}</th>
                <th>{t('settings.usageCost')}</th>
              </tr>
            </thead>
            <tbody>
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={3} className="ca-usage__empty" data-testid="usage-empty">{t('settings.usageEmpty')}</td>
                </tr>
              )}
              {items.map((row) => (
                <tr key={row.id} data-testid="usage-row">
                  <td className="ca-usage__detail" title={row.detail}>{row.detail || row.tool || '—'}</td>
                  <td className="ca-usage__date">{formatWhen(row.created_at)}</td>
                  <td className="ca-usage__cost">{formatSpend(row.amount_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="ca-usage__foot">
          <span className="ca-usage__note">{t('settings.usageFootnote')}</span>
          <div className="ca-usage__pager">
            <button type="button" className="ca-panel__secondary" disabled={page <= 1 || loading} onClick={() => setPage((p) => Math.max(1, p - 1))} data-testid="usage-prev">
              <span className="ca-icon">{Icons.chevron}</span>
            </button>
            <span className="ca-usage__page" data-testid="usage-page">{page} / {pages}</span>
            <button type="button" className="ca-panel__secondary" disabled={page >= pages || loading} onClick={() => setPage((p) => p + 1)} data-testid="usage-next">
              <span className="ca-icon" style={{ transform: 'rotate(-90deg)' }}>{Icons.chevron}</span>
            </button>
          </div>
        </div>
      </div>
    </Modal>
  )
}
