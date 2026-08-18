import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import ArticleDetail from './ArticleDetail'

function NewArticleForm({ onCreated }) {
  const [form, setForm] = useState({ wiki_title: '', wiki_pageid: '', display_title: '', summary_extract: '' })
  const [error, setError] = useState(null)
  const [open, setOpen] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      await api.admin.createArticle({ ...form, wiki_pageid: Number(form.wiki_pageid) })
      setForm({ wiki_title: '', wiki_pageid: '', display_title: '', summary_extract: '' })
      setOpen(false)
      onCreated()
    } catch (err) {
      setError(err.data?.error || err.message)
    }
  }

  if (!open) return <button type="button" onClick={() => setOpen(true)}>+ Add article manually</button>

  return (
    <form className="admin-panel__new-article" onSubmit={submit}>
      <input
        placeholder="Exact enwiki title"
        value={form.wiki_title}
        onChange={(e) => setForm({ ...form, wiki_title: e.target.value })}
        required
      />
      <input
        placeholder="Wikipedia pageid"
        type="number"
        value={form.wiki_pageid}
        onChange={(e) => setForm({ ...form, wiki_pageid: e.target.value })}
        required
      />
      <input
        placeholder="Display title"
        value={form.display_title}
        onChange={(e) => setForm({ ...form, display_title: e.target.value })}
        required
      />
      <input
        placeholder="Summary (shown on win/loss)"
        value={form.summary_extract}
        onChange={(e) => setForm({ ...form, summary_extract: e.target.value })}
      />
      <button type="submit">Create</button>
      <button type="button" onClick={() => setOpen(false)}>Cancel</button>
      {error && <span className="game-board__status--error">{error}</span>}
    </form>
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
