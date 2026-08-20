import { useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useGameStore } from '../../state/gameStore'
import TileBoard from './TileBoard'
import ClueFeed from './ClueFeed'
import GuessPanel from './GuessPanel'
import GuessHistory from './GuessHistory'
import { wikipediaUrl } from '../../lib/wikipedia'

const DEGREES_POLL_INTERVAL_MS = 3000

export default function GameBoard() {
  const { date: routeDate } = useParams()
  const { state, loading, error, guessInProgress, loadPuzzle, submitGuess, refreshPuzzle } = useGameStore()

  useEffect(() => {
    loadPuzzle(routeDate || null)
  }, [loadPuzzle, routeDate])

  // While any guess is still waiting on its live degrees-of-Wikipedia
  // computation (see backend GuessAttempt.degrees_pending), poll for it to
  // finish instead of leaving the cogwheel placeholder up forever.
  const hasPendingDegrees = state?.guesses.some((g) => g.degrees_pending)
  useEffect(() => {
    if (!hasPendingDegrees) return undefined
    const id = setInterval(refreshPuzzle, DEGREES_POLL_INTERVAL_MS)
    return () => clearInterval(id)
  }, [hasPendingDegrees, refreshPuzzle])

  if (loading && !state) return <p className="game-board__status">Loading puzzle…</p>
  if (error && !state) return <p className="game-board__status game-board__status--error">{error}</p>
  if (!state) return null

  const finished = state.status !== 'in_progress'

  return (
    <div className="game-board">
      {!state.is_today && (
        <p className="game-board__archive-banner">
          Playing {state.challenge_date} from the archive — <Link to="/archive">choose another day</Link>. This
          doesn't count toward your stats.
        </p>
      )}

      {finished && (
        <TileBoard slotPattern={state.slot_pattern} readOnly revealedTiles={state.solved_answer_tiles} />
      )}

      {finished && (
        <div className={`game-board__result game-board__result--${state.status} game-board__result--enter`}>
          {state.status === 'won' ? (
            <p>
              Solved in {state.guesses.length} guess{state.guesses.length === 1 ? '' : 'es'}! The answer was{' '}
              <a href={wikipediaUrl(state.solved_answer_title)} target="_blank" rel="noopener noreferrer">
                <strong>{state.solved_answer_title}</strong>
              </a>
              .
            </p>
          ) : (
            <p>
              Out of clues — the answer was{' '}
              <a href={wikipediaUrl(state.solved_answer_title)} target="_blank" rel="noopener noreferrer">
                <strong>{state.solved_answer_title}</strong>
              </a>
              .
            </p>
          )}
          {state.summary_extract && <p className="game-board__summary">{state.summary_extract}</p>}
        </div>
      )}

      {!finished && (
        <GuessPanel
          key={state.challenge_date}
          slotPattern={state.slot_pattern}
          dateStr={state.challenge_date}
          onSubmit={submitGuess}
          disabled={guessInProgress}
          guessCount={state.guesses.length}
          totalClues={state.total_clues_available}
        />
      )}

      <GuessHistory guesses={state.guesses} totalClues={state.total_clues_available} />

      {error && <p className="game-board__status game-board__status--error">{error}</p>}

      <ClueFeed clues={state.clues_revealed} />

      {state.status === 'won' && state.remaining_clues.length > 0 && (
        <ClueFeed
          clues={state.remaining_clues}
          indexOffset={state.clues_revealed.length}
          dimmed
          heading="Clues you didn't need"
        />
      )}
    </div>
  )
}
