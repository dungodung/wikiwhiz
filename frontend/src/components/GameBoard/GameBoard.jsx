import { useEffect } from 'react'
import { useGameStore } from '../../state/gameStore'
import WordSlots from './WordSlots'
import ClueFeed from './ClueFeed'
import ClosenessGradientBar from './ClosenessGradientBar'
import DegreesBadge from './DegreesBadge'
import GuessInput from './GuessInput'

export default function GameBoard() {
  const { state, loading, error, guessInProgress, loadToday, submitGuess } = useGameStore()

  useEffect(() => {
    loadToday()
  }, [loadToday])

  if (loading && !state) return <p className="game-board__status">Loading today's puzzle…</p>
  if (error && !state) return <p className="game-board__status game-board__status--error">{error}</p>
  if (!state) return null

  const lastGuess = state.guesses[state.guesses.length - 1]
  const finished = state.status !== 'in_progress'

  return (
    <div className="game-board">
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

      {!finished && <GuessInput onSubmit={submitGuess} disabled={guessInProgress} />}

      {error && <p className="game-board__status game-board__status--error">{error}</p>}

      <ClueFeed clues={state.clues_revealed} />
    </div>
  )
}
