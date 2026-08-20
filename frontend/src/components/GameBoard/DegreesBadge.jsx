export default function DegreesBadge({ degrees, capped, pending }) {
  let label = '—'
  if (capped) label = '6+'
  else if (degrees != null) label = String(degrees)

  return (
    <div className="degrees-badge" title="Degrees of Wikipedia: link-hops between your guess and the answer">
      {pending ? (
        <span className="degrees-badge__value degrees-badge__value--pending" aria-hidden="true">
          ⚙
        </span>
      ) : (
        <span className="degrees-badge__value">{label}</span>
      )}
      <span className="degrees-badge__caption">
        {pending ? 'calculating degrees of Wikipedia…' : 'degrees of Wikipedia'}
      </span>
    </div>
  )
}
