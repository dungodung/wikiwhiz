import { useEffect, useState } from 'react'
import { api } from '../../api/client'

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

function addDaysIso(iso, days) {
  const d = new Date(`${iso}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}

export default function AdminSchedule() {
  const [days, setDays] = useState([])
  const [readyArticles, setReadyArticles] = useState([])
  const [error, setError] = useState(null)
  const [reassigning, setReassigning] = useState(null) // challenge_date currently being reassigned

  const load = () => {
    const from = todayIso()
    const to = addDaysIso(from, 30)
    api.admin.listSchedule(from, to).then((data) => setDays(data.days)).catch((err) => setError(err.message))
    api.admin.listArticles('ready').then((data) => setReadyArticles(data.articles)).catch(() => {})
  }

  useEffect(load, [])

  const unschedule = async (dateStr) => {
    if (!window.confirm(`Unschedule ${dateStr}? The article reverts to 'ready'.`)) return
    try {
      await api.admin.unschedule(dateStr)
      load()
    } catch (err) {
      setError(err.data?.error || err.message)
    }
  }

  const assign = async (dateStr, articleId) => {
    try {
      await api.admin.assignSchedule(dateStr, Number(articleId))
      setReassigning(null)
      load()
    } catch (err) {
      setError(err.data?.error || err.message)
    }
  }

  return (
    <div className="admin-panel">
      <p>Next 30 days. Today and past days are locked and cannot be changed here.</p>
      {error && <p className="game-board__status game-board__status--error">{error}</p>}
      <div className="admin-table-wrap">
      <table className="admin-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Article</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {days.map((d) => (
            <tr key={d.challenge_date}>
              <td>{d.challenge_date}</td>
              <td>{d.wiki_title}</td>
              <td>
                {!d.locked && (
                  <>
                    {reassigning === d.challenge_date ? (
                      <select onChange={(e) => e.target.value && assign(d.challenge_date, e.target.value)} defaultValue="">
                        <option value="" disabled>
                          Pick a ready article…
                        </option>
                        {readyArticles.map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.display_title}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <button type="button" onClick={() => setReassigning(d.challenge_date)}>Reassign</button>
                    )}
                    <button type="button" onClick={() => unschedule(d.challenge_date)}>Unschedule</button>
                  </>
                )}
                {d.locked && <em>locked</em>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  )
}
