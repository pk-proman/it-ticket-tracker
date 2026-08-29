import { useEffect, useState } from 'react'
import { api } from '../api'
import Modal from '../components/Modal.jsx'

const BLANK = { username: '', password: '', full_name: '', email: '', role: 'agent', is_admin: false, department: '' }

export default function AdminUsers() {
  const [items, setItems] = useState([])
  const [editing, setEditing] = useState(null)
  const [resetTarget, setResetTarget] = useState(null)
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState('')

  const load = () => api.get('/users').then(setItems)
  useEffect(() => { load() }, [])

  const createUser = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await api.post('/users', editing)
      setEditing(null)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const toggleActive = async (u) => {
    await api.patch(`/users/${u.id}`, { active: !u.active })
    load()
  }

  const toggleAdmin = async (u) => {
    await api.patch(`/users/${u.id}`, { is_admin: !u.is_admin })
    load()
  }

  const doResetPassword = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await api.post(`/users/${resetTarget.id}/reset-password`, { new_password: newPassword })
      setResetTarget(null)
      setNewPassword('')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold text-slate-800">Users</h1>
        <button className="btn-primary" onClick={() => setEditing({ ...BLANK })}>New User</button>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full min-w-[800px] text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Username</th>
              <th className="px-3 py-2">Email</th>
              <th className="px-3 py-2">Role</th>
              <th className="px-3 py-2">Sign-in</th>
              <th className="px-3 py-2">Admin</th>
              <th className="px-3 py-2">Active</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {items.map((u) => (
              <tr key={u.id} className="hover:bg-slate-50">
                <td className="px-3 py-2 font-medium text-slate-700">{u.full_name}</td>
                <td className="px-3 py-2 text-slate-500">{u.username}</td>
                <td className="px-3 py-2 text-slate-500">{u.email}</td>
                <td className="px-3 py-2 capitalize text-slate-500">{u.role}</td>
                <td className="px-3 py-2 text-slate-500">{u.auth_provider === 'microsoft' ? 'Microsoft' : 'Local'}</td>
                <td className="px-3 py-2">
                  <button className="text-xs" onClick={() => toggleAdmin(u)}>{u.is_admin ? '✅' : '—'}</button>
                </td>
                <td className="px-3 py-2">
                  <button className={`badge ${u.active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-500'}`} onClick={() => toggleActive(u)}>
                    {u.active ? 'Active' : 'Disabled'}
                  </button>
                </td>
                <td className="px-3 py-2 text-right">
                  <button className="text-xs text-brand-600 hover:underline" onClick={() => setResetTarget(u)}>Reset Password</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editing && (
        <Modal onClose={() => setEditing(null)} title="New User">
          <form onSubmit={createUser} className="space-y-3">
            {error && <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
            <div className="grid grid-cols-2 gap-3">
              <div><label className="label">Full Name</label><input className="input" required value={editing.full_name} onChange={(e) => setEditing({ ...editing, full_name: e.target.value })} /></div>
              <div><label className="label">Username</label><input className="input" required value={editing.username} onChange={(e) => setEditing({ ...editing, username: e.target.value })} /></div>
              <div><label className="label">Email</label><input type="email" className="input" required value={editing.email} onChange={(e) => setEditing({ ...editing, email: e.target.value })} /></div>
              <div><label className="label">Temporary Password</label><input type="text" className="input" required minLength={6} value={editing.password} onChange={(e) => setEditing({ ...editing, password: e.target.value })} /></div>
              <div><label className="label">Role</label>
                <select className="input" value={editing.role} onChange={(e) => setEditing({ ...editing, role: e.target.value })}>
                  <option value="agent">Agent</option>
                  <option value="requester">Requester</option>
                </select>
              </div>
              <div><label className="label">Department</label><input className="input" value={editing.department} onChange={(e) => setEditing({ ...editing, department: e.target.value })} /></div>
            </div>
            <label className="flex items-center gap-1.5 text-sm text-slate-600">
              <input type="checkbox" checked={editing.is_admin} onChange={(e) => setEditing({ ...editing, is_admin: e.target.checked })} />
              Grant admin (manage users, categories, SLA rules)
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" className="btn-secondary" onClick={() => setEditing(null)}>Cancel</button>
              <button type="submit" className="btn-primary">Create User</button>
            </div>
          </form>
        </Modal>
      )}

      {resetTarget && (
        <Modal onClose={() => setResetTarget(null)} title={`Reset Password: ${resetTarget.full_name}`}>
          <form onSubmit={doResetPassword} className="space-y-3">
            {error && <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
            <div><label className="label">New Password</label><input type="text" required minLength={6} className="input" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} /></div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" className="btn-secondary" onClick={() => setResetTarget(null)}>Cancel</button>
              <button type="submit" className="btn-primary">Reset Password</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
