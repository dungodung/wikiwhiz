import { NavLink, useLocation } from 'react-router-dom'
import LoginButton from './LoginButton'
import { useAuthStore } from '../../state/authStore'

export default function Header() {
  const isAdmin = useAuthStore((s) => s.isAdmin)
  const { pathname } = useLocation()

  // Navigating to "/" while already on "/" is a no-op for the router, so a
  // tab left open since yesterday would keep showing the solved puzzle.
  // Reload instead, so the brand always lands on today's game. Modified
  // clicks (new tab/window) are left to the browser.
  const handleBrandClick = (e) => {
    if (pathname !== '/' || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
    e.preventDefault()
    window.location.reload()
  }

  return (
    <header className="app-header">
      <NavLink to="/" className="app-header__brand" onClick={handleBrandClick}>
        WikiWhiz
      </NavLink>
      <nav className="app-header__nav">
        <NavLink to="/archive" className="app-header__link">
          Archive
        </NavLink>
        <NavLink to="/stats" className="app-header__link">
          Stats
        </NavLink>
        <NavLink to="/info" className="app-header__link">
          Info
        </NavLink>
        {isAdmin && (
          <NavLink to="/admin" className="app-header__link">
            Admin
          </NavLink>
        )}
      </nav>
      <LoginButton />
    </header>
  )
}
