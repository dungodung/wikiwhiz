const BASE = '/api'

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const error = new Error(data?.error || `Request failed: ${response.status}`)
    error.status = response.status
    error.data = data
    throw error
  }
  return data
}

export const api = {
  getToday: () => request('/game/today'),
  submitGuess: (guessText) =>
    request('/game/guess', { method: 'POST', body: JSON.stringify({ guess_text: guessText }) }),
  me: () => request('/auth/me'),
  logout: () => request('/auth/logout', { method: 'POST' }),
  myStats: () => request('/stats/me'),
}

export const LOGIN_URL = `${BASE}/auth/login`
