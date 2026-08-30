const THEME_STORAGE_KEY = 'wikiwhiz:themePreference'

// Logged-in players' theme preference lives server-side (see authStore);
// anonymous play has no account to attach it to, so it's kept in
// localStorage instead -- also used as a same-device cache of a logged-in
// player's last-known choice, so a reload can apply the right theme before
// the async /auth/me response comes back (see index.html's pre-paint
// script, which reads this same key to avoid a flash of the wrong theme).
export function readStoredTheme() {
  try {
    const value = localStorage.getItem(THEME_STORAGE_KEY)
    return value === 'light' ? 'light' : value === 'dark' ? 'dark' : null
  } catch {
    return null
  }
}

export function writeStoredTheme(theme) {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme)
  } catch {
    // Preference just won't persist -- same as before this existed.
  }
}

export function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme === 'light' ? 'light' : 'dark')
}
