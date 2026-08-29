import { useState } from 'react'

// Shared toggle behavior for every admin table's sortable columns: clicking
// the currently-sorted column flips its direction, clicking a different one
// switches to it ascending.
export default function useSort(defaultKey, defaultDirection = 'asc') {
  const [sort, setSort] = useState({ key: defaultKey, direction: defaultDirection })

  const onSort = (key) => {
    setSort((prev) =>
      prev.key === key ? { key, direction: prev.direction === 'asc' ? 'desc' : 'asc' } : { key, direction: 'asc' }
    )
  }

  return [sort, onSort]
}
