import { useEffect, useState } from 'react'
import { useAuthStore } from '../../state/authStore'
import { api } from '../../api/client'
import StatsChart from './StatsChart'

export default function StatsPage() {
  const { authenticated, checked, login } = useAuthStore()
  const [stats, setStats] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!authenticated) return
    api.myStats().then(setStats).catch((err) => setError(err.message))
  }, [authenticated])

  if (!checked) return null

  if (!authenticated) {
    return (
      <div className="stats-page stats-page--logged-out">
        <p>Log in with your Wikimedia account to track your WikiWhiz stats across days.</p>
        <button type="button" className="login-button" onClick={login}>
          Log in with Wikimedia
        </button>
      </div>
    )
  }

  if (error) return <p className="game-board__status game-board__status--error">{error}</p>
  if (!stats) return <p className="game-board__status">Loading stats…</p>

  const winPct = stats.games_played ? Math.round((stats.games_won / stats.games_played) * 100) : 0

  return (
    <div className="stats-page">
      <div className="stats-page__summary">
        <div>
          <span className="stats-page__number">{stats.games_played}</span>
          <span className="stats-page__label">Played</span>
        </div>
        <div>
          <span className="stats-page__number">{winPct}%</span>
          <span className="stats-page__label">Win rate</span>
        </div>
        <div>
          <span className="stats-page__number">{stats.current_streak}</span>
          <span className="stats-page__label">Current streak</span>
        </div>
        <div>
          <span className="stats-page__number">{stats.max_streak}</span>
          <span className="stats-page__label">Max streak</span>
        </div>
      </div>
      <h2 className="stats-page__heading">Guess distribution</h2>
      <StatsChart winDistribution={stats.win_distribution} />
    </div>
  )
}
