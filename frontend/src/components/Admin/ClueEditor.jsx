import { useState } from 'react'
import { api } from '../../api/client'

const CLUE_TYPES = [
  'commons_image', 'dyk_or_notable_fact', 'wikidata_fact', 'infobox_fact', 'categories',
  'etymology', 'wikisource_excerpt', 'wikivoyage_fact', 'pageviews', 'top_citation',
  'incoming_links', 'long_section_title', 'creation_year', 'langlinks_count',
]

export function NewClueForm({ articleId, onCreated }) {
  const [clueType, setClueType] = useState(CLUE_TYPES[0])
  const [text, setText] = useState('')
  const [rank, setRank] = useState(3)
  const [error, setError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      await api.admin.createClue({ article_id: articleId, clue_type: clueType, clue_text: text, reveal_rank_hint: Number(rank) })
      setText('')
      onCreated()
    } catch (err) {
      setError(err.data?.error === 'clue_leaks_title' ? 'That clue text contains the article title — reword it.' : err.message)
    }
  }

  return (
    <form className="clue-editor__new" onSubmit={submit}>
      <select value={clueType} onChange={(e) => setClueType(e.target.value)}>
        {CLUE_TYPES.map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>
      <input
        type="number"
        min={1}
        max={7}
        value={rank}
        onChange={(e) => setRank(e.target.value)}
        title="Reveal rank hint (1=obscure/first .. 7=revealing/last)"
        style={{ width: '3.5em' }}
      />
      <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Clue text…" style={{ flex: 1 }} />
      <button type="submit">Add clue</button>
      {error && <span className="game-board__status--error">{error}</span>}
    </form>
  )
}

export function ClueRow({ clue, locked, onChanged, onMove, isFirst, isLast }) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(clue.clue_text)
  const [error, setError] = useState(null)

  const save = async () => {
    setError(null)
    try {
      await api.admin.updateClue(clue.id, { clue_text: text })
      setEditing(false)
      onChanged()
    } catch (err) {
      setError(err.data?.error === 'clue_leaks_title' ? 'That clue text contains the article title.' : err.message)
    }
  }

  const remove = async () => {
    if (!window.confirm('Delete this clue?')) return
    await api.admin.deleteClue(clue.id)
    onChanged()
  }

  return (
    <li className="clue-editor__row">
      <span className="clue-editor__type">{clue.clue_type}</span>
      {editing ? (
        <input value={text} onChange={(e) => setText(e.target.value)} style={{ flex: 1 }} />
      ) : (
        <span className="clue-editor__text">{clue.clue_text}</span>
      )}
      {!locked && (
        <span className="clue-editor__actions">
          {editing ? (
            <>
              <button type="button" onClick={save}>Save</button>
              <button type="button" onClick={() => setEditing(false)}>Cancel</button>
            </>
          ) : (
            <>
              <button type="button" onClick={() => onMove(-1)} disabled={isFirst}>↑</button>
              <button type="button" onClick={() => onMove(1)} disabled={isLast}>↓</button>
              <button type="button" onClick={() => setEditing(true)}>Edit</button>
              <button type="button" onClick={remove}>Delete</button>
            </>
          )}
        </span>
      )}
      {error && <span className="game-board__status--error">{error}</span>}
    </li>
  )
}
