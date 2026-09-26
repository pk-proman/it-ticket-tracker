import { useEffect, useState } from 'react'
import { api } from '../api'

const PRIORITIES = ['Critical', 'High', 'Medium', 'Low']

export default function AdminSettings() {
  const [categories, setCategories] = useState([])
  const [agents, setAgents] = useState([])
  const [newCategory, setNewCategory] = useState('')
  const [sla, setSla] = useState({})
  const [configs, setConfigs] = useState({}) // categoryId -> {default_assignee_id, requires_approval, approver_id}
  const [error, setError] = useState('')
  const [savedId, setSavedId] = useState(null)

  const load = () => {
    api.get('/settings/categories').then((rows) => {
      setCategories(rows)
      const next = {}
      rows.forEach((c) => {
        next[c.id] = {
          default_assignee_id: c.default_assignee_id ?? '',
          requires_approval: Boolean(c.requires_approval),
          approver_id: c.approver_id ?? '',
        }
      })
      setConfigs(next)
    })
    api.get('/settings/sla').then((rows) => {
      const map = {}
      rows.forEach((r) => { map[r.priority] = r.hours })
      setSla(map)
    })
    api.get('/users/agents').then(setAgents)
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

  const setConfig = (id, patch) => setConfigs((c) => ({ ...c, [id]: { ...c[id], ...patch } }))

  const saveConfig = async (id) => {
    setError('')
    const cfg = configs[id]
    try {
      await api.patch(`/settings/categories/${id}`, {
        default_assignee_id: cfg.default_assignee_id ? Number(cfg.default_assignee_id) : null,
        requires_approval: cfg.requires_approval,
        approver_id: cfg.approver_id ? Number(cfg.approver_id) : null,
      })
      setSavedId(id)
      setTimeout(() => setSavedId(null), 1500)
      load()
    } catch (err) {
      setError(err.message)
    }
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
        <h2 className="text-sm font-semibold text-slate-700">Categories &amp; ticket routing</h2>
        <p className="mb-3 text-xs text-slate-400">
          Optionally set a default assignee per category, applied the moment a ticket is raised. Turn on
          "Requires approval" to route it to an approver first instead — it stays unassigned until they
          approve (via a link in their email, no login needed) or reject it.
        </p>
        {error && <div className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

        <div className="space-y-3">
          {categories.map((c) => {
            const cfg = configs[c.id] || {}
            return (
              <div key={c.id} className="rounded-md border border-slate-200 p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-800">{c.name}</span>
                  <button className="text-xs text-red-500 hover:underline" onClick={() => removeCategory(c.id)}>Remove</button>
                </div>
                <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <div>
                    <label className="label">Default assignee</label>
                    <select
                      className="input"
                      value={cfg.default_assignee_id || ''}
                      onChange={(e) => setConfig(c.id, { default_assignee_id: e.target.value })}
                    >
                      <option value="">None</option>
                      {agents.map((a) => <option key={a.id} value={a.id}>{a.full_name}</option>)}
                    </select>
                  </div>
                  <label className="flex items-center gap-1.5 pt-5 text-sm text-slate-600">
                    <input
                      type="checkbox"
                      checked={cfg.requires_approval || false}
                      onChange={(e) => setConfig(c.id, { requires_approval: e.target.checked })}
                    />
                    Requires approval
                  </label>
                  {cfg.requires_approval && (
                    <div>
                      <label className="label">Approver</label>
                      <select
                        className="input"
                        value={cfg.approver_id || ''}
                        onChange={(e) => setConfig(c.id, { approver_id: e.target.value })}
                      >
                        <option value="">Select an approver…</option>
                        {agents.map((a) => <option key={a.id} value={a.id}>{a.full_name}</option>)}
                      </select>
                    </div>
                  )}
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <button className="btn-secondary text-xs" onClick={() => saveConfig(c.id)}>Save</button>
                  {savedId === c.id && <span className="text-xs text-emerald-600">Saved</span>}
                </div>
              </div>
            )
          })}
        </div>

        <form onSubmit={addCategory} className="mt-4 flex gap-2">
          <input className="input" placeholder="New category name" value={newCategory} onChange={(e) => setNewCategory(e.target.value)} />
          <button type="submit" className="btn-primary">Add</button>
        </form>
      </div>
    </div>
  )
}
