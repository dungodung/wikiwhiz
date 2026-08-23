import { create } from 'zustand'
import { api, LOGIN_URL } from '../api/client'

export const useAuthStore = create((set, get) => ({
  authenticated: false,
  username: null,
  isAdmin: false,
  hintModePreference: false,
  checked: false,

  checkAuth: async () => {
    try {
      const data = await api.me()
      set({
        authenticated: data.authenticated,
        username: data.username || null,
        isAdmin: data.is_admin || false,
        hintModePreference: data.hint_mode_preference || false,
        checked: true,
      })
    } catch {
      set({ authenticated: false, username: null, isAdmin: false, hintModePreference: false, checked: true })
    }
  },

  login: () => {
    window.location.href = LOGIN_URL
  },

  logout: async () => {
    await api.logout()
    set({ authenticated: false, username: null, isAdmin: false, hintModePreference: false })
  },

  // Optimistic: the toggle should feel instant, and this is low-stakes
  // enough (a display preference, not game state) that a rare failed
  // persist just means it doesn't stick for next time -- not worth
  // rolling back the UI over.
  setHintModePreference: async (enabled) => {
    if (!get().authenticated) return
    set({ hintModePreference: enabled })
    try {
      await api.setHintModePreference(enabled)
    } catch {
      // best-effort -- see comment above
    }
  },
}))
