import ClueCard from './ClueCard'

export default function ClueFeed({ clues, indexOffset = 0, dimmed = false, heading = null, reverse = false }) {
  // `reverse` flips display order (last clue first) while each card keeps
  // its true "Clue N" label -- the index still comes from the clue's
  // original position, not its position in the (possibly reversed) list.
  const ordered = reverse ? [...clues].reverse() : clues
  const indexFor = (i) => (reverse ? indexOffset + clues.length - 1 - i : indexOffset + i)

  return (
    <>
      {heading && <h3 className="clue-feed__heading">{heading}</h3>}
      <ul className={`clue-feed${dimmed ? ' clue-feed--dimmed' : ''}`}>
        {ordered.map((clue, i) => (
          <ClueCard key={clue.clue_id} clue={clue} index={indexFor(i)} animate={!dimmed} />
        ))}
      </ul>
    </>
  )
}
