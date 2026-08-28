import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { PriorityBadge, SlaBadge, StatusBadge } from '../components/Badges.jsx'

function StatCard({ label, value, tone = 'text-slate-800', to }) {
  const content = (
    <div className="card p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${tone}`}>{value}</div>
    </div>
  )
  return to ? <Link to={to}>{content}</Link> : content
}

function combineSeries(created, resolved) {
  const map = {}
  created.forEach((c) => {
    map[c.day] = { day: c.day, created: c.count, resolved: 0 }
  })
  resolved.forEach((r) => {
    if (!map[r.day]) map[r.day] = { day: r.day, created: 0, resolved: 0 }
    map[r.day].resolved = r.count
  })
  return Object.values(map).sort((a, b) => (a.day < b.day ? -1 : 1))
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/dashboard').then(setData).catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="text-sm text-red-600">{error}</div>
  if (!data) return <div className="text-sm text-slate-400">Loading dashboard…</div>

  const series = combineSeries(data.created_series, data.resolved_series)
  const priorityChart = data.by_priority.map((p) => ({ name: p.priority, count: p.count }))

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-800">Dashboard</h1>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Open tickets" value={data.open_total} to="/tickets" />
        <StatCard label="Overdue (SLA)" value={data.overdue_count} tone="text-red-600" to="/tickets?overdue=1" />
        <StatCard label="Assigned to me" value={data.assigned_to_me.length} to="/tickets?mine=1" />
        <StatCard label="Licenses expiring soon" value={data.licenses_expiring.length} to="/licenses" />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Open tickets by priority</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={priorityChart}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#3a63f7" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Created vs. resolved (last 30 days)</h2>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={series}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="day" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Line type="monotone" dataKey="created" stroke="#3a63f7" strokeWidth={2} dot={false} name="Created" />
              <Line type="monotone" dataKey="resolved" stroke="#10b981" strokeWidth={2} dot={false} name="Resolved" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Overdue tickets</h2>
          {data.overdue_tickets.length === 0 && <p className="text-sm text-slate-400">Nothing overdue. 🎉</p>}
          <ul className="divide-y divide-slate-100">
            {data.overdue_tickets.map((t) => (
              <li key={t.id} className="py-2">
                <Link to={`/tickets/${t.id}`} className="flex items-center justify-between gap-2 text-sm hover:text-brand-700">
                  <span className="truncate">
                    <span className="font-medium text-slate-700">{t.ticket_number}</span> — {t.title}
                  </span>
                  <PriorityBadge priority={t.priority} />
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <div className="card p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Assigned to me</h2>
          {data.assigned_to_me.length === 0 && <p className="text-sm text-slate-400">Nothing on your plate right now.</p>}
          <ul className="divide-y divide-slate-100">
            {data.assigned_to_me.map((t) => (
              <li key={t.id} className="py-2">
                <Link to={`/tickets/${t.id}`} className="flex items-center justify-between gap-2 text-sm hover:text-brand-700">
                  <span className="truncate">
                    <span className="font-medium text-slate-700">{t.ticket_number}</span> — {t.title}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <StatusBadge status={t.status} />
                    <SlaBadge overdue={t.sla_overdue} status={t.status} />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Licenses expiring within 90 days</h2>
          {data.licenses_expiring.length === 0 && <p className="text-sm text-slate-400">Nothing expiring soon.</p>}
          <ul className="divide-y divide-slate-100 text-sm">
            {data.licenses_expiring.map((l) => (
              <li key={l.id} className="flex justify-between py-2">
                <span>{l.software_name}</span>
                <span className="text-slate-500">{l.renewal_date}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="card p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Assets due for warranty renewal</h2>
          {data.assets_expiring.length === 0 && <p className="text-sm text-slate-400">Nothing due soon.</p>}
          <ul className="divide-y divide-slate-100 text-sm">
            {data.assets_expiring.map((a) => (
              <li key={a.id} className="flex justify-between py-2">
                <span>{a.asset_tag} ({a.type})</span>
                <span className="text-slate-500">{a.warranty_expiry}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
