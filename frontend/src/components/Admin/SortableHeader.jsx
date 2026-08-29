// A <th> that toggles sort on click: unsorted -> ascending -> descending ->
// ascending... Shared across every admin table so sorting behaves and looks
// identical regardless of which page it's in.
export default function SortableHeader({ label, sortKey, sort, onSort }) {
  const active = sort?.key === sortKey
  const arrow = active ? (sort.direction === 'desc' ? ' ▼' : ' ▲') : ''

  return (
    <th>
      <button
        type="button"
        className="admin-table__sort-btn"
        onClick={() => onSort(sortKey)}
        aria-sort={active ? (sort.direction === 'desc' ? 'descending' : 'ascending') : 'none'}
      >
        {label}
        {arrow}
      </button>
    </th>
  )
}
