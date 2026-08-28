import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

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
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-lg bg-brand-600 text-lg font-bold text-white">
            IT
          </div>
          <h1 className="text-lg font-semibold text-slate-800">IT Support Ticket Tracker</h1>
          <p className="text-sm text-slate-500">Sign in to continue</p>
        </div>
        <form onSubmit={handleSubmit} className="card space-y-4 p-6">
          {error && <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
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
        <p className="mt-4 text-center text-xs text-slate-400">
          First run? Default admin is <code className="rounded bg-slate-200 px-1">admin / admin123</code> — change it after logging in.
        </p>
      </div>
    </div>
  )
}
