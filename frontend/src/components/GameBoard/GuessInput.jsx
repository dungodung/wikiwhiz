import { useState } from 'react'
import OnScreenKeyboard from './OnScreenKeyboard'

export default function GuessInput({ onSubmit, disabled }) {
  const [value, setValue] = useState('')

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSubmit(trimmed)
    setValue('')
  }

  return (
    <div className="guess-input">
      <form
        className="guess-input__form"
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        <input
          className="guess-input__field"
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Type your guess…"
          disabled={disabled}
          aria-label="Your guess"
        />
        <button type="submit" className="guess-input__submit" disabled={disabled || !value.trim()}>
          Guess
        </button>
      </form>
      <OnScreenKeyboard
        onKey={(k) => setValue((v) => v + k)}
        onBackspace={() => setValue((v) => v.slice(0, -1))}
        onEnter={submit}
      />
    </div>
  )
}
