import { create } from 'zustand'
import { api, LOGIN_URL } from '../api/client'

export const useAuthStore = create((set) => ({
  authenticated: false,
  username: null,
  checked: false,

  checkAuth: async () => {
    try {
      const data = await api.me()
      set({ authenticated: data.authenticated, username: data.username || null, checked: true })
    } catch {
      set({ authenticated: false, username: null, checked: true })
    }
  },

  login: () => {
    window.location.href = LOGIN_URL
  },

  logout: async () => {
    await api.logout()
    set({ authenticated: false, username: null })
  },
}))
