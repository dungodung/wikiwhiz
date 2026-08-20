import ClueCard from './ClueCard'

export default function ClueFeed({ clues, indexOffset = 0, dimmed = false, heading = null }) {
  return (
    <>
      {heading && <h3 className="clue-feed__heading">{heading}</h3>}
      <ul className={`clue-feed${dimmed ? ' clue-feed--dimmed' : ''}`}>
        {clues.map((clue, i) => (
          <ClueCard key={clue.clue_id} clue={clue} index={indexOffset + i} animate={!dimmed} />
        ))}
      </ul>
    </>
  )
}
