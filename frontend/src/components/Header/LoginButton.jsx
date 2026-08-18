import { useAuthStore } from '../../state/authStore'

export default function LoginButton() {
  const { authenticated, username, login, logout } = useAuthStore()

  if (!authenticated) {
    return (
      <button type="button" className="login-button" onClick={login}>
        Log in with Wikimedia
      </button>
    )
  }

  return (
    <div className="login-button login-button--authed">
      <span className="login-button__username">{username}</span>
      <button type="button" className="login-button__logout" onClick={logout}>
        Log out
      </button>
    </div>
  )
}
