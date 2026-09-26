import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import Modal from '../components/Modal.jsx'
import { useAuth } from '../context/AuthContext.jsx'

// Three user types, one selector -- Admin and Agent are both stored as
// role='agent' (is_admin true/false); Requester is its own role. Internally
// still the same two underlying fields the API expects, just never shown
// as two independently-toggleable controls in this form.
const BLANK = { username: '', password: '', full_name: '', email: '', userType: 'agent', department: '' }

function userTypeToFields(userType) {
  return {
    role: userType === 'requester' ? 'requester' : 'agent',
    is_admin: userType === 'admin',
  }
}

const CSV_TEMPLATE =
  'username,full_name,email,role,department,password,is_admin\n' +
  'jdoe,Jane Doe,jane.doe@example.com,requester,Production,,false\n'

export default function AdminUsers() {
  const { user: currentUser } = useAuth()
  const [items, setItems] = useState([])
  const [editing, setEditing] = useState(null)
  const [resetTarget, setResetTarget] = useState(null)
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(new Set())
  const [importResult, setImportResult] = useState(null)
  const [importing, setImporting] = useState(false)
  const fileInputRef = useRef(null)

  const load = () => api.get('/users').then(setItems)
  useEffect(() => { load() }, [])

  const createUser = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const { userType, ...rest } = editing
      await api.post('/users', { ...rest, ...userTypeToFields(userType) })
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

  const deleteOne = async (u) => {
    if (!confirm(`Delete ${u.full_name} (${u.username})? This cannot be undone.`)) return
    try {
      await api.del(`/users/${u.id}`)
      load()
    } catch (err) {
      alert(err.message)
    }
  }

  const toggleSelect = (id) => {
    setSelected((s) => {
      const next = new Set(s)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const deletableItems = items.filter((u) => u.id !== currentUser?.id)

  const toggleSelectAll = () => {
    if (selected.size === deletableItems.length) setSelected(new Set())
    else setSelected(new Set(deletableItems.map((u) => u.id)))
  }

  const deleteSelected = async () => {
    if (selected.size === 0) return
    if (!confirm(`Delete ${selected.size} selected user(s)? This cannot be undone.`)) return
    const failures = []
    for (const id of selected) {
      try {
        await api.del(`/users/${id}`)
      } catch (err) {
        const u = items.find((i) => i.id === id)
        failures.push(`${u?.full_name || id}: ${err.message}`)
      }
    }
    setSelected(new Set())
    load()
    if (failures.length) alert(`Some users couldn't be deleted:\n\n${failures.join('\n')}`)
  }

  const downloadTemplate = () => {
    const blob = new Blob([CSV_TEMPLATE], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'users_import_template.csv'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  const handleImportFile = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setImporting(true)
    setError('')
    const fd = new FormData()
    fd.append('file', file)
    try {
      const result = await api.upload('/users/import', fd)
      setImportResult(result)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setImporting(false)
      e.target.value = ''
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold text-slate-800">Users</h1>
        <div className="flex flex-wrap gap-2">
          <button className="btn-secondary" onClick={downloadTemplate}>Download CSV Template</button>
          <button className="btn-secondary" disabled={importing} onClick={() => fileInputRef.current?.click()}>
            {importing ? 'Importing…' : 'Import CSV'}
          </button>
          <input ref={fileInputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={handleImportFile} />
          <button className="btn-primary" onClick={() => setEditing({ ...BLANK })}>New User</button>
        </div>
      </div>

      {error && <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      {selected.size > 0 && (
        <div className="card flex items-center gap-3 p-3">
          <span className="text-sm text-slate-600">{selected.size} selected</span>
          <button className="btn-danger" onClick={deleteSelected}>Delete Selected</button>
        </div>
      )}

      <div className="card overflow-x-auto">
        <table className="w-full min-w-[900px] text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="w-8 px-3 py-2">
                <input
                  type="checkbox"
                  checked={selected.size > 0 && selected.size === deletableItems.length}
                  onChange={toggleSelectAll}
                />
              </th>
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
                <td className="px-3 py-2">
                  {u.id !== currentUser?.id && (
                    <input type="checkbox" checked={selected.has(u.id)} onChange={() => toggleSelect(u.id)} />
                  )}
                </td>
                <td className="px-3 py-2 font-medium text-slate-700">
                  {u.full_name}
                  {u.id === currentUser?.id && <span className="ml-1.5 text-xs text-slate-400">(you)</span>}
                </td>
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
                <td className="px-3 py-2 text-right whitespace-nowrap">
                  <button className="mr-3 text-xs text-brand-600 hover:underline" onClick={() => setResetTarget(u)}>Reset Password</button>
                  {u.id !== currentUser?.id && (
                    <button className="text-xs text-red-500 hover:underline" onClick={() => deleteOne(u)}>Delete</button>
                  )}
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
              <div><label className="label">User Type</label>
                <select className="input" value={editing.userType} onChange={(e) => setEditing({ ...editing, userType: e.target.value })}>
                  <option value="admin">Admin — full access, manages users/categories/SLA</option>
                  <option value="agent">Agent — works tickets, no admin access</option>
                  <option value="requester">Requester — raises and tracks their own tickets</option>
                </select>
              </div>
              <div><label className="label">Department</label><input className="input" value={editing.department} onChange={(e) => setEditing({ ...editing, department: e.target.value })} /></div>
            </div>
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

      {importResult && (
        <Modal onClose={() => setImportResult(null)} title="Import Results">
          <div className="max-h-[60vh] space-y-4 overflow-y-auto text-sm">
            <p className="text-slate-600">
              {importResult.created.length} created, {importResult.skipped.length} skipped, {importResult.errors.length} errors.
            </p>

            {importResult.created.length > 0 && (
              <div>
                <h3 className="mb-1 font-semibold text-emerald-700">Created</h3>
                <ul className="space-y-1">
                  {importResult.created.map((c) => (
                    <li key={c.row} className="rounded bg-emerald-50 px-2 py-1">
                      <span className="font-medium">{c.username}</span> ({c.full_name}, {c.role})
                      {c.temp_password && (
                        <span className="ml-2 text-xs text-slate-500">
                          temp password: <code className="rounded bg-white px-1">{c.temp_password}</code>
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
                <p className="mt-1 text-xs text-amber-700">
                  Copy any temp passwords now — they're shown once and not stored anywhere retrievable.
                </p>
              </div>
            )}

            {importResult.skipped.length > 0 && (
              <div>
                <h3 className="mb-1 font-semibold text-slate-600">Skipped</h3>
                <ul className="space-y-1">
                  {importResult.skipped.map((s) => (
                    <li key={s.row} className="rounded bg-slate-50 px-2 py-1">Row {s.row} ({s.username}): {s.reason}</li>
                  ))}
                </ul>
              </div>
            )}

            {importResult.errors.length > 0 && (
              <div>
                <h3 className="mb-1 font-semibold text-red-700">Errors</h3>
                <ul className="space-y-1">
                  {importResult.errors.map((e) => (
                    <li key={e.row} className="rounded bg-red-50 px-2 py-1">Row {e.row} ({e.username || '—'}): {e.reason}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <button className="btn-primary" onClick={() => setImportResult(null)}>Done</button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
