import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import Pager from './Pager'

export default function AdminUsers() {
  const [q, setQ] = useState('')
  const [users, setUsers] = useState([])
  const [error, setError] = useState(null)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)

  const load = () => {
    api.admin
      .listUsers(q, page)
      .then((data) => {
        setUsers(data.users)
        setTotalPages(data.total_pages)
      })
      .catch((err) => setError(err.message))
  }

  // Search is submit-triggered, not live-as-you-type -- q is deliberately
  // excluded so typing doesn't refetch on every keystroke.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [page])

  const toggle = async (user) => {
    setError(null)
    try {
      if (user.is_admin) await api.admin.demoteUser(user.id)
      else await api.admin.promoteUser(user.id)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="admin-panel">
      <form
        className="admin-panel__search"
        onSubmit={(e) => {
          e.preventDefault()
          if (page === 1) load()
          else setPage(1) // effect on [page] reloads with the new query
        }}
      >
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search username…" />
        <button type="submit">Search</button>
      </form>

      {error && <p className="game-board__status game-board__status--error">{error}</p>}

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Username</th>
              <th>Admin</th>
              <th>Joined</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.username}</td>
                <td>{u.is_admin ? 'Yes' : 'No'}</td>
                <td>{new Date(u.created_at).toLocaleDateString()}</td>
                <td>
                  <button type="button" onClick={() => toggle(u)}>
                    {u.is_admin ? 'Demote' : 'Promote'}
                  </button>
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
