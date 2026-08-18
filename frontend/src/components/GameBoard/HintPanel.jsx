import { useEffect, useMemo, useState } from 'react'
import { api } from '../../api/client'

const PLACEHOLDER = '_'

// Flattens slot_pattern's "word" tokens into a single letters array (one
// entry per letter position across the whole title), which is what the
// hint API's `pattern` param expects -- spaces/punctuation are implied by
// the puzzle's own slot_pattern server-side, so the client only ever sends
// letters. The player can fill any box, in any order; blanks stay wildcards.
//
// Parent (GameBoard) mounts this with `key={challenge_date}`, so switching
// puzzles remounts it with fresh state instead of needing a reset effect.
function useLetterState(slotPattern) {
  const totalLetters = useMemo(
    () => slotPattern.filter((t) => t.type === 'word').reduce((sum, t) => sum + t.len, 0),
    [slotPattern],
  )
  const [letters, setLetters] = useState(() => Array(totalLetters).fill(''))

  const setLetter = (index, char) => {
    setLetters((prev) => {
      const next = [...prev]
      next[index] = char.slice(-1).toUpperCase()
      return next
    })
  }

  const pattern = letters.map((l) => l || PLACEHOLDER).join('')
  return { letters, setLetter, pattern }
}

export default function HintPanel({ slotPattern, dateStr, onPickSuggestion }) {
  const { letters, setLetter, pattern } = useLetterState(slotPattern)
  const [suggestions, setSuggestions] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [truncated, setTruncated] = useState(false)

  useEffect(() => {
    const hasAnyLetter = letters.some(Boolean)
    if (!hasAnyLetter) {
      setSuggestions(null)
      return undefined
    }
    setLoading(true)
    setError(null)
    const timer = setTimeout(async () => {
      try {
        const result = await api.getHint(dateStr, pattern)
        if (result.unavailable) {
          setError('Hint search is temporarily unavailable — try again in a moment.')
          setSuggestions(null)
        } else {
          setSuggestions(result.matches)
          setTruncated(result.truncated)
        }
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }, 400)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pattern, dateStr])

  let letterCursor = 0

  return (
    <div className="hint-panel">
      <p className="hint-panel__instructions">
        Fill in any letters you're confident about — leave the rest blank. Matches update as you type.
      </p>
      <div className="hint-panel__slots">
        {slotPattern.map((token, i) => {
          if (token.type === 'space') return <span key={i} className="word-slots__gap" />
          if (token.type === 'punct') {
            return (
              <span key={i} className="word-slots__punct">
                {token.char}
              </span>
            )
          }
          const start = letterCursor
          letterCursor += token.len
          return (
            <span key={i} className="word-slots__word">
              {Array.from({ length: token.len }).map((_, j) => {
                const idx = start + j
                return (
                  <input
                    key={j}
                    className="hint-panel__letter"
                    maxLength={1}
                    value={letters[idx]}
                    onChange={(e) => setLetter(idx, e.target.value)}
                    aria-label={`Letter ${idx + 1}`}
                  />
                )
              })}
            </span>
          )
        })}
      </div>

      {loading && <p className="hint-panel__status">Searching…</p>}
      {error && <p className="hint-panel__status hint-panel__status--error">{error}</p>}
      {suggestions && !loading && !error && (
        <>
          {suggestions.length === 0 ? (
            <p className="hint-panel__status">No matching articles found.</p>
          ) : (
            <ul className="hint-panel__suggestions">
              {suggestions.map((title) => (
                <li key={title}>
                  <button type="button" onClick={() => onPickSuggestion(title)}>
                    {title}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {truncated && <p className="hint-panel__status">More matches exist — fill in another letter to narrow it down.</p>}
        </>
      )}
    </div>
  )
}
