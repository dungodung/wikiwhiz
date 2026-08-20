import { useState } from 'react'
import { bucketColor } from '../../lib/closeness'
import { wikipediaUrl } from '../../lib/wikipedia'
import ClosenessGradientBar from './ClosenessGradientBar'
import DegreesBadge from './DegreesBadge'

const TOOLTIP_GAP = 10
const NARROW_BREAKPOINT = 1100

// A compact record of past guesses, floated beside the board -- stands in
// for a Wordle-style grid of predetermined rows (which would take a lot of
// vertical space here) while still giving a sense of how many attempts have
// been used against the total (state.total_clues_available doubles as the
// max-attempts count, since running out of clues is how you lose). Each
// guess's circle carries a rich hover tooltip with the full closeness scale
// and degrees-of-Wikipedia badge for that specific guess, rather than those
// living as an always-visible row for just the most recent guess.
//
// The tooltip is positioned with `position: fixed`, computed from the
// swatch's own bounding rect, rather than `position: absolute` inside the
// swatch -- .guess-history scrolls (`overflow-y: auto`) once there are
// enough guesses, and an absolutely-positioned descendant gets clipped to
// that scrolling container's bounds no matter what coordinates it's given.
// `fixed` positioning isn't subject to an ancestor's overflow, so it can
// render outside the box.
export default function GuessHistory({ guesses, totalClues }) {
  const [hovered, setHovered] = useState(null)

  if (guesses.length === 0) return null

  const showTooltip = (e, guess) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const narrow = window.innerWidth <= NARROW_BREAKPOINT
    if (narrow) {
      setHovered({
        guess,
        placement: 'below',
        top: rect.bottom + TOOLTIP_GAP,
        left: rect.left + rect.width / 2,
      })
    } else {
      setHovered({
        guess,
        placement: 'left',
        top: rect.top + rect.height / 2,
        left: rect.left - TOOLTIP_GAP,
      })
    }
  }
  const hideTooltip = () => setHovered(null)

  return (
    <aside className="guess-history" aria-label="Previous guesses">
      <h3 className="guess-history__heading">
        Guess {guesses.length} of {totalClues}
      </h3>
      <ul className="guess-history__list">
        {guesses.map((g) => (
          <li key={g.attempt_number} className="guess-history__item">
            <span className="guess-history__number">{g.attempt_number}</span>
            <span
              className={`guess-history__swatch${g.degrees_pending ? ' guess-history__swatch--pending' : ''}`}
              style={{ backgroundColor: bucketColor(g.lexical_score_bucket) }}
              tabIndex={0}
              role="button"
              aria-label={
                g.degrees_pending
                  ? 'Degrees of Wikipedia still being calculated for this guess'
                  : 'Closeness and degrees of Wikipedia for this guess'
              }
              onMouseEnter={(e) => showTooltip(e, g)}
              onMouseLeave={hideTooltip}
              onFocus={(e) => showTooltip(e, g)}
              onBlur={hideTooltip}
            >
              {g.degrees_pending ? (
                <span aria-hidden="true">⚙</span>
              ) : g.degrees_capped ? (
                '+'
              ) : g.degrees_value === 0 ? (
                <span aria-hidden="true">✓</span>
              ) : (
                g.degrees_value
              )}
            </span>
            {g.resolved_title ? (
              <a
                className="guess-history__text"
                href={wikipediaUrl(g.resolved_title)}
                target="_blank"
                rel="noopener noreferrer"
              >
                {g.resolved_title}
              </a>
            ) : (
              <span className="guess-history__text">{g.raw_guess_text}</span>
            )}
          </li>
        ))}
      </ul>

      {hovered && (
        <div
          className={`guess-history__tooltip guess-history__tooltip--${hovered.placement}`}
          style={{ top: hovered.top, left: hovered.left }}
        >
          <ClosenessGradientBar bucket={hovered.guess.lexical_score_bucket} />
          <DegreesBadge
            degrees={hovered.guess.degrees_value}
            capped={hovered.guess.degrees_capped}
            pending={hovered.guess.degrees_pending}
          />
        </div>
      )}
    </aside>
  )
}
