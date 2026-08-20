import { create } from 'zustand'
import { api } from '../api/client'

// dateStr === null means "today" (routes through /game/today + /game/guess);
// an explicit ISO date routes through /game/day/:date + /game/day/:date/guess
// for archive play. Both share this one store/GameBoard so archive puzzles
// look and behave identically to today's, just without touching stats
// (enforced server-side, see backend/app/blueprints/game/service.py).
export const useGameStore = create((set, get) => ({
  state: null,
  loading: false,
  error: null,
  guessInProgress: false,
  dateStr: null,

  loadPuzzle: async (dateStr = null) => {
    set({ loading: true, error: null, state: null, dateStr })
    try {
      const state = dateStr ? await api.getDay(dateStr) : await api.getToday()
      set({ state, loading: false })
    } catch (err) {
      set({ error: err.message, loading: false })
    }
  },

  // Silent re-fetch used to poll for a guess's degrees value finishing in
  // the background (see GameBoard's polling effect) -- doesn't touch
  // loading/error, so it never flashes the "loading puzzle" state or
  // surfaces a transient failure as a page error.
  refreshPuzzle: async () => {
    const { dateStr } = get()
    try {
      const state = dateStr ? await api.getDay(dateStr) : await api.getToday()
      set({ state })
    } catch {
      // best-effort; the next poll tick will just try again
    }
  },

  submitGuess: async (guessText) => {
    if (get().guessInProgress) return
    set({ guessInProgress: true, error: null })
    try {
      const { dateStr } = get()
      const state = dateStr ? await api.submitDayGuess(dateStr, guessText) : await api.submitGuess(guessText)
      set({ state, guessInProgress: false })
    } catch (err) {
      set({ error: err.message, guessInProgress: false })
    }
  },
}))
