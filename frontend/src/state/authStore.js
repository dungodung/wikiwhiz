import { create } from 'zustand'
import { api, LOGIN_URL } from '../api/client'
import { applyTheme, readStoredTheme, writeStoredTheme } from '../lib/theme'

export const useAuthStore = create((set, get) => ({
  authenticated: false,
  username: null,
  isAdmin: false,
  hintModePreference: false,
  // Seeded from localStorage (index.html's pre-paint script already applied
  // it to the DOM) so the toggle UI shows the right state immediately, even
  // before checkAuth's async response can confirm/override it for a
  // logged-in player.
  themePreference: readStoredTheme() || 'dark',
  checked: false,

  checkAuth: async () => {
    try {
      const data = await api.me()
      const theme = data.authenticated ? data.theme_preference || 'dark' : readStoredTheme() || 'dark'
      set({
        authenticated: data.authenticated,
        username: data.username || null,
        isAdmin: data.is_admin || false,
        hintModePreference: data.hint_mode_preference || false,
        themePreference: theme,
        checked: true,
      })
      applyTheme(theme)
      if (data.authenticated) writeStoredTheme(theme)
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

  // Optimistic, same rationale as setHintModePreference below. Anonymous
  // play persists to localStorage instead of the server (see theme.js).
  setThemePreference: async (theme) => {
    set({ themePreference: theme })
    applyTheme(theme)
    if (get().authenticated) {
      writeStoredTheme(theme)
      try {
        await api.setThemePreference(theme)
      } catch {
        // best-effort -- see comment above
      }
    } else {
      writeStoredTheme(theme)
    }
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
