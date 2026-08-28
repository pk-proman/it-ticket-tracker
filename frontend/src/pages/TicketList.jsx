import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, qs, API_BASE } from '../api'
import { PriorityBadge, SlaBadge, StatusBadge } from '../components/Badges.jsx'

const STATUSES = ['Open', 'In Progress', 'Waiting on User', 'Waiting on Vendor', 'Resolved', 'Closed']
const PRIORITIES = ['Low', 'Medium', 'High', 'Critical']

export default function TicketList() {
  const [searchParams] = useSearchParams()
  const [filters, setFilters] = useState({
    status: '', priority: '', category: '', assignee_id: '', date_from: '', date_to: '', q: '',
    mine: searchParams.get('mine') === '1',
  })
  const overdueOnly = searchParams.get('overdue') === '1'
  const [result, setResult] = useState({ items: [], total: 0 })
  const [categories, setCategories] = useState([])
  const [agents, setAgents] = useState([])
  const [selected, setSelected] = useState(new Set())
  const [sort, setSort] = useState({ col: 'created_at', dir: 'desc' })
  const [loading, setLoading] = useState(false)
  const [bulkAssignee, setBulkAssignee] = useState('')
  const [bulkStatus, setBulkStatus] = useState('')

  useEffect(() => {
    api.get('/settings/categories').then((c) => setCategories(c.map((x) => x.name)))
    api.get('/users/agents').then(setAgents)
  }, [])

  const load = () => {
    setLoading(true)
    const params = { ...filters, sort: sort.col, direction: sort.dir, page_size: 200 }
    api
      .get(`/tickets${qs(params)}`)
      .then((data) => {
        let items = data.items
        if (overdueOnly) items = items.filter((t) => t.sla_overdue)
        setResult({ ...data, items })
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, sort])

  const toggleSelect = (id) => {
    setSelected((s) => {
      const next = new Set(s)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selected.size === result.items.length) setSelected(new Set())
    else setSelected(new Set(result.items.map((t) => t.id)))
  }

  const applySort = (col) => {
    setSort((s) => ({ col, dir: s.col === col && s.dir === 'asc' ? 'desc' : 'asc' }))
  }

  const runBulk = async () => {
    if (selected.size === 0) return
    const payload = { ticket_ids: [...selected] }
    if (bulkStatus) payload.status = bulkStatus
    if (bulkAssignee) payload.assignee_id = Number(bulkAssignee)
    if (!payload.status && !payload.assignee_id) return
    await api.post('/tickets/bulk', payload)
    setSelected(new Set())
    setBulkStatus('')
    setBulkAssignee('')
    load()
  }

  const exportUrl = useMemo(() => `${API_BASE}/tickets/export.csv${qs(filters)}`, [filters])

  const clearFilters = () =>
    setFilters({ status: '', priority: '', category: '', assignee_id: '', date_from: '', date_to: '', q: '', mine: false })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold text-slate-800">Tickets</h1>
        <div className="flex gap-2">
          <a href={exportUrl} className="btn-secondary">Export CSV</a>
          <Link to="/new-ticket" className="btn-primary">New Ticket</Link>
        </div>
      </div>

      <div className="card grid grid-cols-2 gap-3 p-4 md:grid-cols-4 lg:grid-cols-7">
        <input
          className="input col-span-2 lg:col-span-2"
          placeholder="Search title, description, ticket #…"
          value={filters.q}
          onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))}
        />
        <select className="input" value={filters.status} onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}>
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className="input" value={filters.priority} onChange={(e) => setFilters((f) => ({ ...f, priority: e.target.value }))}>
          <option value="">All priorities</option>
          {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select className="input" value={filters.category} onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value }))}>
          <option value="">All categories</option>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select className="input" value={filters.assignee_id} onChange={(e) => setFilters((f) => ({ ...f, assignee_id: e.target.value }))}>
          <option value="">All assignees</option>
          {agents.map((a) => <option key={a.id} value={a.id}>{a.full_name}</option>)}
        </select>
        <div className="flex gap-1">
          <input type="date" className="input" value={filters.date_from} onChange={(e) => setFilters((f) => ({ ...f, date_from: e.target.value }))} />
          <input type="date" className="input" value={filters.date_to} onChange={(e) => setFilters((f) => ({ ...f, date_to: e.target.value }))} />
        </div>
        <div className="col-span-2 flex items-center gap-3 lg:col-span-7">
          <label className="flex items-center gap-1.5 text-sm text-slate-600">
            <input type="checkbox" checked={filters.mine} onChange={(e) => setFilters((f) => ({ ...f, mine: e.target.checked }))} />
            Assigned to me
          </label>
          <button className="text-xs text-brand-600 hover:underline" onClick={clearFilters}>Clear filters</button>
          {overdueOnly && <span className="badge bg-red-100 text-red-700">Filtering: overdue only</span>}
        </div>
      </div>

      {selected.size > 0 && (
        <div className="card flex flex-wrap items-center gap-2 p-3">
          <span className="text-sm text-slate-600">{selected.size} selected</span>
          <select className="input w-auto" value={bulkStatus} onChange={(e) => setBulkStatus(e.target.value)}>
            <option value="">Change status…</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <select className="input w-auto" value={bulkAssignee} onChange={(e) => setBulkAssignee(e.target.value)}>
            <option value="">Reassign…</option>
            {agents.map((a) => <option key={a.id} value={a.id}>{a.full_name}</option>)}
          </select>
          <button className="btn-primary" onClick={runBulk}>Apply</button>
        </div>
      )}

      <div className="card overflow-x-auto">
        <table className="w-full min-w-[900px] text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="w-8 px-3 py-2">
                <input type="checkbox" checked={selected.size > 0 && selected.size === result.items.length} onChange={toggleSelectAll} />
              </th>
              <Th label="Ticket #" col="ticket_number" sort={sort} onClick={applySort} />
              <th className="px-3 py-2">Title</th>
              <th className="px-3 py-2">Category</th>
              <Th label="Priority" col="priority" sort={sort} onClick={applySort} />
              <Th label="Status" col="status" sort={sort} onClick={applySort} />
              <th className="px-3 py-2">Assignee</th>
              <Th label="Created" col="created_at" sort={sort} onClick={applySort} />
              <th className="px-3 py-2">SLA</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {result.items.map((t) => (
              <tr key={t.id} className="hover:bg-slate-50">
                <td className="px-3 py-2">
                  <input type="checkbox" checked={selected.has(t.id)} onChange={() => toggleSelect(t.id)} />
                </td>
                <td className="whitespace-nowrap px-3 py-2 font-medium text-slate-700">
                  <Link to={`/tickets/${t.id}`} className="hover:text-brand-700">{t.ticket_number}</Link>
                </td>
                <td className="max-w-xs truncate px-3 py-2">
                  <Link to={`/tickets/${t.id}`} className="hover:text-brand-700">{t.title}</Link>
                </td>
                <td className="px-3 py-2 text-slate-500">{t.category}</td>
                <td className="px-3 py-2"><PriorityBadge priority={t.priority} /></td>
                <td className="px-3 py-2"><StatusBadge status={t.status} /></td>
                <td className="px-3 py-2 text-slate-500">{t.assignee_name || '—'}</td>
                <td className="whitespace-nowrap px-3 py-2 text-slate-500">{t.created_at?.slice(0, 10)}</td>
                <td className="px-3 py-2"><SlaBadge overdue={t.sla_overdue} status={t.status} /></td>
              </tr>
            ))}
            {!loading && result.items.length === 0 && (
              <tr><td colSpan={9} className="px-3 py-8 text-center text-slate-400">No tickets match these filters.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="text-xs text-slate-400">{result.total} total ticket(s)</div>
    </div>
  )
}

function Th({ label, col, sort, onClick }) {
  const active = sort.col === col
  return (
    <th className="cursor-pointer select-none px-3 py-2" onClick={() => onClick(col)}>
      {label} {active && (sort.dir === 'asc' ? '▲' : '▼')}
    </th>
  )
}
