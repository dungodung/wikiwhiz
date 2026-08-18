import ClueCard from './ClueCard'

export default function ClueFeed({ clues }) {
  return (
    <ul className="clue-feed">
      {clues.map((clue, i) => (
        <ClueCard key={clue.clue_id} clue={clue} index={i} />
      ))}
    </ul>
  )
}
