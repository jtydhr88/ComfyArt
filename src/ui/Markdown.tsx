import type { ReactNode } from 'react'

import { CopyButton } from './CopyButton'
import { isTaskRefCode } from '../wsErrors'

const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)\s]+\))/g

function inline(text: string): ReactNode[] {
  const parts = text.split(INLINE)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) return <strong key={i}>{part.slice(2, -2)}</strong>
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      const c = part.slice(1, -1)  // #715: only the task id after the taskRef prefix gets nowrap/ellipsis/title; other code is main's behaviour
      return isTaskRefCode(parts[i - 1] ?? '') ? <code key={i} className="ca-task-id" title={c}>{c}</code> : <code key={i}>{c}</code>
    }
    const link = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(part)
    if (link) return <a key={i} href={link[2]} target="_blank" rel="noreferrer">{link[1]}</a>
    return part
  })
}

export function Markdown({ text }: { text: string }) {
  const out: ReactNode[] = []
  const lines = text.split('\n')
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    if (line.startsWith('```')) {
      const body: string[] = []
      while (++i < lines.length && !lines[i].startsWith('```')) body.push(lines[i])
      out.push(<div key={i} className="ca-md__code"><pre>{body.join('\n')}</pre><CopyButton text={body.join('\n')} /></div>)
      continue
    }
    if (line.trim().startsWith('|')) {
      const rows: string[][] = []
      for (; i < lines.length && lines[i].trim().startsWith('|'); i++) {
        if (!/^\s*\|[\s:|-]+\|?\s*$/.test(lines[i])) rows.push(lines[i].trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim()))
      }
      i--
      out.push(
        <table key={i}>
          <tbody>{rows.map((r, j) => <tr key={j}>{r.map((c, k) => (j ? <td key={k}>{inline(c)}</td> : <th key={k}>{inline(c)}</th>))}</tr>)}</tbody>
        </table>,
      )
      continue
    }
    const list = /^\s*(?:[-*]|\d+\.)\s+/.exec(line)
    if (list) {
      const ordered = /\d/.test(list[0])
      const items: string[] = []
      for (; i < lines.length && /^\s*(?:[-*]|\d+\.)\s+/.test(lines[i]); i++) items.push(lines[i].replace(/^\s*(?:[-*]|\d+\.)\s+/, ''))
      i--
      const children = items.map((t, j) => <li key={j}>{inline(t)}</li>)
      out.push(ordered ? <ol key={i}>{children}</ol> : <ul key={i}>{children}</ul>)
      continue
    }
    const heading = /^#{1,4}\s+(.*)$/.exec(line)
    if (heading) out.push(<p key={i} className="ca-md__h">{inline(heading[1])}</p>)
    else if (line.trim()) out.push(<p key={i}>{inline(line)}</p>)
  }
  return <div className="ca-md">{out}</div>
}
