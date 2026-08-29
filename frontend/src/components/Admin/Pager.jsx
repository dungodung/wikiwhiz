export default function Pager({ page, totalPages, onChange }) {
  if (totalPages <= 1) return null

  return (
    <div className="admin-pager">
      <button type="button" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        Previous
      </button>
      <span className="admin-pager__status">
        Page {page} of {totalPages}
      </span>
      <button type="button" disabled={page >= totalPages} onClick={() => onChange(page + 1)}>
        Next
      </button>
    </div>
  )
}
