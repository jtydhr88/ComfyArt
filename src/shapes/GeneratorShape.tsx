import { Fragment, type ReactNode } from 'react'
import { TOP_UP_URL, isTaskRefCode } from '../wsErrors'
import {
  BaseBoxShapeUtil,
  createShapePropsMigrationIds,
  createShapePropsMigrationSequence,
  HTMLContainer,
  T,
  type RecordProps,
  type TLShape,
  useEditor,
  useValue,
} from 'tldraw'

import { isVideo } from '../models'
import { errorText, resultsAtom, stopJob } from '../jobs'
import { Icons } from '../ui/icons'
import { t } from '../i18n'

export const GENERATOR = 'generator'
/** #287: shared with the home composer, which has no editor to ask for defaults. */
export const GENERATOR_DEFAULTS: GeneratorShape['props'] = { w: 512, h: 512, prompt: '', ratio: '1:1', resolution: '1K', count: 1, workflow: '', duration: 5, transparent: false, quality: 'standard', style: '', cw: 1024, ch: 1024 }

declare module 'tldraw' {
  export interface TLGlobalShapePropsMap {
    [GENERATOR]: {
      w: number
      h: number
      prompt: string
      ratio: string
      resolution: string
      count: number
      workflow: string
      duration: number
      transparent: boolean
      quality: string
      style: string
      cw: number
      ch: number
    }
  }
}

export type GeneratorShape = TLShape<typeof GENERATOR>

const versions = createShapePropsMigrationIds(GENERATOR, { AddDuration: 1, AddOptions: 2 })

/** #163: the top-up URL in the insufficient-balance copy is clickable; same text, no new wording. */
export function withTopUpLink(text: string): ReactNode {
  // #715 design: a `task id` renders as a nowrap, copyable <code> (full id in title); its own line via pre-line CSS
  if (/`[^`\n]+`/.test(text)) {
    const ps = text.split(/(`[^`\n]+`)/)
    return <>{ps.map((p, k) => (k % 2 ? (isTaskRefCode(ps[k - 1]) ? <code key={k} className="ca-task-id" title={p.slice(1, -1)}>{p.slice(1, -1)}</code> : <code key={k}>{p.slice(1, -1)}</code>) : <Fragment key={k}>{linkTopUp(p)}</Fragment>))}</>
  }
  return linkTopUp(text)
}

function linkTopUp(text: string): ReactNode {
  const i = text.indexOf(TOP_UP_URL)
  if (i < 0) return text
  return <>{text.slice(0, i)}<a href={TOP_UP_URL} target="_blank" rel="noreferrer" onPointerDown={(e) => e.stopPropagation()}>{TOP_UP_URL}</a>{text.slice(i + TOP_UP_URL.length)}</>
}

export class GeneratorShapeUtil extends BaseBoxShapeUtil<GeneratorShape> {
  static override type = GENERATOR
  static override props: RecordProps<GeneratorShape> = {
    w: T.number,
    h: T.number,
    prompt: T.string,
    ratio: T.string,
    resolution: T.string,
    count: T.number,
    workflow: T.string,
    duration: T.number,
    transparent: T.boolean,
    quality: T.string,
    style: T.string,
    cw: T.number,
    ch: T.number,
  }

  static override migrations = createShapePropsMigrationSequence({
    sequence: [
      { id: versions.AddDuration, up: (props) => { props.duration = 5 } },
      { id: versions.AddOptions, up: (props) => Object.assign(props, { transparent: false, quality: 'standard', style: '', cw: 1024, ch: 1024 }) },
    ],
  })

  override getDefaultProps(): GeneratorShape['props'] {
    return { ...GENERATOR_DEFAULTS }
  }

  override canEdit() {
    return false
  }

  /** #356: while generating — no selection border / resize / rotate chrome (reference design) */
  override hideSelectionBoundsFg(shape: GeneratorShape) {
    return !!(shape.meta as { job?: unknown }).job
  }

  override hideSelectionBoundsBg(shape: GeneratorShape) {
    return !!(shape.meta as { job?: unknown }).job
  }

  override hideResizeHandles(shape: GeneratorShape) {
    return !!(shape.meta as { job?: unknown }).job
  }

  override hideRotateHandle(shape: GeneratorShape) {
    return !!(shape.meta as { job?: unknown }).job
  }

  override component(shape: GeneratorShape) {
    return <GeneratorCard shape={shape} />
  }

  override getIndicatorPath(shape: GeneratorShape) {
    // Empty path while generating so no selection stroke either
    const path = new Path2D()
    if ((shape.meta as { job?: unknown }).job) return path
    path.rect(0, 0, shape.props.w, shape.props.h)
    return path
  }
}

function GeneratorCard({ shape }: { shape: GeneratorShape }) {
  const editor = useEditor()
  const job = shape.meta.job as { id: string; stopping?: boolean } | undefined
  const error = useValue('generator error', () => (job ? undefined : resultsAtom.get()[shape.id]?.error), [job?.id, shape.id])
  return (
    <HTMLContainer
      className={job ? 'ca-gen-card ca-gen-frame' : 'ca-gen-card'}
      data-running={job ? true : undefined}
      style={{ width: '100%', height: '100%' }}
    >
      <span className="ca-gen-card__icon">{isVideo(shape.props.workflow) ? Icons.video : Icons.image}</span>
      {error && <div className="ca-gen-card__error" role="alert">{withTopUpLink(error)}</div>}
      {job && (
        <button
          type="button"
          className="ca-gen-card__stop"
          title={t('jobs.stop')}
          aria-label={t('jobs.stop')}
          disabled={job.stopping}
          onPointerDown={(e) => e.stopPropagation()}
          onClick={() => void stopJob(editor, shape.id).catch((e) => {
            // stop failure only — success settles via finish without a toast
            resultsAtom.update((r) => ({ ...r, [shape.id]: { srcs: r[shape.id]?.srcs ?? [], error: errorText(e) } }))
          })}
        >{Icons.stop}</button>
      )}
      {job && <div className="ca-gen-frame__pill">{t('taskDetails.generating')}</div>}
    </HTMLContainer>
  )
}
