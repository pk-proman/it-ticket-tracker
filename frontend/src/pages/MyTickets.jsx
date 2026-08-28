import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { PriorityBadge, StatusBadge } from '../components/Badges.jsx'

export default function MyTickets() {
  const [items, setItems] = useState(null)

  const load = () => api.get('/tickets?page_size=200').then((d) => setItems(d.items))

  useEffect(() => {
    load()
  }, [])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-800">My Tickets</h1>
        <Link to="/new-ticket" className="btn-primary">Raise a Ticket</Link>
      </div>

      {items === null && <p className="text-sm text-slate-400">Loading…</p>}
      {items && items.length === 0 && (
        <div className="card p-8 text-center text-sm text-slate-400">
          You haven't raised any tickets yet.
          <div className="mt-3"><Link to="/new-ticket" className="btn-primary">Raise your first ticket</Link></div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {items?.map((t) => (
          <Link to={`/tickets/${t.id}`} key={t.id} className="card block p-4 hover:border-brand-300">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-slate-700">{t.ticket_number}</span>
              <StatusBadge status={t.status} />
            </div>
            <div className="mt-1 truncate text-sm text-slate-800">{t.title}</div>
            <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
              <span>{t.category}</span>
              <PriorityBadge priority={t.priority} />
            </div>
            <div className="mt-1 text-xs text-slate-400">Opened {t.created_at?.slice(0, 10)}</div>
          </Link>
        ))}
      </div>
    </div>
  )
}
