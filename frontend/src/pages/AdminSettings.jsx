import { useEffect, useState } from 'react'
import { api } from '../api'

const PRIORITIES = ['Critical', 'High', 'Medium', 'Low']

export default function AdminSettings() {
  const [categories, setCategories] = useState([])
  const [newCategory, setNewCategory] = useState('')
  const [sla, setSla] = useState({})
  const [error, setError] = useState('')

  const load = () => {
    api.get('/settings/categories').then(setCategories)
    api.get('/settings/sla').then((rows) => {
      const map = {}
      rows.forEach((r) => { map[r.priority] = r.hours })
      setSla(map)
    })
  }
  useEffect(() => { load() }, [])

  const addCategory = async (e) => {
    e.preventDefault()
    setError('')
    if (!newCategory.trim()) return
    try {
      await api.post('/settings/categories', { name: newCategory.trim() })
      setNewCategory('')
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const removeCategory = async (id) => {
    if (!confirm('Delete this category?')) return
    await api.del(`/settings/categories/${id}`)
    load()
  }

  const saveSla = async (priority) => {
    await api.put('/settings/sla', { priority, hours: Number(sla[priority]) })
    load()
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-800">Settings</h1>

      <div className="card p-5">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">SLA Rules (target resolution time, in hours, per priority)</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {PRIORITIES.map((p) => (
            <div key={p}>
              <label className="label">{p}</label>
              <div className="flex gap-1.5">
                <input
                  type="number"
                  min="1"
                  className="input"
                  value={sla[p] ?? ''}
                  onChange={(e) => setSla((s) => ({ ...s, [p]: e.target.value }))}
                />
                <button className="btn-secondary" onClick={() => saveSla(p)}>Save</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card p-5">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Categories</h2>
        {error && <div className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
        <ul className="mb-3 space-y-1 text-sm">
          {categories.map((c) => (
            <li key={c.id} className="flex items-center justify-between border-b border-slate-50 py-1.5">
              <span>{c.name}</span>
              <button className="text-xs text-red-500 hover:underline" onClick={() => removeCategory(c.id)}>Remove</button>
            </li>
          ))}
        </ul>
        <form onSubmit={addCategory} className="flex gap-2">
          <input className="input" placeholder="New category name" value={newCategory} onChange={(e) => setNewCategory(e.target.value)} />
          <button type="submit" className="btn-primary">Add</button>
        </form>
      </div>
    </div>
  )
}
