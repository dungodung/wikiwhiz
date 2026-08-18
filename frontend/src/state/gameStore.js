import { create } from 'zustand'
import { api } from '../api/client'

export const useGameStore = create((set, get) => ({
  state: null,
  loading: false,
  error: null,
  guessInProgress: false,

  loadToday: async () => {
    set({ loading: true, error: null })
    try {
      const state = await api.getToday()
      set({ state, loading: false })
    } catch (err) {
      set({ error: err.message, loading: false })
    }
  },

  submitGuess: async (guessText) => {
    if (get().guessInProgress) return
    set({ guessInProgress: true, error: null })
    try {
      const state = await api.submitGuess(guessText)
      set({ state, guessInProgress: false })
    } catch (err) {
      set({ error: err.message, guessInProgress: false })
    }
  },
}))
