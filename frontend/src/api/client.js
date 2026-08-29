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
  submitPass: () => request('/game/pass', { method: 'POST' }),
  getArchive: () => request('/game/archive'),
  getDay: (dateStr) => request(`/game/day/${dateStr}`),
  submitDayPass: (dateStr) => request(`/game/day/${dateStr}/pass`, { method: 'POST' }),
  submitDayGuess: (dateStr, guessText) =>
    request(`/game/day/${dateStr}/guess`, { method: 'POST', body: JSON.stringify({ guess_text: guessText }) }),
  getHint: (dateStr, pattern) => request(`/game/day/${dateStr}/hint?pattern=${encodeURIComponent(pattern)}`),
  me: () => request('/auth/me'),
  logout: () => request('/auth/logout', { method: 'POST' }),
  setHintModePreference: (enabled) =>
    request('/auth/hint-mode', { method: 'PATCH', body: JSON.stringify({ enabled }) }),
  myStats: () => request('/stats/me'),

  admin: {
    listUsers: (q = '', page = 1) => request(`/admin/users?q=${encodeURIComponent(q)}&page=${page}`),
    promoteUser: (id) => request(`/admin/users/${id}/promote`, { method: 'POST' }),
    demoteUser: (id) => request(`/admin/users/${id}/demote`, { method: 'POST' }),

    searchArticleTitles: (q) => request(`/admin/article-lookup/search?q=${encodeURIComponent(q)}`),
    resolveArticleLookup: (title) => request(`/admin/article-lookup/resolve?title=${encodeURIComponent(title)}`),

    articleStats: (page = 1) => request(`/admin/article-stats?page=${page}`),

    listArticles: (status = '', page = 1, perPage) =>
      request(
        `/admin/articles?page=${page}${perPage ? `&per_page=${perPage}` : ''}${status ? `&status=${status}` : ''}`
      ),
    getArticle: (id) => request(`/admin/articles/${id}`),
    createArticle: (body) => request('/admin/articles', { method: 'POST', body: JSON.stringify(body) }),
    updateArticle: (id, body) => request(`/admin/articles/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    deleteArticle: (id) => request(`/admin/articles/${id}`, { method: 'DELETE' }),

    createClue: (body) => request('/admin/clues', { method: 'POST', body: JSON.stringify(body) }),
    updateClue: (id, body) => request(`/admin/clues/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    deleteClue: (id) => request(`/admin/clues/${id}`, { method: 'DELETE' }),
    reorderClues: (articleId, clueIds) =>
      request(`/admin/articles/${articleId}/reorder-clues`, { method: 'POST', body: JSON.stringify({ clue_ids: clueIds }) }),

    scheduleArticle: (articleId, dateStr) =>
      request(`/admin/articles/${articleId}/schedule`, {
        method: 'POST',
        body: JSON.stringify(dateStr ? { date: dateStr } : {}),
      }),
    listSchedule: (from, page = 1) => request(`/admin/schedule?from=${from}&page=${page}`),
    assignSchedule: (dateStr, articleId) =>
      request(`/admin/schedule/${dateStr}/assign`, { method: 'POST', body: JSON.stringify({ article_id: articleId }) }),
    unschedule: (dateStr) => request(`/admin/schedule/${dateStr}`, { method: 'DELETE' }),
  },
}

export const LOGIN_URL = `${BASE}/auth/login`
