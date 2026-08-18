import { NavLink } from 'react-router-dom'
import LoginButton from './LoginButton'

export default function Header() {
  return (
    <header className="app-header">
      <NavLink to="/" className="app-header__brand">
        WikiWhiz
      </NavLink>
      <nav className="app-header__nav">
        <NavLink to="/stats" className="app-header__link">
          Stats
        </NavLink>
        <NavLink to="/info" className="app-header__link">
          Info
        </NavLink>
      </nav>
      <LoginButton />
    </header>
  )
}
