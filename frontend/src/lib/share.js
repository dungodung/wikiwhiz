import { temperatureIndex } from './closeness'

// No green here -- green is reserved exclusively for the winning square
// (guess.is_correct), so the shareable grid reads unambiguously the same
// way Wordle's does: green only ever means "solved", never "close".
const TEMPERATURE_EMOJI = ['🟦', '🟦', '🟨', '🟨', '🟧', '🟥', '🟥']

function guessEmoji(guess) {
  if (guess.is_pass) return '⬜'
  if (guess.is_correct) return '🟩'
  if (guess.lexical_score_bucket == null) return '⬛'
  return TEMPERATURE_EMOJI[temperatureIndex(guess.lexical_score_bucket)]
}

// state is the same shape GameBoard/useGameStore already work with --
// challenge_date, is_today, guesses, total_clues_available.
export function buildShareText(state) {
  const squares = state.guesses.map(guessEmoji).join('')
  const url = state.is_today ? window.location.origin : `${window.location.origin}/archive/${state.challenge_date}`
  return (
    `WikiWhiz — ${state.challenge_date}\n` +
    `Solved in ${state.guesses.length}/${state.total_clues_available}\n` +
    `${squares}\n${url}`
  )
}
