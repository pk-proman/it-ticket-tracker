import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../context/AuthContext.jsx'
import promanLogo from '../assets/proman-logo.png'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(searchParams.get('sso_error')?.replace(/\+/g, ' ') || '')
  const [busy, setBusy] = useState(false)
  const [ssoEnabled, setSsoEnabled] = useState(false)

  useEffect(() => {
    api.get('/auth/sso/status').then((s) => setSsoEnabled(s.enabled)).catch(() => setSsoEnabled(false))
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login(username, password)
      navigate('/')
    } catch (err) {
      setError(err.message || 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center">
          <img src={promanLogo} alt="Proman" className="mb-4 h-10 w-auto" />
          <h1 className="text-lg font-semibold text-slate-800">IT Support &amp; Maintenance Tracker</h1>
          <p className="text-sm text-slate-500">Sign in to continue</p>
        </div>

        {error && <div className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

        {ssoEnabled && (
          <div className="card mb-4 p-6">
            <a href="/api/auth/sso/login" className="btn-secondary w-full">
              <MicrosoftLogo />
              Sign in with Microsoft
            </a>
          </div>
        )}

        <div className="card space-y-4 p-6">
          {ssoEnabled && (
            <div className="flex items-center gap-3 text-xs text-slate-400">
              <div className="h-px flex-1 bg-slate-200" />
              or sign in with a local account
              <div className="h-px flex-1 bg-slate-200" />
            </div>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label" htmlFor="username">Username</label>
              <input
                id="username"
                className="input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
                required
              />
            </div>
            <div>
              <label className="label" htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                className="input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </div>
            <button type="submit" disabled={busy} className="btn-primary w-full">
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>

        <p className="mt-4 text-center text-xs text-slate-400">
          First run? Default admin is <code className="rounded bg-slate-200 px-1">admin / admin123</code> — change it after logging in.
        </p>
      </div>
    </div>
  )
}

function MicrosoftLogo() {
  return (
    <svg width="16" height="16" viewBox="0 0 21 21" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="1" y="1" width="9" height="9" fill="#f25022" />
      <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
      <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
      <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
    </svg>
  )
}
