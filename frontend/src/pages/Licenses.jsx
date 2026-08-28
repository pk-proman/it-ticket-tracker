import { useEffect, useState } from 'react'
import { api } from '../api'
import Modal from '../components/Modal.jsx'

const BLANK = { software_name: '', vendor: '', license_key: '', total_seats: 1, seats_in_use: 0, renewal_date: '', cost: 0, owner: '' }

function expiryTone(dateStr) {
  if (!dateStr) return ''
  const days = (new Date(dateStr) - new Date()) / (1000 * 60 * 60 * 24)
  if (days < 0) return 'text-red-600 font-medium'
  if (days <= 30) return 'text-red-600'
  if (days <= 60) return 'text-amber-600'
  if (days <= 90) return 'text-amber-500'
  return 'text-slate-500'
}

export default function Licenses() {
  const [items, setItems] = useState([])
  const [q, setQ] = useState('')
  const [editing, setEditing] = useState(null)
  const [error, setError] = useState('')

  const load = () => api.get(`/licenses${q ? `?q=${encodeURIComponent(q)}` : ''}`).then(setItems)

  useEffect(() => { load() }, [q]) // eslint-disable-line react-hooks/exhaustive-deps

  const save = async (e) => {
    e.preventDefault()
    setError('')
    try {
      if (editing.id) await api.patch(`/licenses/${editing.id}`, editing)
      else await api.post('/licenses', editing)
      setEditing(null)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const remove = async (id) => {
    if (!confirm('Delete this license? This cannot be undone.')) return
    await api.del(`/licenses/${id}`)
    load()
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold text-slate-800">Licenses</h1>
        <button className="btn-primary" onClick={() => setEditing({ ...BLANK })}>New License</button>
      </div>

      <input className="input max-w-sm" placeholder="Search software, vendor…" value={q} onChange={(e) => setQ(e.target.value)} />

      <div className="card overflow-x-auto">
        <table className="w-full min-w-[850px] text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-2">Software</th>
              <th className="px-3 py-2">Vendor</th>
              <th className="px-3 py-2">Seats</th>
              <th className="px-3 py-2">Renewal</th>
              <th className="px-3 py-2">Cost</th>
              <th className="px-3 py-2">Owner</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {items.map((l) => (
              <tr key={l.id} className="hover:bg-slate-50">
                <td className="px-3 py-2 font-medium text-slate-700">{l.software_name}</td>
                <td className="px-3 py-2 text-slate-500">{l.vendor || '—'}</td>
                <td className="px-3 py-2 text-slate-500">{l.seats_in_use}/{l.total_seats}</td>
                <td className={`px-3 py-2 ${expiryTone(l.renewal_date)}`}>{l.renewal_date || '—'}</td>
                <td className="px-3 py-2 text-slate-500">{l.cost ? `$${Number(l.cost).toLocaleString()}` : '—'}</td>
                <td className="px-3 py-2 text-slate-500">{l.owner || '—'}</td>
                <td className="px-3 py-2 text-right">
                  <button className="mr-3 text-xs text-brand-600 hover:underline" onClick={() => setEditing({ ...l })}>Edit</button>
                  <button className="text-xs text-red-500 hover:underline" onClick={() => remove(l.id)}>Delete</button>
                </td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={7} className="px-3 py-8 text-center text-slate-400">No licenses found.</td></tr>}
          </tbody>
        </table>
      </div>

      {editing && (
        <Modal onClose={() => setEditing(null)} title={editing.id ? 'Edit License' : 'New License'}>
          <form onSubmit={save} className="space-y-3">
            {error && <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
            <div><label className="label">Software Name</label><input className="input" required value={editing.software_name} onChange={(e) => setEditing({ ...editing, software_name: e.target.value })} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="label">Vendor</label><input className="input" value={editing.vendor} onChange={(e) => setEditing({ ...editing, vendor: e.target.value })} /></div>
              <div><label className="label">License Key</label><input className="input" value={editing.license_key} onChange={(e) => setEditing({ ...editing, license_key: e.target.value })} /></div>
              <div><label className="label">Total Seats</label><input type="number" min="0" className="input" value={editing.total_seats} onChange={(e) => setEditing({ ...editing, total_seats: Number(e.target.value) })} /></div>
              <div><label className="label">Seats In Use</label><input type="number" min="0" className="input" value={editing.seats_in_use} onChange={(e) => setEditing({ ...editing, seats_in_use: Number(e.target.value) })} /></div>
              <div><label className="label">Renewal Date</label><input type="date" className="input" value={editing.renewal_date || ''} onChange={(e) => setEditing({ ...editing, renewal_date: e.target.value })} /></div>
              <div><label className="label">Cost ($/yr)</label><input type="number" step="0.01" min="0" className="input" value={editing.cost} onChange={(e) => setEditing({ ...editing, cost: Number(e.target.value) })} /></div>
            </div>
            <div><label className="label">Owner</label><input className="input" value={editing.owner} onChange={(e) => setEditing({ ...editing, owner: e.target.value })} /></div>
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
