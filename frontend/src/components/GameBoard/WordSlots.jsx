// Renders the Wheel-of-Fortune-style slot pattern from the backend
// (Article.slot_pattern, see backend/app/lib/slot_pattern.py). Letters stay
// blank until the puzzle is won/lost, at which point solved_answer_title is
// walked in lockstep with the pattern to fill each slot in.

// Pure transform: annotate each token with its starting offset into
// revealedTitle, without mutating a loop variable during render.
function withOffsets(slotPattern) {
  return slotPattern.reduce(
    (acc, token) => {
      const charsConsumed = token.type === 'word' ? token.len : token.type === 'punct' || token.type === 'space' ? 1 : 0
      acc.tokens.push({ token, offset: acc.cursor })
      acc.cursor += charsConsumed
      return acc
    },
    { tokens: [], cursor: 0 },
  ).tokens
}

export default function WordSlots({ slotPattern, revealedTitle }) {
  const tokens = withOffsets(slotPattern)

  return (
    <div className="word-slots" role="group" aria-label="Answer slots">
      {tokens.map(({ token, offset }, i) => {
        if (token.type === 'space') {
          return <span key={i} className="word-slots__gap" />
        }
        if (token.type === 'punct') {
          return (
            <span key={i} className="word-slots__punct">
              {revealedTitle ? revealedTitle[offset] : token.char}
            </span>
          )
        }
        const letters = revealedTitle ? revealedTitle.slice(offset, offset + token.len) : null
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
