import { useState } from 'react'
import { buildShareText } from '../../lib/share'

const CONFIRMATION_MS = 2000

// navigator.share (mobile-friendly native share sheet) when available,
// falling back to clipboard copy -- same pattern most Wordle-likes use.
// Both paths can fail/be cancelled by the user; neither is an error worth
// surfacing beyond just not showing the "Copied!" confirmation.
export default function ShareButton({ state }) {
  const [copied, setCopied] = useState(false)

  const share = async () => {
    const text = buildShareText(state)
    if (navigator.share) {
      try {
        await navigator.share({ text })
      } catch {
        // Cancelled or unsupported mid-call -- no fallback needed, the
        // share sheet itself is the user-visible feedback.
      }
      return
    }
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), CONFIRMATION_MS)
    } catch {
      // Clipboard access denied/unavailable -- nothing more we can do.
    }
  }

  return (
    <button type="button" className="share-button" onClick={share}>
      {copied ? 'Copied!' : 'Share'}
    </button>
  )
}
