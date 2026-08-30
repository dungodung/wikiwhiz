import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import Pager from './Pager'
import SortableHeader from './SortableHeader'
import useSort from './useSort'
import { wikipediaUrl } from '../../lib/wikipedia'

export default function AdminArticleStats() {
  const [rows, setRows] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [sort, onSort] = useSort('date', 'desc')

  useEffect(() => {
    api.admin
      .articleStats(page, sort)
      .then((data) => {
        setRows(data.articles)
        setTotalPages(data.total_pages)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [page, sort])

  const changeSort = (key) => {
    onSort(key)
    setPage(1)
  }

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
          <table className="admin-table admin-table--compact">
            <thead>
              <tr>
                <SortableHeader label="Article" sortKey="article" sort={sort} onSort={changeSort} />
                <SortableHeader label="Date" sortKey="date" sort={sort} onSort={changeSort} />
                <SortableHeader label="Attempted" sortKey="attempted" sort={sort} onSort={changeSort} />
                <SortableHeader
                  label={<>Won<br />(total)</>}
                  sortKey="won_total"
                  sort={sort}
                  onSort={changeSort}
                />
                <SortableHeader
                  label={<>Won<br />(registered)</>}
                  sortKey="won_registered"
                  sort={sort}
                  onSort={changeSort}
                />
                <SortableHeader
                  label={<>Failed<br />(total)</>}
                  sortKey="failed_total"
                  sort={sort}
                  onSort={changeSort}
                />
                <SortableHeader
                  label={<>Failed<br />(registered)</>}
                  sortKey="failed_registered"
                  sort={sort}
                  onSort={changeSort}
                />
                <SortableHeader
                  label={<>Avg. guess<br />to win</>}
                  sortKey="avg_win_guess"
                  sort={sort}
                  onSort={changeSort}
                />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.article_id}>
                  <td>
                    <a href={wikipediaUrl(r.wiki_title)} target="_blank" rel="noopener noreferrer">
                      {r.display_title}
                    </a>
                  </td>
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
      {!loading && !error && <Pager page={page} totalPages={totalPages} onChange={setPage} />}
    </div>
  )
}
