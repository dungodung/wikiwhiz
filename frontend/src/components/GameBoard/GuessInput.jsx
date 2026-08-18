import OnScreenKeyboard from './OnScreenKeyboard'

export default function GuessInput({ value, onChange, onSubmit, disabled }) {
  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSubmit(trimmed)
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
          onChange={(e) => onChange(e.target.value)}
          placeholder="Type your guess…"
          disabled={disabled}
          aria-label="Your guess"
        />
        <button type="submit" className="guess-input__submit" disabled={disabled || !value.trim()}>
          Guess
        </button>
      </form>
      <OnScreenKeyboard
        onKey={(k) => onChange(value + k)}
        onBackspace={() => onChange(value.slice(0, -1))}
        onEnter={submit}
      />
    </div>
  )
}
