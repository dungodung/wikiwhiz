import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import Pager from './Pager'

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

export default function AdminSchedule() {
  const [days, setDays] = useState([])
  const [readyArticles, setReadyArticles] = useState([])
  const [error, setError] = useState(null)
  const [reassigning, setReassigning] = useState(null) // challenge_date currently being reassigned
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)

  const load = () => {
    api.admin
      .listSchedule(todayIso(), page)
      .then((data) => {
        setDays(data.days)
        setTotalPages(data.total_pages)
      })
      .catch((err) => setError(err.message))
    // The reassign dropdown needs every ready article, not just one page of
    // them -- MAX_PER_PAGE (100) rather than the default 20.
    api.admin.listArticles('ready', 1, 100).then((data) => setReadyArticles(data.articles)).catch(() => {})
  }

  useEffect(load, [page])

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
      <p>Upcoming scheduled days. Today and past days are locked and cannot be changed here.</p>
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
      <Pager page={page} totalPages={totalPages} onChange={setPage} />
    </div>
  )
}
