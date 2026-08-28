import { useEffect, useState } from 'react'
import { api } from '../api'
import Modal from '../components/Modal.jsx'

const BLANK = { title: '', category: 'Other', body: '', tags: '' }

export default function KnowledgeBase() {
  const [items, setItems] = useState([])
  const [categories, setCategories] = useState([])
  const [q, setQ] = useState('')
  const [category, setCategory] = useState('')
  const [editing, setEditing] = useState(null)
  const [error, setError] = useState('')

  const load = () => {
    const params = new URLSearchParams()
    if (q) params.set('q', q)
    if (category) params.set('category', category)
    const s = params.toString()
    api.get(`/kb${s ? `?${s}` : ''}`).then(setItems)
  }

  useEffect(() => {
    api.get('/settings/categories').then((c) => setCategories(c.map((x) => x.name)))
  }, [])
  useEffect(() => { load() }, [q, category]) // eslint-disable-line react-hooks/exhaustive-deps

  const save = async (e) => {
    e.preventDefault()
    setError('')
    try {
      if (editing.id) await api.patch(`/kb/${editing.id}`, editing)
      else await api.post('/kb', editing)
      setEditing(null)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const remove = async (id) => {
    if (!confirm('Delete this article?')) return
    await api.del(`/kb/${id}`)
    load()
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold text-slate-800">Knowledge Base</h1>
        <button className="btn-primary" onClick={() => setEditing({ ...BLANK })}>New Article</button>
      </div>

      <div className="flex flex-wrap gap-3">
        <input className="input max-w-sm" placeholder="Search articles…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="input w-auto" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">All categories</option>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {items.map((a) => (
          <div key={a.id} className="card p-4">
            <div className="flex items-start justify-between gap-2">
              <h3 className="text-sm font-semibold text-slate-800">{a.title}</h3>
              <span className="badge bg-slate-100 text-slate-600 flex-shrink-0">{a.category}</span>
            </div>
            <p className="mt-2 whitespace-pre-wrap text-sm text-slate-600 line-clamp-6">{a.body}</p>
            {a.tags && <p className="mt-2 text-xs text-slate-400">Tags: {a.tags}</p>}
            <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
              <span>By {a.created_by} · updated {a.updated_at?.slice(0, 10)}</span>
              <div className="flex gap-3">
                <button className="text-brand-600 hover:underline" onClick={() => setEditing({ ...a })}>Edit</button>
                <button className="text-red-500 hover:underline" onClick={() => remove(a.id)}>Delete</button>
              </div>
            </div>
          </div>
        ))}
        {items.length === 0 && <div className="col-span-2 card p-8 text-center text-sm text-slate-400">No articles found.</div>}
      </div>

      {editing && (
        <Modal onClose={() => setEditing(null)} title={editing.id ? 'Edit Article' : 'New Article'}>
          <form onSubmit={save} className="space-y-3">
            {error && <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
            <div><label className="label">Title</label><input className="input" required value={editing.title} onChange={(e) => setEditing({ ...editing, title: e.target.value })} /></div>
            <div><label className="label">Category</label>
              <select className="input" value={editing.category} onChange={(e) => setEditing({ ...editing, category: e.target.value })}>
                {categories.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div><label className="label">Solution / Steps</label><textarea className="input" rows={6} required value={editing.body} onChange={(e) => setEditing({ ...editing, body: e.target.value })} /></div>
            <div><label className="label">Tags (comma-separated)</label><input className="input" value={editing.tags} onChange={(e) => setEditing({ ...editing, tags: e.target.value })} /></div>
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
