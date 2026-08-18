// Renders the Wheel-of-Fortune-style slot pattern from the backend
// (Article.slot_pattern, see backend/app/lib/slot_pattern.py). Letters stay
// blank until the puzzle is won/lost, at which point solved_answer_title is
// walked in lockstep with the pattern to fill each slot in.
export default function WordSlots({ slotPattern, revealedTitle }) {
  let cursor = 0

  return (
    <div className="word-slots" role="group" aria-label="Answer slots">
      {slotPattern.map((token, i) => {
        if (token.type === 'space') {
          if (revealedTitle) cursor += 1
          return <span key={i} className="word-slots__gap" />
        }
        if (token.type === 'punct') {
          const ch = revealedTitle ? revealedTitle[cursor] : token.char
          if (revealedTitle) cursor += 1
          return (
            <span key={i} className="word-slots__punct">
              {ch}
            </span>
          )
        }
        const letters = revealedTitle ? revealedTitle.slice(cursor, cursor + token.len) : null
        if (revealedTitle) cursor += token.len
        return (
          <span key={i} className="word-slots__word">
            {Array.from({ length: token.len }).map((_, j) => (
              <span key={j} className="word-slots__letter">
                {letters ? letters[j] : ''}
              </span>
            ))}
          </span>
        )
      })}
    </div>
  )
}
