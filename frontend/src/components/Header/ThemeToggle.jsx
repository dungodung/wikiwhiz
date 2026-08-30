import { useAuthStore } from '../../state/authStore'

// Shared by both LoginButton branches: a logged-out visitor gets this
// directly (left of the Log in button); a logged-in one gets it inside the
// username dropdown. Same control either way, just different placement.
export default function ThemeToggle() {
  const themePreference = useAuthStore((s) => s.themePreference)
  const setThemePreference = useAuthStore((s) => s.setThemePreference)
  const isLight = themePreference === 'light'

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={() => setThemePreference(isLight ? 'dark' : 'light')}
      aria-label={isLight ? 'Switch to dark mode' : 'Switch to light mode'}
    >
      {isLight ? '☀️' : '🌙'}
      <span className="theme-toggle__label">{isLight ? ' Light mode' : ' Dark mode'}</span>
    </button>
  )
}
