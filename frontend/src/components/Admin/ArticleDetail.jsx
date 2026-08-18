import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { ClueRow, NewClueForm } from './ClueEditor'

export default function ArticleDetail({ articleId, onBack }) {
  const [article, setArticle] = useState(null)
  const [error, setError] = useState(null)
  const [scheduleDate, setScheduleDate] = useState('')

  const load = () => {
    api.admin.getArticle(articleId).then(setArticle).catch((err) => setError(err.message))
  }

  useEffect(load, [articleId])

  if (error) return <p className="game-board__status game-board__status--error">{error}</p>
  if (!article) return <p className="game-board__status">Loading…</p>

  const move = async (index, direction) => {
    const ids = article.clues.map((c) => c.id)
    const target = index + direction
    if (target < 0 || target >= ids.length) return
    ;[ids[index], ids[target]] = [ids[target], ids[index]]
    await api.admin.reorderClues(article.id, ids)
    load()
  }

  const promoteReady = async () => {
    setError(null)
    try {
      await api.admin.updateArticle(article.id, { status: 'ready' })
      load()
    } catch (err) {
      setError(err.data?.error === 'not_enough_clues' ? `Needs at least 5 non-leaking clues (has ${err.data.clue_count}).` : err.message)
    }
  }

  const schedule = async () => {
    setError(null)
    try {
      await api.admin.scheduleArticle(article.id, scheduleDate || undefined)
      load()
    } catch (err) {
      setError(err.data?.error || err.message)
    }
  }

  const remove = async () => {
    if (!window.confirm(`Delete "${article.display_title}" and all its clues?`)) return
    await api.admin.deleteArticle(article.id)
    onBack()
  }

  return (
    <div className="admin-article-detail">
      <button type="button" onClick={onBack}>&larr; Back to list</button>
      <h3>{article.display_title}</h3>
      <p>
        Status: <strong>{article.status}</strong>
        {article.scheduled_date && ` — scheduled for ${article.scheduled_date}`}
        {article.locked && ' (locked: live today or in the past)'}
      </p>

      {error && <p className="game-board__status game-board__status--error">{error}</p>}

      <h4>Clues ({article.clues.length})</h4>
      <ul className="clue-editor__list">
        {article.clues.map((clue, i) => (
          <ClueRow
            key={clue.id}
            clue={clue}
            locked={article.locked}
            onChanged={load}
            onMove={(dir) => move(i, dir)}
            isFirst={i === 0}
            isLast={i === article.clues.length - 1}
          />
        ))}
      </ul>

      {!article.locked && <NewClueForm articleId={article.id} onCreated={load} />}

      {!article.locked && (
        <div className="admin-article-detail__actions">
          {article.status === 'draft' && (
            <button type="button" onClick={promoteReady}>Mark ready</button>
          )}
          {article.status === 'ready' && (
            <>
              <input
                type="date"
                value={scheduleDate}
                onChange={(e) => setScheduleDate(e.target.value)}
                title="Leave blank to use the next open date"
              />
              <button type="button" onClick={schedule}>Schedule</button>
            </>
          )}
          <button type="button" onClick={remove}>Delete article</button>
        </div>
      )}
    </div>
  )
}
