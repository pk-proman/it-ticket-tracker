import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { PriorityBadge, SlaBadge, StatusBadge } from '../components/Badges.jsx'
import { useAuth } from '../context/AuthContext.jsx'

export default function MyTickets() {
  const { user } = useAuth()
  const isAgent = user?.role === 'agent'
  const [items, setItems] = useState(null)
  const [assets, setAssets] = useState(null)

  useEffect(() => {
    api.get('/tickets?page_size=200').then((d) => setItems(d.items))
    api.get('/assets').then(setAssets)
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-800">My Tickets</h1>
        <Link to="/new-ticket" className="btn-primary">Raise a Ticket</Link>
      </div>

      {items === null && <p className="text-sm text-slate-400">Loading…</p>}
      {items && items.length === 0 && (
        <div className="card p-8 text-center text-sm text-slate-400">
          {isAgent ? "No tickets raised by you or assigned to you yet." : "You haven't raised any tickets yet."}
          <div className="mt-3"><Link to="/new-ticket" className="btn-primary">Raise your first ticket</Link></div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {items?.map((t) => (
          <Link to={`/tickets/${t.id}`} key={t.id} className="card block p-4 hover:border-brand-300">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-slate-700">{t.ticket_number}</span>
              <div className="flex items-center gap-1.5">
                <StatusBadge status={t.status} />
                <SlaBadge overdue={t.sla_overdue} status={t.status} />
              </div>
            </div>
            <div className="mt-1 truncate text-sm text-slate-800">{t.title}</div>
            <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
              <span>{t.category}</span>
              <PriorityBadge priority={t.priority} />
            </div>
            <div className="mt-1 flex items-center justify-between text-xs text-slate-400">
              <span>Opened {t.created_at?.slice(0, 10)}</span>
              {isAgent && t.assignee_name && t.assignee_id !== user.id && <span>Assigned: {t.assignee_name}</span>}
              {isAgent && t.assignee_id === user.id && <span className="text-brand-600">Assigned to you</span>}
            </div>
          </Link>
        ))}
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold text-slate-800">My Assets</h2>
        {assets === null && <p className="text-sm text-slate-400">Loading…</p>}
        {assets && assets.length === 0 && (
          <div className="card p-6 text-center text-sm text-slate-400">No assets currently registered to you.</div>
        )}
        {assets && assets.length > 0 && (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {assets.map((a) => (
              <div key={a.id} className="card p-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-slate-700">{a.asset_tag}</span>
                  <span className="badge bg-slate-100 text-slate-700">{a.status}</span>
                </div>
                <div className="mt-1 text-sm text-slate-600">{a.type}</div>
                <div className="mt-2 text-xs text-slate-400">
                  {a.location || 'No location on file'}
                  {a.warranty_expiry && ` · warranty until ${a.warranty_expiry}`}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
