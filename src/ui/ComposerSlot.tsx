import { useRef, useState } from 'react'

import { t } from '../i18n'
import { Icons } from './icons'
import { VoiceButton, type State as VoiceState } from './VoiceButton'

/** #250/#268/#276: one 32px round action slot shared by the canvas composer and the home composer.
 *  Empty input → voice (waveform); text or an attached image → send (↑). Whitespace-only counts as empty.
 *  The slot does not flip while an IME is composing (`composing`), and stays on voice while recording. */
export function useSlot(hasContent: boolean, composing: boolean) {
  const [voice, setVoice] = useState<VoiceState>('idle')
  const ref = useRef(false)
  if (!composing) ref.current = hasContent && voice === 'idle'
  return { showSend: ref.current, setVoice }
}

export function ComposerSlot({ showSend, setVoice, canSend, onSend, onText, onError, title, onStop }: {
  showSend: boolean; setVoice: (s: VoiceState) => void; canSend: boolean; onSend: () => void
  onText: (text: string) => void; onError: (msg: string) => void; title?: string
  /** #763: while a turn is running the same slot becomes Stop (solid square); no separate working/stop chrome. */
  onStop?: () => void
}) {
  if (onStop) {
    return (
      <div className="ca-composer__slotwrap" data-slot="stop">
        <button type="button" className="ca-gen__send ca-composer__slot" data-slot="stop" data-testid="composer-stop" title={t('agentPanel.stop')} aria-label={t('agentPanel.stop')} onClick={onStop}>
          <span className="ca-icon">{Icons.stop}</span>
        </button>
      </div>
    )
  }
  return (
    <div className="ca-composer__slotwrap" data-slot={showSend ? 'send' : 'voice'}>
      <VoiceButton slot hidden={showSend} onState={setVoice} onError={onError} onText={onText} />
      {showSend && (
        <button type="button" className="ca-gen__send ca-composer__slot" data-slot="send" disabled={!canSend} title={title ?? t('composer.send')} onClick={onSend}>
          <span className="ca-icon">{Icons.send}</span>
        </button>
      )}
    </div>
  )
}
