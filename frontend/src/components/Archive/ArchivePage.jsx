import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'

const WEEKDAYS = ['S', 'M', 'T', 'W', 'T', 'F', 'S']

function groupByMonth(days) {
  const byMonth = new Map()
  for (const day of days) {
    const monthKey = day.challenge_date.slice(0, 7)
    if (!byMonth.has(monthKey)) byMonth.set(monthKey, [])
    byMonth.get(monthKey).push(day)
  }
  return [...byMonth.entries()].sort((a, b) => (a[0] < b[0] ? 1 : -1))
}

function MonthGrid({ monthKey, days }) {
  const byDate = useMemo(() => Object.fromEntries(days.map((d) => [d.challenge_date, d])), [days])
  const [year, month] = monthKey.split('-').map(Number)
  const firstOfMonth = new Date(Date.UTC(year, month - 1, 1))
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate()
  const leadingBlanks = firstOfMonth.getUTCDay()
  const monthLabel = firstOfMonth.toLocaleDateString(undefined, { month: 'long', year: 'numeric', timeZone: 'UTC' })

  const cells = []
  for (let i = 0; i < leadingBlanks; i++) cells.push(null)
  for (let day = 1; day <= daysInMonth; day++) {
    const iso = `${monthKey}-${String(day).padStart(2, '0')}`
    cells.push(byDate[iso] || { challenge_date: iso, missing: true })
  }

  return (
    <div className="archive-month">
      <h3 className="archive-month__label">{monthLabel}</h3>
      <div className="archive-month__weekdays">
        {WEEKDAYS.map((w, i) => (
          <span key={i}>{w}</span>
        ))}
      </div>
      <div className="archive-month__grid">
        {cells.map((cell, i) => {
          if (!cell) return <span key={i} className="archive-day archive-day--blank" />
          if (cell.missing) return <span key={i} className="archive-day archive-day--missing">{Number(cell.challenge_date.slice(8))}</span>
          const dayNum = Number(cell.challenge_date.slice(8))
          return (
            <Link
              key={i}
              to={cell.is_today ? '/' : `/archive/${cell.challenge_date}`}
              className={`archive-day archive-day--${cell.status}${cell.is_today ? ' archive-day--today' : ''}`}
              title={`${cell.challenge_date}: ${cell.status.replace('_', ' ')}`}
            >
              {dayNum}
            </Link>
          )
        })}
      </div>
    </div>
  )
}

export default function ArchivePage() {
  const [days, setDays] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.getArchive().then((data) => setDays(data.days)).catch((err) => setError(err.message))
  }, [])

  if (error) return <p className="game-board__status game-board__status--error">{error}</p>
  if (!days) return <p className="game-board__status">Loading archive…</p>
  if (days.length === 0) return <p className="game-board__status">No past puzzles yet — check back tomorrow!</p>

  return (
    <div className="archive-page">
      <p className="archive-page__legend">
        <span className="archive-legend-swatch archive-day--won" /> solved{' '}
        <span className="archive-legend-swatch archive-day--lost" /> missed{' '}
        <span className="archive-legend-swatch archive-day--in_progress" /> in progress{' '}
        <span className="archive-legend-swatch archive-day--not_started" /> not played
      </p>
      {groupByMonth(days).map(([monthKey, monthDays]) => (
        <MonthGrid key={monthKey} monthKey={monthKey} days={monthDays} />
      ))}
    </div>
  )
}
