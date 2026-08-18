import { useState } from 'react'

const ROWS = ['QWERTYUIOP', 'ASDFGHJKL', 'ZXCVBNM']

// A typing aid, not a per-letter Wordle keyboard: guesses are whole titles,
// so keys just append to the current guess input. Hidden by default.
export default function OnScreenKeyboard({ onKey, onBackspace, onEnter }) {
  const [visible, setVisible] = useState(false)

  return (
    <div className="on-screen-keyboard">
      <button
        type="button"
        className="on-screen-keyboard__toggle"
        onClick={() => setVisible((v) => !v)}
        aria-expanded={visible}
      >
        {visible ? 'Hide keyboard' : 'Show on-screen keyboard'}
      </button>
      {visible && (
        <div className="on-screen-keyboard__keys">
          {ROWS.map((row, i) => (
            <div key={i} className="on-screen-keyboard__row">
              {row.split('').map((letter) => (
                <button
                  key={letter}
                  type="button"
                  className="on-screen-keyboard__key"
                  onClick={() => onKey(letter)}
                >
                  {letter}
                </button>
              ))}
            </div>
          ))}
          <div className="on-screen-keyboard__row">
            <button type="button" className="on-screen-keyboard__key on-screen-keyboard__key--wide" onClick={() => onKey(' ')}>
              space
            </button>
            <button type="button" className="on-screen-keyboard__key on-screen-keyboard__key--wide" onClick={onBackspace}>
              ⌫
            </button>
            <button type="button" className="on-screen-keyboard__key on-screen-keyboard__key--wide" onClick={onEnter}>
              enter
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
