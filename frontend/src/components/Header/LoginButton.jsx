import { useEffect, useRef, useState } from 'react'
import { useAuthStore } from '../../state/authStore'
import NotificationSettings from './NotificationSettings'
import ThemeToggle from './ThemeToggle'

export default function LoginButton() {
  const { authenticated, username, login, logout } = useAuthStore()
  const [menuOpen, setMenuOpen] = useState(false)
  const [notifOpen, setNotifOpen] = useState(false)
  const containerRef = useRef(null)

  useEffect(() => {
    if (!menuOpen) return undefined
    const handleClickOutside = (e) => {
      if (!containerRef.current?.contains(e.target)) setMenuOpen(false)
    }
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [menuOpen])

  if (!authenticated) {
    return (
      <div className="login-button-group">
        <ThemeToggle />
        <button type="button" className="login-button" onClick={login}>
          Log in<span className="login-button__full-text"> with Wikimedia</span>
        </button>
      </div>
    )
  }

  return (
    <div className="login-button login-button--authed" ref={containerRef}>
      <button
        type="button"
        className="login-button__username"
        onClick={() => setMenuOpen((open) => !open)}
        aria-expanded={menuOpen}
      >
        {username} ▾
      </button>
      {menuOpen && (
        <div className="login-button__menu">
          <ThemeToggle />
          <button
            type="button"
            className="login-button__menu-item"
            onClick={() => {
              setNotifOpen(true)
              setMenuOpen(false)
            }}
          >
            <span aria-hidden="true">🔔</span> Daily reminder
          </button>
          <button type="button" className="login-button__logout" onClick={logout}>
            Log out
          </button>
        </div>
      )}
      {/* Rendered outside the menu so closing the dropdown (including the
          click-outside handler above) doesn't tear the modal down with it. */}
      {notifOpen && <NotificationSettings onClose={() => setNotifOpen(false)} />}
    </div>
  )
}
