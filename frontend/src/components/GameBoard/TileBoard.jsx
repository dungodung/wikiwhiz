import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'

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
//
// A long title (e.g. "Ludwig van Beethoven", 22 tiles) can force the row to
// wrap on narrower screens. A wide viewport gets a single unbroken row
// instead (see the >=900px rule in global.css); below that, wrapping is
// grouped by word so a break only ever falls right after a real space --
// never mid-word. On the read-only (finished) board every character is
// known, so every group (including the last) is a real, complete word. On
// the editable board a space is only known once the player has actually
// typed one themselves (the board can't know word positions ahead of that
// without giving away unsolved structure) -- so the trailing run after the
// last typed space is "open": still possibly one long word, or the start of
// several the player hasn't reached yet. An open group renders with
// `display: contents` (see .tile-board__word--open in global.css) so its
// tiles fall back to being direct children of the wrapping outer container,
// exactly like before this grouping existed -- critically, this lets that
// run wrap freely tile-by-tile when it doesn't fit, rather than forcing it
// onto one line no matter what (which was a real bug caught in testing:
// without this, a long blank board on a narrow screen got crushed down to
// illegible slivers instead of wrapping, since flexbox will shrink an
// unbreakable nowrap group to fit before it'll let it overflow).
function groupIntoWords(values, { allowOpenTrailing = false } = {}) {
  const groups = []
  let current = []
  values.forEach((value, index) => {
    current.push(index)
    if (value === ' ') {
      groups.push({ indices: current, closed: true })
      current = []
    }
  })
  if (current.length) groups.push({ indices: current, closed: !allowOpenTrailing })
  return groups
}

const INTERACTIVE_SELECTOR = 'button, a, input, textarea, select, [role="button"], [tabindex]'

const TileBoard = forwardRef(function TileBoard(
  { slotPattern, letters = [], onLetterChange, readOnly, revealedTiles },
  ref
) {
  const inputRefs = useRef({})
  const length = slotPattern.length

  const focusTile = (index) => {
    inputRefs.current[index]?.focus()
  }

  // Exposed so a parent can pull focus back to tile 0 after a submitted
  // guess clears the board -- otherwise the last-filled tile (now empty)
  // keeps DOM focus, and the player has to click before typing again even
  // though they clearly want to start a fresh guess from the beginning.
  useImperativeHandle(ref, () => ({
    focusFirst: () => focusTile(0),
  }))

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

  useEffect(() => {
    if (readOnly) return undefined

    const handleDocumentClick = (e) => {
      if (e.target.closest(INTERACTIVE_SELECTOR)) return
      focusTile(firstEmptyIndex())
    }

    const handleDocumentKeyDown = (e) => {
      // Same guard as handleDocumentClick above -- without it, Space
      // (e.key === ' ', a length-1 string) steals focus away from any
      // other focused interactive control (a button, a link, the hint-mode
      // switch) mid-press, so its native Space/Enter activation never
      // completes. Only redirect when focus isn't already on something
      // that's supposed to receive the keystroke itself.
      if (document.activeElement?.closest(INTERACTIVE_SELECTOR)) return
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
    const values = slotPattern.split('').map((_, i) => (revealedTiles ? revealedTiles[i] : ''))
    return (
      <div className="tile-board-viewport">
        <div className="tile-board" role="group" aria-label="Answer tiles">
          {groupIntoWords(values).map((group, gi) => (
            <span className="tile-board__word" key={gi}>
              {group.indices.map((i) => (
                <span key={i} className="tile-board__tile tile-board__tile--filled">
                  {values[i]}
                </span>
              ))}
            </span>
          ))}
        </div>
      </div>
    )
  }

  const values = slotPattern.split('').map((_, i) => letters[i] || '')
  return (
    <div className="tile-board-viewport">
      <div className="tile-board" role="group" aria-label="Answer tiles">
        {groupIntoWords(values, { allowOpenTrailing: true }).map((group, gi) => (
          <span className={`tile-board__word${group.closed ? '' : ' tile-board__word--open'}`} key={gi}>
            {group.indices.map((i) => (
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
          </span>
        ))}
      </div>
    </div>
  )
})

export default TileBoard
