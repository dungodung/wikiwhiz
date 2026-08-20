import { useState } from 'react'
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

export default function AdminPage() {
  const [tab, setTab] = useState('articles')
  const { Component } = TABS[tab]

  return (
    <div className="admin-page">
      <nav className="admin-page__tabs">
        {Object.entries(TABS).map(([key, { label }]) => (
          <button
            key={key}
            type="button"
            className={tab === key ? 'admin-page__tab admin-page__tab--active' : 'admin-page__tab'}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </nav>
      <Component />
    </div>
  )
}
