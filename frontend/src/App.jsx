import { useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import Header from './components/Header/Header'
import GameBoard from './components/GameBoard/GameBoard'
import ArchivePage from './components/Archive/ArchivePage'
import StatsPage from './components/Stats/StatsPage'
import InfoPage from './components/Info/InfoPage'
import AdminPage from './components/Admin/AdminPage'
import { useAuthStore } from './state/authStore'
import { reportPageView } from './lib/geolocation'

function AdminRoute() {
  const { checked, isAdmin } = useAuthStore()
  if (!checked) return null
  if (!isAdmin) return <p className="game-board__status">Admins only.</p>
  return <AdminPage />
}

export default function App() {
  const checkAuth = useAuthStore((s) => s.checkAuth)

  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  // App only mounts once per real page load (client-side route changes
  // don't remount it), which is exactly "a page view" -- see
  // lib/geolocation.js and backend/app/lib/page_views.py.
  useEffect(() => {
    reportPageView()
  }, [])

  return (
    <div className="app">
      <Header />
      <main className="app__main">
        <Routes>
          <Route path="/" element={<GameBoard />} />
          <Route path="/archive" element={<ArchivePage />} />
          <Route path="/archive/:date" element={<GameBoard />} />
          <Route path="/stats" element={<StatsPage />} />
          <Route path="/info" element={<InfoPage />} />
          <Route path="/admin" element={<AdminRoute />} />
        </Routes>
      </main>
    </div>
  )
}
