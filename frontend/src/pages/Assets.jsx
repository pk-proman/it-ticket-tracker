import { useEffect, useState } from 'react'
import { api } from '../api'
import Modal from '../components/Modal.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const TYPES = ['Laptop', 'Desktop', 'Server', 'Network Device', 'Printer', 'Other']
const STATUSES = ['In Use', 'Spare', 'Retired']

const BLANK = { asset_tag: '', type: 'Laptop', assigned_to: '', location: '', purchase_date: '', warranty_expiry: '', status: 'In Use', notes: '' }

export default function Assets() {
  const { user } = useAuth()
  const isAdmin = Boolean(user?.is_admin)
  const canEdit = user?.role === 'agent' // create/edit stays available to any agent, admin or not
  const [items, setItems] = useState([])
  const [q, setQ] = useState('')
  const [editing, setEditing] = useState(null) // null = closed, {} = new, {...} = editing
  const [error, setError] = useState('')

  const load = () => api.get(`/assets${q ? `?q=${encodeURIComponent(q)}` : ''}`).then(setItems)

  useEffect(() => { load() }, [q]) // eslint-disable-line react-hooks/exhaustive-deps

  const save = async (e) => {
    e.preventDefault()
    setError('')
    try {
      if (editing.id) await api.patch(`/assets/${editing.id}`, editing)
      else await api.post('/assets', editing)
      setEditing(null)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const remove = async (id) => {
    if (!confirm('Delete this asset? This cannot be undone.')) return
    await api.del(`/assets/${id}`)
    load()
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold text-slate-800">{isAdmin ? 'Assets' : 'My Assets'}</h1>
        {canEdit && <button className="btn-primary" onClick={() => setEditing({ ...BLANK })}>New Asset</button>}
      </div>

      <input className="input max-w-sm" placeholder="Search asset tag, type, location, assignee…" value={q} onChange={(e) => setQ(e.target.value)} />

      <div className="card overflow-x-auto">
        <table className="w-full min-w-[800px] text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-2">Tag</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Assigned To</th>
              <th className="px-3 py-2">Location</th>
              <th className="px-3 py-2">Warranty Expiry</th>
              <th className="px-3 py-2">Status</th>
              {canEdit && <th className="px-3 py-2"></th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {items.map((a) => (
              <tr key={a.id} className="hover:bg-slate-50">
                <td className="px-3 py-2 font-medium text-slate-700">{a.asset_tag}</td>
                <td className="px-3 py-2">{a.type}</td>
                <td className="px-3 py-2 text-slate-500">{a.assigned_to || '—'}</td>
                <td className="px-3 py-2 text-slate-500">{a.location || '—'}</td>
                <td className="px-3 py-2 text-slate-500">{a.warranty_expiry || '—'}</td>
                <td className="px-3 py-2"><span className="badge bg-slate-100 text-slate-700">{a.status}</span></td>
                {canEdit && (
                  <td className="px-3 py-2 text-right">
                    <button className="mr-3 text-xs text-brand-600 hover:underline" onClick={() => setEditing({ ...a })}>Edit</button>
                    {isAdmin && <button className="text-xs text-red-500 hover:underline" onClick={() => remove(a.id)}>Delete</button>}
                  </td>
                )}
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={7} className="px-3 py-8 text-center text-slate-400">No assets found.</td></tr>}
          </tbody>
        </table>
      </div>

      {editing && (
        <Modal onClose={() => setEditing(null)} title={editing.id ? 'Edit Asset' : 'New Asset'}>
          <form onSubmit={save} className="space-y-3">
            {error && <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
            <div className="grid grid-cols-2 gap-3">
              <div><label className="label">Asset Tag</label><input className="input" required value={editing.asset_tag} onChange={(e) => setEditing({ ...editing, asset_tag: e.target.value })} /></div>
              <div><label className="label">Type</label>
                <select className="input" value={editing.type} onChange={(e) => setEditing({ ...editing, type: e.target.value })}>
                  {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div><label className="label">Assigned To</label><input className="input" value={editing.assigned_to} onChange={(e) => setEditing({ ...editing, assigned_to: e.target.value })} /></div>
              <div><label className="label">Location</label><input className="input" value={editing.location} onChange={(e) => setEditing({ ...editing, location: e.target.value })} /></div>
              <div><label className="label">Purchase Date</label><input type="date" className="input" value={editing.purchase_date || ''} onChange={(e) => setEditing({ ...editing, purchase_date: e.target.value })} /></div>
              <div><label className="label">Warranty Expiry</label><input type="date" className="input" value={editing.warranty_expiry || ''} onChange={(e) => setEditing({ ...editing, warranty_expiry: e.target.value })} /></div>
              <div><label className="label">Status</label>
                <select className="input" value={editing.status} onChange={(e) => setEditing({ ...editing, status: e.target.value })}>
                  {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            </div>
            <div><label className="label">Notes</label><textarea className="input" rows={2} value={editing.notes} onChange={(e) => setEditing({ ...editing, notes: e.target.value })} /></div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" className="btn-secondary" onClick={() => setEditing(null)}>Cancel</button>
              <button type="submit" className="btn-primary">Save</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
