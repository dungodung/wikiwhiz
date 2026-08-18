import { useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import Header from './components/Header/Header'
import GameBoard from './components/GameBoard/GameBoard'
import StatsPage from './components/Stats/StatsPage'
import InfoPage from './components/Info/InfoPage'
import { useAuthStore } from './state/authStore'

export default function App() {
  const checkAuth = useAuthStore((s) => s.checkAuth)

  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  return (
    <div className="app">
      <Header />
      <main className="app__main">
        <Routes>
          <Route path="/" element={<GameBoard />} />
          <Route path="/stats" element={<StatsPage />} />
          <Route path="/info" element={<InfoPage />} />
        </Routes>
      </main>
    </div>
  )
}
