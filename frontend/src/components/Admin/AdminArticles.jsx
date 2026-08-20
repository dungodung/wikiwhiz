import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import ArticleDetail from './ArticleDetail'

const AUTOCOMPLETE_DEBOUNCE_MS = 250

// The title field doubles as an autocomplete combobox: typing debounces
// into a prefixsearch call (see MediaWikiClient.prefix_search), and
// picking a suggestion resolves it into pageid/display_title/summary
// auto-fill (backend/app/blueprints/admin/routes.py::article_lookup_resolve)
// -- pageid/display_title/summary stay manually editable afterward in case
// the admin wants to override what came back.
function TitleAutocomplete({ value, onChange, onResolved }) {
  const [suggestions, setSuggestions] = useState([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [resolving, setResolving] = useState(false)
  const containerRef = useRef(null)

  useEffect(() => {
    if (!value.trim()) {
      return undefined
    }
    const timer = setTimeout(async () => {
      try {
        const { results } = await api.admin.searchArticleTitles(value)
        setSuggestions(results)
      } catch {
        setSuggestions([])
      }
    }, AUTOCOMPLETE_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [value])

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (!containerRef.current?.contains(e.target)) setShowSuggestions(false)
    }
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [])

  const pickSuggestion = async (title) => {
    onChange(title)
    setShowSuggestions(false)
    setResolving(true)
    try {
      const resolved = await api.admin.resolveArticleLookup(title)
      onResolved(resolved)
    } catch {
      // Resolution failing (network hiccup, page vanished mid-pick) just
      // means the admin fills the rest in by hand -- the title itself is
      // still set, so this isn't a dead end.
    } finally {
      setResolving(false)
    }
  }

  return (
    <div className="admin-autocomplete" ref={containerRef}>
      <input
        placeholder="Exact enwiki title"
        value={value}
        onChange={(e) => {
          onChange(e.target.value)
          setShowSuggestions(true)
        }}
        onFocus={() => setShowSuggestions(true)}
        required
      />
      {resolving && <span className="admin-autocomplete__status">Filling in details…</span>}
      {showSuggestions && value.trim() && suggestions.length > 0 && (
        <ul className="admin-autocomplete__suggestions">
          {suggestions.map((s) => (
            <li key={s.pageid}>
              <button type="button" onClick={() => pickSuggestion(s.title)}>
                {s.title}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

const EMPTY_FORM = { wiki_title: '', wiki_pageid: '', display_title: '', summary_extract: '' }

function NewArticleModal({ onClose, onCreated }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState(null)

  const applyResolved = (resolved) => {
    setForm((prev) => ({
      ...prev,
      wiki_title: resolved.wiki_title,
      wiki_pageid: String(resolved.wiki_pageid),
      display_title: resolved.display_title,
      summary_extract: resolved.summary_extract || prev.summary_extract,
    }))
  }

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      await api.admin.createArticle({ ...form, wiki_pageid: Number(form.wiki_pageid) })
      onCreated()
      onClose()
    } catch (err) {
      setError(err.data?.error || err.message)
    }
  }

  useEffect(() => {
    const handleEscape = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="admin-modal-backdrop" onClick={onClose}>
      <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
        <h3>Add article manually</h3>
        <form className="admin-modal__form" onSubmit={submit}>
          <label>
            Exact enwiki title
            <TitleAutocomplete
              value={form.wiki_title}
              onChange={(wiki_title) => setForm((prev) => ({ ...prev, wiki_title }))}
              onResolved={applyResolved}
            />
          </label>
          <label>
            Wikipedia pageid
            <input
              type="number"
              value={form.wiki_pageid}
              onChange={(e) => setForm({ ...form, wiki_pageid: e.target.value })}
              required
            />
          </label>
          <label>
            Display title
            <input
              value={form.display_title}
              onChange={(e) => setForm({ ...form, display_title: e.target.value })}
              required
            />
          </label>
          <label>
            Summary (shown on win/loss, auto-filled from Wikidata when available)
            <textarea
              value={form.summary_extract}
              onChange={(e) => setForm({ ...form, summary_extract: e.target.value })}
              rows={3}
            />
          </label>
          {error && <p className="game-board__status game-board__status--error game-board__status--inline">{error}</p>}
          <div className="admin-modal__actions">
            <button type="submit">Create</button>
            <button type="button" onClick={onClose}>Cancel</button>
          </div>
        </form>
      </div>
    </div>
  )
}

function NewArticleForm({ onCreated }) {
  const [open, setOpen] = useState(false)

  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>+ Add article manually</button>
      {open && <NewArticleModal onClose={() => setOpen(false)} onCreated={onCreated} />}
    </>
  )
}

export default function AdminArticles() {
  const [status, setStatus] = useState('')
  const [articles, setArticles] = useState([])
  const [error, setError] = useState(null)
  const [selectedId, setSelectedId] = useState(null)

  const load = () => {
    api.admin.listArticles(status).then((data) => setArticles(data.articles)).catch((err) => setError(err.message))
  }

  useEffect(load, [status])

  if (selectedId) {
    return (
      <ArticleDetail
        articleId={selectedId}
        onBack={() => {
          setSelectedId(null)
          load()
        }}
      />
    )
  }

  return (
    <div className="admin-panel">
      <div className="admin-panel__filters">
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="ready">Ready</option>
          <option value="scheduled">Scheduled</option>
          <option value="retired">Retired</option>
        </select>
        <NewArticleForm onCreated={load} />
      </div>

      {error && <p className="game-board__status game-board__status--error">{error}</p>}

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Status</th>
              <th>Clues</th>
              <th>Scheduled</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {articles.map((a) => (
              <tr key={a.id}>
                <td>{a.display_title}</td>
                <td>{a.status}</td>
                <td>{a.clue_count}</td>
                <td>{a.scheduled_date || '—'}</td>
                <td>
                  <button type="button" onClick={() => setSelectedId(a.id)}>Open</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
