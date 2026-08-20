import { useEffect, useRef } from 'react'

// Renders the flat tile board from the backend (Article.slot_pattern, see
// backend/app/lib/slot_pattern.py): one row of tiles, all of them guessable
// -- letters and kept punctuation (space, dash, comma, parenthesis) alike.
// Nothing is pre-revealed; the player has to figure out both the letters
// and where any spaces/dashes/commas/parens fall. In readOnly mode (game
// finished) it shows revealedTiles instead of accepting input.
//
// Editable mode owns keyboard behavior: typing a character fills the tile
// and advances to the next one; Backspace on an empty tile steps back and
// clears the previous tile; arrow keys step focus without touching content.
// The text caret itself is hidden (see .tile-board__tile in global.css) so
// only the focused tile's highlight shows the active position -- there's
// never a visible blinking cursor to manage.
//
// Two conveniences so the player doesn't have to aim precisely at a tile
// before they can start typing: clicking any non-interactive spot on the
// page focuses the first empty tile, and typing a character while nothing
// is focused redirects that keystroke to the first empty tile too (see the
// document-level listeners below).

const INTERACTIVE_SELECTOR = 'button, a, input, textarea, select, [role="button"], [tabindex]'

export default function TileBoard({ slotPattern, letters = [], onLetterChange, readOnly, revealedTiles }) {
  const inputRefs = useRef({})
  const length = slotPattern.length

  const focusTile = (index) => {
    inputRefs.current[index]?.focus()
  }

  const stepTo = (fromIndex, direction) => {
    const next = fromIndex + direction
    if (next >= 0 && next < length) {
      focusTile(next)
    }
  }

  const firstEmptyIndex = () => {
    const idx = letters.findIndex((c) => !c)
    return idx === -1 ? 0 : idx
  }

  const handleChange = (index, rawValue) => {
    const char = rawValue.slice(-1).toUpperCase()
    onLetterChange(index, char)
    if (char) stepTo(index, 1)
  }

  const handleKeyDown = (index, e) => {
    if (e.key === 'Backspace' && !letters[index]) {
      e.preventDefault()
      if (index > 0) {
        onLetterChange(index - 1, '')
        focusTile(index - 1)
      }
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault()
      stepTo(index, -1)
    } else if (e.key === 'ArrowRight') {
      e.preventDefault()
      stepTo(index, 1)
    }
  }

  const isOwnTile = (el) => Object.values(inputRefs.current).includes(el)

  useEffect(() => {
    if (readOnly) return undefined

    const handleDocumentClick = (e) => {
      if (e.target.closest(INTERACTIVE_SELECTOR)) return
      focusTile(firstEmptyIndex())
    }

    const handleDocumentKeyDown = (e) => {
      if (isOwnTile(document.activeElement)) return
      if (e.ctrlKey || e.metaKey || e.altKey) return
      if (e.key.length !== 1) return
      focusTile(firstEmptyIndex())
    }

    document.addEventListener('click', handleDocumentClick)
    document.addEventListener('keydown', handleDocumentKeyDown)
    return () => {
      document.removeEventListener('click', handleDocumentClick)
      document.removeEventListener('keydown', handleDocumentKeyDown)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [readOnly, letters])

  if (readOnly) {
    return (
      <div className="tile-board" role="group" aria-label="Answer tiles">
        {slotPattern.split('').map((_, i) => (
          <span key={i} className="tile-board__tile tile-board__tile--filled">
            {revealedTiles ? revealedTiles[i] : ''}
          </span>
        ))}
      </div>
    )
  }

  return (
    <div className="tile-board" role="group" aria-label="Answer tiles">
      {slotPattern.split('').map((_, i) => (
        <input
          key={i}
          ref={(el) => {
            inputRefs.current[i] = el
          }}
          className="tile-board__tile"
          maxLength={1}
          value={letters[i] || ''}
          onChange={(e) => handleChange(i, e.target.value)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          onFocus={(e) => e.target.select()}
          aria-label={`Tile ${i + 1}`}
        />
      ))}
    </div>
  )
}
