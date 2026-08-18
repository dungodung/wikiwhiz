import { useEffect, useState } from 'react'
import { api } from '../../api/client'

export default function AdminUsers() {
  const [q, setQ] = useState('')
  const [users, setUsers] = useState([])
  const [error, setError] = useState(null)

  const load = () => {
    api.admin.listUsers(q).then((data) => setUsers(data.users)).catch((err) => setError(err.message))
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
          load()
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
    </div>
  )
}
