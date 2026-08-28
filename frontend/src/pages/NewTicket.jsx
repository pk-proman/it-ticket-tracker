import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../context/AuthContext.jsx'

const PRIORITIES = ['Low', 'Medium', 'High', 'Critical']

export default function NewTicket() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [categories, setCategories] = useState([])
  const [form, setForm] = useState({
    title: '', description: '', category: '', priority: 'Medium',
    requester_name: '', requester_email: '', requester_department: '',
  })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.get('/settings/categories').then((c) => {
      setCategories(c)
      if (c.length) setForm((f) => ({ ...f, category: c[0].name }))
    })
  }, [])

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const ticket = await api.post('/tickets', form)
      navigate(`/tickets/${ticket.id}`)
    } catch (err) {
      setError(err.message || 'Could not create ticket')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-xl font-semibold text-slate-800">Raise a Ticket</h1>
      <form onSubmit={handleSubmit} className="card space-y-4 p-6">
        {error && <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

        <div>
          <label className="label">Title</label>
          <input className="input" required maxLength={300} value={form.title} onChange={set('title')} placeholder="Short summary of the issue" />
        </div>

        <div>
          <label className="label">Description</label>
          <textarea className="input" rows={5} value={form.description} onChange={set('description')} placeholder="What's happening? Steps to reproduce, error messages, etc." />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Category</label>
            <select className="input" value={form.category} onChange={set('category')} required>
              {categories.map((c) => <option key={c.id} value={c.name}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Priority</label>
            <select className="input" value={form.priority} onChange={set('priority')}>
              {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
        </div>

        {user?.role === 'agent' && (
          <div className="space-y-3 rounded-md border border-dashed border-slate-300 p-3">
            <p className="text-xs font-medium text-slate-500">Raising on behalf of someone (walk-up / phone request). Leave blank to raise as yourself.</p>
            <div className="grid grid-cols-2 gap-3">
              <input className="input" placeholder="Requester name" value={form.requester_name} onChange={set('requester_name')} />
              <input className="input" type="email" placeholder="Requester email" value={form.requester_email} onChange={set('requester_email')} />
            </div>
            <input className="input" placeholder="Requester department" value={form.requester_department} onChange={set('requester_department')} />
          </div>
        )}

        <button type="submit" disabled={busy} className="btn-primary w-full">
          {busy ? 'Submitting…' : 'Submit Ticket'}
        </button>
      </form>
    </div>
  )
}
