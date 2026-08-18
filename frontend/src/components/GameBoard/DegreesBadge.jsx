export default function DegreesBadge({ degrees, capped }) {
  let label = '—'
  if (capped) label = '6+'
  else if (degrees != null) label = String(degrees)

  return (
    <div className="degrees-badge" title="Degrees of Wikipedia: link-hops between your guess and the answer">
      <span className="degrees-badge__value">{label}</span>
      <span className="degrees-badge__caption">degrees of Wikipedia</span>
    </div>
  )
}
