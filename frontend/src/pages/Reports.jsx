import { useEffect, useState } from 'react'
import { api, API_BASE } from '../api'

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

export default function Reports() {
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [report, setReport] = useState(null)

  useEffect(() => {
    api.get(`/reports/monthly?year=${year}&month=${month}`).then(setReport)
  }, [year, month])

  const exportUrl = `${API_BASE}/reports/monthly/export.csv?year=${year}&month=${month}`

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-800">Monthly Summary Report</h1>

      <div className="card flex flex-wrap items-end gap-3 p-4">
        <div>
          <label className="label">Month</label>
          <select className="input w-auto" value={month} onChange={(e) => setMonth(Number(e.target.value))}>
            {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Year</label>
          <input type="number" className="input w-24" value={year} onChange={(e) => setYear(Number(e.target.value))} />
        </div>
        <a href={exportUrl} className="btn-secondary">Export CSV</a>
      </div>

      {report && (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Stat label="Tickets Created" value={report.total_created} />
            <Stat label="Tickets Resolved" value={report.total_resolved} />
            <Stat label="Avg Resolution Time" value={`${report.avg_resolution_hours}h`} />
            <Stat label="SLA Compliance" value={report.sla_compliance_pct !== null ? `${report.sla_compliance_pct}%` : 'N/A'} />
          </div>

          <div className="card p-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-700">Tickets by Category</h2>
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-slate-400">
                <tr><th className="py-1">Category</th><th className="py-1 text-right">Tickets</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {report.by_category.map((c) => (
                  <tr key={c.category}><td className="py-1.5">{c.category}</td><td className="py-1.5 text-right">{c.count}</td></tr>
                ))}
                {report.by_category.length === 0 && (
                  <tr><td colSpan={2} className="py-4 text-center text-slate-400">No tickets created this period.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div className="card p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-800">{value}</div>
    </div>
  )
}
