import { NavLink } from 'react-router-dom'
import LoginButton from './LoginButton'
import { useAuthStore } from '../../state/authStore'

export default function Header() {
  const isAdmin = useAuthStore((s) => s.isAdmin)

  return (
    <header className="app-header">
      <NavLink to="/" className="app-header__brand">
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
