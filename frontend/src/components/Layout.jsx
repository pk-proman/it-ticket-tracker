import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import NotificationBell from './NotificationBell.jsx'
import promanMark from '../assets/proman-mark-square.png'

const adminLinks = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/tickets', label: 'Tickets' },
  { to: '/assets', label: 'Assets' },
  { to: '/licenses', label: 'Licenses' },
  { to: '/kb', label: 'Knowledge Base' },
  { to: '/reports', label: 'Reports' },
]

const nonAdminAgentLinks = [
  { to: '/', label: 'My Tickets', end: true },
  { to: '/tickets', label: 'Ticket Search' },
  { to: '/assets', label: 'My Assets' },
  { to: '/kb', label: 'Knowledge Base' },
]

const requesterLinks = [
  { to: '/', label: 'My Tickets', end: true },
  { to: '/new-ticket', label: 'Raise a Ticket' },
  { to: '/assets', label: 'My Assets' },
]

const adminOnlyLinks = [{ to: '/admin/users', label: 'Users' }, { to: '/admin/settings', label: 'Settings' }]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  if (!user) return null

  const links = user.is_admin ? adminLinks : user.role === 'agent' ? nonAdminAgentLinks : requesterLinks

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="hidden w-56 flex-shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
        <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-3">
          <img src={promanMark} alt="Proman" className="h-9 w-9 flex-shrink-0" />
          <span className="text-xs font-semibold leading-tight text-slate-600">IT Support &amp; Maintenance Tracker</span>
        </div>
        <nav className="flex-1 space-y-0.5 px-2 py-3">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={({ isActive }) =>
                `block rounded-md px-3 py-2 text-sm font-medium ${
                  isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'
                }`
              }
            >
              {l.label}
            </NavLink>
          ))}
          {Boolean(user.is_admin) && (
            <>
              <div className="mt-4 px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Admin
              </div>
              {adminOnlyLinks.map((l) => (
                <NavLink
                  key={l.to}
                  to={l.to}
                  className={({ isActive }) =>
                    `block rounded-md px-3 py-2 text-sm font-medium ${
                      isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'
                    }`
                  }
                >
                  {l.label}
                </NavLink>
              ))}
            </>
          )}
        </nav>
        <div className="border-t border-slate-100 p-3">
          <div className="text-sm font-medium text-slate-700">{user.full_name}</div>
          <div className="text-xs text-slate-400">{user.role === 'agent' ? (user.is_admin ? 'Admin / Agent' : 'Agent') : 'Requester'}</div>
          <button onClick={handleLogout} className="btn-secondary mt-2 w-full text-xs">
            Log out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 flex-shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4 md:px-6">
          <MobileNav links={links} isAdmin={user.is_admin} />
          <div className="flex-1" />
          <NotificationBell />
        </header>
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function MobileNav({ links, isAdmin }) {
  return (
    <details className="md:hidden">
      <summary className="cursor-pointer select-none rounded-md border border-slate-200 px-3 py-1.5 text-sm">Menu</summary>
      <div className="absolute left-0 top-14 z-30 w-56 border-r border-b border-slate-200 bg-white p-2 shadow-lg">
        {links.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.end} className="block rounded-md px-3 py-2 text-sm text-slate-600 hover:bg-slate-100">
            {l.label}
          </NavLink>
        ))}
        {Boolean(isAdmin) && (
          <>
            <NavLink to="/admin/users" className="block rounded-md px-3 py-2 text-sm text-slate-600 hover:bg-slate-100">Users</NavLink>
            <NavLink to="/admin/settings" className="block rounded-md px-3 py-2 text-sm text-slate-600 hover:bg-slate-100">Settings</NavLink>
          </>
        )}
      </div>
    </details>
  )
}
