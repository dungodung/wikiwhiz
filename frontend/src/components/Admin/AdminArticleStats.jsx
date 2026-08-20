import { useEffect, useState } from 'react'
import { api } from '../../api/client'

export default function AdminArticleStats() {
  const [rows, setRows] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.admin
      .articleStats()
      .then((data) => setRows(data.articles))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="admin-panel">
      <p className="admin-panel__hint">
        Every daily challenge from the start of history through today — future, unplayed days aren't shown since
        they have no sessions yet.
      </p>

      {error && <p className="game-board__status game-board__status--error game-board__status--inline">{error}</p>}
      {loading && <p className="game-board__status">Loading…</p>}

      {!loading && !error && (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Article</th>
                <th>Date</th>
                <th>Attempted</th>
                <th>Won (total)</th>
                <th>Won (registered)</th>
                <th>Failed (total)</th>
                <th>Failed (registered)</th>
                <th>Avg. guess to win</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.article_id}>
                  <td>{r.display_title}</td>
                  <td>{r.challenge_date}</td>
                  <td>{r.attempted}</td>
                  <td>{r.won_total}</td>
                  <td>{r.won_registered}</td>
                  <td>{r.failed_total}</td>
                  <td>{r.failed_registered}</td>
                  <td>{r.avg_win_guess ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
