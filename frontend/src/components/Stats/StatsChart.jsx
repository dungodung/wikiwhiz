export default function StatsChart({ winDistribution }) {
  const keys = ['1', '2', '3', '4', '5', '6', '7', 'failed']
  const max = Math.max(1, ...keys.map((k) => winDistribution[k] || 0))

  return (
    <div className="stats-chart">
      {keys.map((key) => {
        const count = winDistribution[key] || 0
        return (
          <div key={key} className="stats-chart__row">
            <span className="stats-chart__key">{key === 'failed' ? 'X' : key}</span>
            <div className="stats-chart__bar-track">
              <div className="stats-chart__bar" style={{ width: `${(count / max) * 100}%` }} />
            </div>
            <span className="stats-chart__count">{count}</span>
          </div>
        )
      })}
    </div>
  )
}
