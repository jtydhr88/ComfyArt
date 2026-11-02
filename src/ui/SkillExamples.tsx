import { useState } from 'react'

import { t } from '../i18n'
import { filmstripIndexLabel, isSkillMediaVideo } from '../skills'

/** #541 「效果示例」: 704×506 contain-centred stage + thumbnail strip.
 *  #593: numbered filmstrip so left-column examples match dual-column gold UX.
 *  #601: zero-padded index 01…10 (padStart 2).
 *  #575: examples may mix stills and short mp4 — stage muted-loops the current clip; leave selection → next still/video. */
function ExampleMedia({ src, stage }: { src: string; stage?: boolean }) {
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

export function SkillExamples({ examples }: { examples?: string[] }) {
  const [at, setAt] = useState(0)
  if (!examples?.length) return null
  const cur = examples[Math.min(at, examples.length - 1)]
  return (
    <section className="ca-skillrun__examples" data-testid="skill-run-examples" data-count={examples.length}>
      <div className="ca-skillrun__section">{t('skillRun.examples')}</div>
      <div className="ca-skillrun__stage" data-testid="skill-run-example-stage" data-media={isSkillMediaVideo(cur) ? 'video' : 'image'}>
        <ExampleMedia src={cur} stage />
      </div>
      {examples.length > 1 && (
        <div className="ca-skillrun__strip" role="tablist">
          {examples.map((src, i) => (
            <button key={`${src}-${i}`} type="button" role="tab" aria-selected={i === at} data-on={i === at || undefined}
              className="ca-skillrun__thumb" data-testid="skill-run-example-thumb" data-index={i + 1}
              data-media={isSkillMediaVideo(src) ? 'video' : 'image'}
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
