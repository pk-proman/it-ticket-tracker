import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './context/AuthContext.jsx'
import Layout from './components/Layout.jsx'

import Login from './pages/Login.jsx'
import Dashboard from './pages/Dashboard.jsx'
import TicketList from './pages/TicketList.jsx'
import TicketDetail from './pages/TicketDetail.jsx'
import NewTicket from './pages/NewTicket.jsx'
import MyTickets from './pages/MyTickets.jsx'
import Assets from './pages/Assets.jsx'
import Licenses from './pages/Licenses.jsx'
import KnowledgeBase from './pages/KnowledgeBase.jsx'
import Reports from './pages/Reports.jsx'
import AdminUsers from './pages/AdminUsers.jsx'
import AdminSettings from './pages/AdminSettings.jsx'

function Loading() {
  return (
    <div className="flex h-screen items-center justify-center text-slate-400 text-sm">Loading…</div>
  )
}

function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <Loading />
  if (!user) return <Navigate to="/login" replace />
  return children
}

function RequireAgent({ children }) {
  const { user } = useAuth()
  if (!user || user.role !== 'agent') return <Navigate to="/" replace />
  return children
}

function RequireAdmin({ children }) {
  const { user } = useAuth()
  if (!user || !user.is_admin) return <Navigate to="/" replace />
  return children
}

export default function App() {
  const { user, loading } = useAuth()
  if (loading) return <Loading />

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={user?.is_admin ? <Dashboard /> : <MyTickets />} />
        <Route path="new-ticket" element={<NewTicket />} />
        <Route
          path="tickets"
          element={
            <RequireAgent>
              <TicketList />
            </RequireAgent>
          }
        />
        <Route path="tickets/:id" element={<TicketDetail />} />
        {/* Assets: any authenticated user (admin sees all, everyone else sees
            only assets assigned to them -- enforced server-side). */}
        <Route path="assets" element={<Assets />} />
        <Route
          path="licenses"
          element={
            <RequireAdmin>
              <Licenses />
            </RequireAdmin>
          }
        />
        <Route
          path="kb"
          element={
            <RequireAgent>
              <KnowledgeBase />
            </RequireAgent>
          }
        />
        <Route
          path="reports"
          element={
            <RequireAdmin>
              <Reports />
            </RequireAdmin>
          }
        />
        <Route
          path="admin/users"
          element={
            <RequireAdmin>
              <AdminUsers />
            </RequireAdmin>
          }
        />
        <Route
          path="admin/settings"
          element={
            <RequireAdmin>
              <AdminSettings />
            </RequireAdmin>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
