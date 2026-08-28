import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { api } from '../api'

const AuthContext = createContext(null)

// The API sends is_admin/active as SQLite integers (0/1), not real booleans.
// Coerce once here so `{user.is_admin && <jsx/>}` never renders a literal "0".
function normalizeUser(u) {
  if (!u) return u
  return { ...u, is_admin: Boolean(u.is_admin), active: Boolean(u.active) }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const me = await api.get('/auth/me')
      setUser(normalizeUser(me))
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const login = async (username, password) => {
    const u = await api.post('/auth/login', { username, password })
    const normalized = normalizeUser(u)
    setUser(normalized)
    return normalized
  }

  const logout = async () => {
    await api.post('/auth/logout')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
