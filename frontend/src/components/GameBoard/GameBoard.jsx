import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useGameStore } from '../../state/gameStore'
import WordSlots from './WordSlots'
import ClueFeed from './ClueFeed'
import ClosenessGradientBar from './ClosenessGradientBar'
import DegreesBadge from './DegreesBadge'
import GuessInput from './GuessInput'
import HintPanel from './HintPanel'

export default function GameBoard() {
  const { date: routeDate } = useParams()
  const { state, loading, error, guessInProgress, loadPuzzle, submitGuess } = useGameStore()
  const [guessText, setGuessText] = useState('')
  const [hintMode, setHintMode] = useState(false)

  useEffect(() => {
    loadPuzzle(routeDate || null)
  }, [loadPuzzle, routeDate])

  if (loading && !state) return <p className="game-board__status">Loading puzzle…</p>
  if (error && !state) return <p className="game-board__status game-board__status--error">{error}</p>
  if (!state) return null

  const lastGuess = state.guesses[state.guesses.length - 1]
  const finished = state.status !== 'in_progress'

  const handleSubmit = (text) => {
    submitGuess(text)
    setGuessText('')
  }

  return (
    <div className="game-board">
      {!state.is_today && (
        <p className="game-board__archive-banner">
          Playing {state.challenge_date} from the archive — <Link to="/archive">choose another day</Link>. This
          doesn't count toward your stats.
        </p>
      )}

      <WordSlots slotPattern={state.slot_pattern} revealedTitle={finished ? state.solved_answer_title : null} />

      <div className="game-board__closeness">
        <ClosenessGradientBar bucket={lastGuess?.lexical_score_bucket ?? null} />
        <DegreesBadge degrees={lastGuess?.degrees_value ?? null} capped={lastGuess?.degrees_capped ?? false} />
      </div>

      {finished && (
        <div className={`game-board__result game-board__result--${state.status}`}>
          {state.status === 'won' ? (
            <p>
              Solved in {state.guesses.length} guess{state.guesses.length === 1 ? '' : 'es'}!
            </p>
          ) : (
            <p>Out of clues — the answer was <strong>{state.solved_answer_title}</strong>.</p>
          )}
          {state.summary_extract && <p className="game-board__summary">{state.summary_extract}</p>}
        </div>
      )}

      {!finished && (
        <>
          <GuessInput value={guessText} onChange={setGuessText} onSubmit={handleSubmit} disabled={guessInProgress} />
          <button
            type="button"
            className="hint-panel__toggle"
            onClick={() => setHintMode((v) => !v)}
            aria-expanded={hintMode}
          >
            {hintMode ? 'Hide hint mode' : 'Hint mode'}
          </button>
          {hintMode && (
            <HintPanel
              key={state.challenge_date}
              slotPattern={state.slot_pattern}
              dateStr={state.challenge_date}
              onPickSuggestion={setGuessText}
            />
          )}
        </>
      )}

      {error && <p className="game-board__status game-board__status--error">{error}</p>}

      <ClueFeed clues={state.clues_revealed} />
    </div>
  )
}
