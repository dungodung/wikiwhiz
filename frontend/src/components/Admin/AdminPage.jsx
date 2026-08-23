import { Navigate, useNavigate, useParams } from 'react-router-dom'
import AdminUsers from './AdminUsers'
import AdminArticles from './AdminArticles'
import AdminSchedule from './AdminSchedule'
import AdminArticleStats from './AdminArticleStats'

const TABS = {
  articles: { label: 'Articles & clues', Component: AdminArticles },
  schedule: { label: 'Schedule', Component: AdminSchedule },
  stats: { label: 'Article stats', Component: AdminArticleStats },
  users: { label: 'Users', Component: AdminUsers },
}

// Tab comes from the URL (see App.jsx's /admin/:tab route) rather than
// local state, so a refresh or a shared/bookmarked link lands back on the
// same subpage instead of always resetting to the first tab.
export default function AdminPage() {
  const { tab } = useParams()
  const navigate = useNavigate()

  if (!TABS[tab]) return <Navigate to="/admin/articles" replace />
  const { Component } = TABS[tab]

  return (
    <div className="admin-page">
      <nav className="admin-page__tabs">
        {Object.entries(TABS).map(([key, { label }]) => (
          <button
            key={key}
            type="button"
            className={tab === key ? 'admin-page__tab admin-page__tab--active' : 'admin-page__tab'}
            onClick={() => navigate(`/admin/${key}`)}
          >
            {label}
          </button>
        ))}
      </nav>
      <Component />
    </div>
  )
}
