import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

// Notifications are polled (no websockets, per v1 scope) every 45 seconds.
const POLL_MS = 45000

export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [unread, setUnread] = useState(0)
  const ref = useRef(null)
  const navigate = useNavigate()

  const load = async () => {
    try {
      const data = await api.get('/notifications')
      setItems(data.items)
      setUnread(data.unread_count)
    } catch {
      /* not logged in yet, ignore */
    }
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, POLL_MS)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    function onClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  const handleItemClick = async (n) => {
    await api.post(`/notifications/${n.id}/read`)
    setOpen(false)
    load()
    if (n.ticket_id) navigate(`/tickets/${n.ticket_id}`)
  }

  const markAllRead = async () => {
    await api.post('/notifications/read-all')
    load()
  }

  return (
    <div className="relative" ref={ref}>
      <button
        className="relative rounded-full p-2 hover:bg-slate-100"
        onClick={() => setOpen((o) => !o)}
        aria-label="Notifications"
      >
        <BellIcon />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-bold text-white">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-2 w-80 max-h-96 overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg">
          <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2">
            <span className="text-sm font-semibold">Notifications</span>
            <button className="text-xs text-brand-600 hover:underline" onClick={markAllRead}>
              Mark all read
            </button>
          </div>
          {items.length === 0 && (
            <div className="px-3 py-6 text-center text-sm text-slate-400">No notifications yet</div>
          )}
          {items.map((n) => (
            <button
              key={n.id}
              onClick={() => handleItemClick(n)}
              className={`block w-full border-b border-slate-50 px-3 py-2 text-left text-sm hover:bg-slate-50 ${
                n.is_read ? 'text-slate-500' : 'font-medium text-slate-800'
              }`}
            >
              <div>{n.message}</div>
              <div className="text-[11px] text-slate-400">{new Date(n.created_at + 'Z').toLocaleString()}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function BellIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5 text-slate-600">
      <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0" />
    </svg>
  )
}
