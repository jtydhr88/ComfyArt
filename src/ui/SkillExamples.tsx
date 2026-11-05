import { useState } from 'react'

import { t } from '../i18n'
import { filmstripIndexLabel, isSkillMediaVideo } from '../skills'
import { isPendingWash } from '../skillRaw748'
import { Icons } from './icons'

/** #751 — a slot whose wash has not landed: the existing empty-state grey plate + image icon (one per slot, never a real still). */
export function PendingWash({ stage }: { stage?: boolean }) {
  return <div className="ca-skillrun__pending" data-pending-wash="1" data-stage={stage || undefined} data-testid="skill-run-pending-wash" aria-label={t('skillRun.noExamples')}><span className="ca-icon">{Icons.image}</span></div>
}

/** #541 「效果示例」: 704×506 contain-centred stage + thumbnail strip.
 *  #593: numbered filmstrip so left-column examples match dual-column gold UX.
 *  #601: zero-padded index 01…10 (padStart 2).
 *  #575: examples may mix stills and short mp4 — stage muted-loops the current clip; leave selection → next still/video.
 *  #641: empty list → 「暂无示例」. Stage skeleton and retry stay inside this section. */
function ExampleMedia({ src, stage }: { src: string; stage?: boolean }) {
  if (isPendingWash(src)) return <PendingWash stage={stage} />
  if (isSkillMediaVideo(src)) {
    return (
      <video
        key={src}
        src={src}
        muted
        loop
        playsInline
        preload="metadata"
        autoPlay={!!stage}
        data-testid={stage ? 'skill-run-example-stage-video' : 'skill-run-example-thumb-video'}
        aria-hidden="true"
      />
    )
  }
  return <img src={src} alt="" />
}

/** Local frame load: skeleton until the current still/video is ready; failure offers retry. Cached media resolves in the ref. */
function StageFrame({ src }: { src: string }) {
  return isPendingWash(src)
    ? <div className="ca-skillrun__stage" data-testid="skill-run-example-stage" data-media="image" data-state="pending-wash"><PendingWash stage /></div>
    : <LoadedStage src={src} />
}

function LoadedStage({ src }: { src: string }) {
  const [attempt, setAttempt] = useState(0)
  const token = `${attempt}:${src}`
  const [readyFor, setReadyFor] = useState('')
  const [failedFor, setFailedFor] = useState('')
  const ready = readyFor === token
  const failed = failedFor === token
  const video = isSkillMediaVideo(src)
  const shown = attempt > 0 ? `${src}${src.includes('?') ? '&' : '?'}retry=${attempt}` : src
  const markReady = () => setReadyFor((cur) => (cur === token ? cur : token))
  const bind = (el: HTMLImageElement | HTMLVideoElement | null) => {
    if (!el || failed) return
    if (el instanceof HTMLImageElement && el.complete && el.naturalWidth > 0) markReady()
    if (el instanceof HTMLVideoElement && el.readyState >= 2) markReady()
  }
  return (
    <div
      className="ca-skillrun__stage"
      data-testid="skill-run-example-stage"
      data-media={video ? 'video' : 'image'}
      data-state={failed ? 'error' : ready ? 'ready' : 'loading'}
      aria-busy={ready || failed ? undefined : true}
    >
      {failed ? (
        <div className="ca-skillrun__mediaerr" data-testid="skill-run-example-error">
          <span>{t('skillRun.exampleFailed')}</span>
          <button type="button" data-testid="skill-run-example-retry" onClick={() => { setFailedFor(''); setAttempt((n) => n + 1) }}>{t('skillRun.retry')}</button>
        </div>
      ) : (
        <>
          {!ready && <span className="ca-skillrun__skel" data-testid="skill-run-example-loading" aria-hidden="true" />}
          {video ? (
            <video
              ref={bind}
              key={token}
              src={shown}
              muted
              loop
              playsInline
              preload="metadata"
              autoPlay
              data-testid="skill-run-example-stage-video"
              aria-hidden="true"
              onLoadedData={markReady}
              onError={() => setFailedFor(token)}
            />
          ) : (
            <img ref={bind} key={token} src={shown} alt="" onLoad={markReady} onError={() => setFailedFor(token)} />
          )}
        </>
      )}
    </div>
  )
}

export function SkillExamples({ examples, pendingWash }: { examples?: string[]; pendingWash?: number[] }) {
  const [at, setAt] = useState(0)
  if (examples && !examples.length) {
    return (
      <section className="ca-skillrun__examples" data-testid="skill-run-examples" data-count={0} data-state="empty">
        <div className="ca-skillrun__section">{t('skillRun.examples')}</div>
        <p className="ca-skillrun__empty" data-testid="skill-run-examples-empty">{t('skillRun.noExamples')}</p>
      </section>
    )
  }
  if (!examples?.length) return null
  const cur = examples[Math.min(at, examples.length - 1)]
  return (
    <section className="ca-skillrun__examples" data-testid="skill-run-examples" data-count={examples.length} data-pending-wash={pendingWash?.length ?? 0}>
      <div className="ca-skillrun__section">{t('skillRun.examples')}</div>
      <StageFrame key={cur} src={cur} />
      {examples.length > 1 && (
        <div className="ca-skillrun__strip" role="tablist">
          {examples.map((src, i) => (
            <button key={`${src}-${i}`} type="button" role="tab" aria-selected={i === at} data-on={i === at || undefined}
              className="ca-skillrun__thumb" data-testid="skill-run-example-thumb" data-index={i + 1}
              data-media={isSkillMediaVideo(src) ? 'video' : 'image'} data-pending-wash={pendingWash?.includes(i) || undefined}
              onClick={() => setAt(i)}>
              <ExampleMedia src={src} />
              <span className="ca-skillrun__thumbnum" aria-hidden="true">{filmstripIndexLabel(i + 1)}</span>
            </button>
          ))}
        </div>
      )}
    </section>
  )
}
