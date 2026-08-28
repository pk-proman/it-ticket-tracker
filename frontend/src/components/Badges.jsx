const PRIORITY_STYLES = {
  Low: 'bg-slate-100 text-slate-700',
  Medium: 'bg-sky-100 text-sky-700',
  High: 'bg-amber-100 text-amber-800',
  Critical: 'bg-red-100 text-red-700',
}

const STATUS_STYLES = {
  Open: 'bg-blue-100 text-blue-700',
  'In Progress': 'bg-indigo-100 text-indigo-700',
  'Waiting on User': 'bg-amber-100 text-amber-800',
  'Waiting on Vendor': 'bg-orange-100 text-orange-800',
  Resolved: 'bg-emerald-100 text-emerald-700',
  Closed: 'bg-slate-200 text-slate-600',
}

export function PriorityBadge({ priority }) {
  return (
    <span className={`badge ${PRIORITY_STYLES[priority] || 'bg-slate-100 text-slate-700'}`}>
      {priority}
    </span>
  )
}

export function StatusBadge({ status }) {
  return (
    <span className={`badge ${STATUS_STYLES[status] || 'bg-slate-100 text-slate-700'}`}>
      {status}
    </span>
  )
}

export function SlaBadge({ overdue, status }) {
  if (status === 'Resolved' || status === 'Closed') return null
  if (overdue) {
    return <span className="badge bg-red-100 text-red-700">SLA overdue</span>
  }
  return <span className="badge bg-emerald-50 text-emerald-700">Within SLA</span>
}
