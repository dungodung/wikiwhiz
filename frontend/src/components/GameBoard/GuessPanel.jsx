import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../../api/client'
import TileBoard from './TileBoard'

const PLACEHOLDER = '_'
// Below this many known characters, the search recall (CirrusSearch, capped
// at 50 candidates server-side) is too weak a sample to say "no matches"
// with any confidence -- plenty of real articles could still fit, we just
// haven't been given enough to narrow the field down to any of them yet.
const SPARSE_INPUT_THRESHOLD = 5

function initialLetters(slotPattern) {
  return Array(slotPattern.length).fill('')
}

// Owns the player's in-progress tile fill and submits it as the guess --
// tiles ARE the guess input now, not a separate free-text box. Parent
// (GameBoard) mounts this with `key={challenge_date}` so switching puzzles
// remounts it with fresh state instead of needing a reset effect.
export default function GuessPanel({ slotPattern, dateStr, onSubmit, disabled, guessCount, totalClues }) {
  const tileBoardRef = useRef(null)
  const [letters, setLetters] = useState(() => initialLetters(slotPattern))
  const [hintMode, setHintMode] = useState(false)
  const [suggestions, setSuggestions] = useState(null)
  const [hintLoading, setHintLoading] = useState(false)
  const [hintError, setHintError] = useState(null)
  const [truncated, setTruncated] = useState(false)

  const setLetter = (index, char) => {
    setLetters((prev) => {
      const next = [...prev]
      next[index] = char.slice(-1).toUpperCase()
      return next
    })
  }

  const clearLetters = () => setLetters(initialLetters(slotPattern))

  // A guess that was accepted (right or wrong) shows up as a new entry in
  // guessCount -- clear the board for the next attempt. A *rejected* guess
  // (not a real article) never increments guessCount, so the player's
  // careful letter placement is left alone to fix instead of wiped.
  const prevGuessCount = useRef(guessCount)
  useEffect(() => {
    if (guessCount > prevGuessCount.current) {
      clearLetters()
      // Otherwise the last-filled tile (now empty) keeps DOM focus, and the
      // player has to click before they can type their next guess even
      // though clearing the board already signals "start over".
      tileBoardRef.current?.focusFirst()
    }
    prevGuessCount.current = guessCount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guessCount])

  const pattern = useMemo(() => letters.map((c) => c || PLACEHOLDER).join(''), [letters])
  const isComplete = useMemo(() => letters.every(Boolean), [letters])
  const knownCharCount = useMemo(() => letters.filter(Boolean).length, [letters])

  useEffect(() => {
    if (!hintMode) {
      return undefined
    }
    const hasAnyLetter = letters.some(Boolean)
    if (!hasAnyLetter) {
      setSuggestions(null)
      return undefined
    }
    setHintLoading(true)
    setHintError(null)
    const timer = setTimeout(async () => {
      try {
        const result = await api.getHint(dateStr, pattern)
        if (result.unavailable) {
          setHintError('Hint search is temporarily unavailable — try again in a moment.')
          setSuggestions(null)
        } else {
          setSuggestions(result.matches)
          setTruncated(result.truncated)
        }
      } catch (err) {
        setHintError(err.message)
      } finally {
        setHintLoading(false)
      }
    }, 400)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hintMode, pattern, dateStr])

  const pickSuggestion = (tiles) => {
    setLetters(tiles.split(''))
  }

  const handleSubmit = () => {
    if (!isComplete || disabled) return
    onSubmit(letters.join(''))
  }

  useEffect(() => {
    if (!isComplete || disabled) return undefined
    const handleKeyDown = (e) => {
      if (e.key === 'Enter') handleSubmit()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isComplete, disabled, letters])

  return (
    <div className="guess-panel">
      <p className="guess-panel__count">
        Guess {guessCount + 1} of {totalClues}
      </p>

      <TileBoard ref={tileBoardRef} slotPattern={slotPattern} letters={letters} onLetterChange={setLetter} />

      <div className="guess-panel__actions">
        <button
          type="button"
          className="guess-panel__submit"
          onClick={handleSubmit}
          disabled={!isComplete || disabled}
        >
          Guess
        </button>
        <button type="button" className="guess-panel__clear" onClick={clearLetters} disabled={disabled}>
          Clear
        </button>
        <button
          type="button"
          className="hint-panel__toggle"
          onClick={() => setHintMode((v) => !v)}
          aria-expanded={hintMode}
          title="Fill in any letters (or spaces, dashes, commas, parentheses) you're confident about — leave the rest blank. Matches update as you type."
        >
          {hintMode ? 'Hide hint mode' : 'Hint mode'}
        </button>
      </div>

      {hintMode && (hintLoading || hintError || suggestions !== null) && (
        <div className="hint-panel">
          {hintLoading && <p className="hint-panel__status">Searching…</p>}
          {hintError && <p className="hint-panel__status hint-panel__status--error">{hintError}</p>}
          {!hintLoading && !hintError && suggestions && (
            <>
              {suggestions.length === 0 ? (
                <p className="hint-panel__status">
                  {knownCharCount < SPARSE_INPUT_THRESHOLD
                    ? 'Many articles could still match — type a few more characters to narrow it down.'
                    : 'No matching articles found.'}
                </p>
              ) : (
                <ul className="hint-panel__suggestions">
                  {suggestions.map((m) => (
                    <li key={m.title}>
                      <button type="button" onClick={() => pickSuggestion(m.tiles)} title={m.title}>
                        {m.tiles}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {truncated && (
                <p className="hint-panel__status">More matches exist — fill in another letter to narrow it down.</p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
