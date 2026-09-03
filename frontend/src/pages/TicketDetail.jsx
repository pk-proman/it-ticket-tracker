import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, API_BASE } from '../api'
import { PriorityBadge, SlaBadge, StatusBadge } from '../components/Badges.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const STATUSES = ['Open', 'In Progress', 'Waiting on User', 'Waiting on Vendor', 'Resolved', 'Closed']
const PRIORITIES = ['Low', 'Medium', 'High', 'Critical']

export default function TicketDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const isAgent = user?.role === 'agent'
  const isAdmin = Boolean(user?.is_admin)

  const [ticket, setTicket] = useState(null)
  const [comments, setComments] = useState([])
  const [audit, setAudit] = useState([])
  const [attachments, setAttachments] = useState([])
  const [categories, setCategories] = useState([])
  const [agents, setAgents] = useState([])
  const [error, setError] = useState('')

  const [commentBody, setCommentBody] = useState('')
  const [isInternal, setIsInternal] = useState(false)
  const [posting, setPosting] = useState(false)
  const [uploading, setUploading] = useState(false)

  const [assetQuery, setAssetQuery] = useState('')
  const [assetResults, setAssetResults] = useState([])
  const [licenseQuery, setLicenseQuery] = useState('')
  const [licenseResults, setLicenseResults] = useState([])

  const [editingDetails, setEditingDetails] = useState(false)
  const [draftTitle, setDraftTitle] = useState('')
  const [draftDescription, setDraftDescription] = useState('')
  const [savingDetails, setSavingDetails] = useState(false)
  const [detailsError, setDetailsError] = useState('')

  const load = async () => {
    try {
      const [t, c, a] = await Promise.all([
        api.get(`/tickets/${id}`),
        api.get(`/tickets/${id}/comments`),
        api.get(`/tickets/${id}/attachments`),
      ])
      setTicket(t)
      setComments(c)
      setAttachments(a)
      if (isAgent) {
        api.get(`/tickets/${id}/audit`).then(setAudit).catch(() => {})
      }
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    load()
    if (isAgent) {
      api.get('/settings/categories').then((c) => setCategories(c.map((x) => x.name)))
      api.get('/users/agents').then(setAgents)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const patch = async (fields) => {
    const updated = await api.patch(`/tickets/${id}`, fields)
    setTicket(updated)
    load()
  }

  const startEditingDetails = () => {
    setDraftTitle(ticket.title)
    setDraftDescription(ticket.description || '')
    setDetailsError('')
    setEditingDetails(true)
  }

  const saveDetails = async () => {
    setSavingDetails(true)
    setDetailsError('')
    try {
      await patch({ title: draftTitle, description: draftDescription })
      setEditingDetails(false)
    } catch (err) {
      setDetailsError(err.message)
    } finally {
      setSavingDetails(false)
    }
  }

  const submitComment = async (e) => {
    e.preventDefault()
    if (!commentBody.trim()) return
    setPosting(true)
    try {
      await api.post(`/tickets/${id}/comments`, { body: commentBody, is_internal: isInternal })
      setCommentBody('')
      setIsInternal(false)
      load()
    } finally {
      setPosting(false)
    }
  }

  const uploadFile = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    const fd = new FormData()
    fd.append('file', file)
    try {
      await api.upload(`/tickets/${id}/attachments`, fd)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const searchAssets = async (q) => {
    setAssetQuery(q)
    if (q.trim().length < 1) return setAssetResults([])
    setAssetResults(await api.get(`/assets?q=${encodeURIComponent(q)}`))
  }
  const searchLicenses = async (q) => {
    setLicenseQuery(q)
    if (q.trim().length < 1) return setLicenseResults([])
    setLicenseResults(await api.get(`/licenses?q=${encodeURIComponent(q)}`))
  }
  const linkAsset = async (assetId) => {
    await api.post(`/tickets/${id}/link-asset`, { id: assetId })
    setAssetQuery('')
    setAssetResults([])
    load()
  }
  const linkLicense = async (licenseId) => {
    await api.post(`/tickets/${id}/link-license`, { id: licenseId })
    setLicenseQuery('')
    setLicenseResults([])
    load()
  }
  const unlinkAsset = async (assetId) => {
    await api.del(`/tickets/${id}/link-asset/${assetId}`)
    load()
  }
  const unlinkLicense = async (licenseId) => {
    await api.del(`/tickets/${id}/link-license/${licenseId}`)
    load()
  }

  const timeline = useMemo(() => {
    const commentEvents = comments.map((c) => ({ type: 'comment', at: c.created_at, data: c }))
    const auditEvents = audit.map((a) => ({ type: 'audit', at: a.changed_at, data: a }))
    return [...commentEvents, ...auditEvents].sort((a, b) => (a.at < b.at ? -1 : 1))
  }, [comments, audit])

  if (error) return <div className="text-sm text-red-600">{error}</div>
  if (!ticket) return <div className="text-sm text-slate-400">Loading ticket…</div>

  const canClose = !isAgent && ticket.status === 'Resolved' && ticket.requester_id === user.id
  const canEditDetails = !isAgent && ticket.requester_id === user.id && ticket.status !== 'Closed'

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div>
        <Link to={isAgent ? '/tickets' : '/'} className="text-xs text-brand-600 hover:underline">&larr; Back</Link>
      </div>

      <div className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="text-xs font-medium text-slate-400">{ticket.ticket_number}</div>
            {editingDetails ? (
              <input
                className="input mt-1 text-lg font-semibold"
                value={draftTitle}
                onChange={(e) => setDraftTitle(e.target.value)}
                maxLength={300}
              />
            ) : (
              <h1 className="text-lg font-semibold text-slate-800">{ticket.title}</h1>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <PriorityBadge priority={ticket.priority} />
            <StatusBadge status={ticket.status} />
            <SlaBadge overdue={ticket.sla_overdue} status={ticket.status} />
          </div>
        </div>

        {editingDetails ? (
          <div className="mt-3 space-y-2">
            {detailsError && <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{detailsError}</div>}
            <textarea
              className="input"
              rows={4}
              value={draftDescription}
              onChange={(e) => setDraftDescription(e.target.value)}
            />
            <div className="flex gap-2">
              <button className="btn-primary" disabled={savingDetails} onClick={saveDetails}>
                {savingDetails ? 'Saving…' : 'Save'}
              </button>
              <button className="btn-secondary" onClick={() => setEditingDetails(false)}>Cancel</button>
            </div>
          </div>
        ) : (
          <div className="mt-3 flex items-start justify-between gap-3">
            <p className="whitespace-pre-wrap text-sm text-slate-700">{ticket.description || <span className="text-slate-400">No description provided.</span>}</p>
            {canEditDetails && (
              <button className="flex-shrink-0 text-xs text-brand-600 hover:underline" onClick={startEditingDetails}>Edit</button>
            )}
          </div>
        )}

        <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 border-t border-slate-100 pt-4 text-sm md:grid-cols-4">
          <Field label="Requester" value={`${ticket.requester_name}${ticket.requester_department ? ' · ' + ticket.requester_department : ''}`} />
          <Field label="Requester email" value={ticket.requester_email} />
          <Field label="Category" value={ticket.category} />
          <Field label="Assignee" value={ticket.assignee_name || 'Unassigned'} />
          <Field label="Created" value={ticket.created_at} />
          <Field label="Updated" value={ticket.updated_at} />
          <Field label="SLA due" value={ticket.sla_due_at || '—'} />
          <Field label="Resolved" value={ticket.resolved_at || '—'} />
        </div>

        {canClose && (
          <div className="mt-4 border-t border-slate-100 pt-4">
            <button className="btn-primary" onClick={() => patch({ status: 'Closed' })}>Close this ticket</button>
            <span className="ml-2 text-xs text-slate-400">Your issue was marked resolved — close it once you're satisfied, or add a comment if it needs more work.</span>
          </div>
        )}

        {isAgent && (
          <div className="mt-4 grid grid-cols-1 gap-3 border-t border-slate-100 pt-4 sm:grid-cols-4">
            <div>
              <label className="label">Status</label>
              <select className="input" value={ticket.status} onChange={(e) => patch({ status: e.target.value })}>
                {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Priority</label>
              <select className="input" value={ticket.priority} onChange={(e) => patch({ priority: e.target.value })}>
                {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Category</label>
              <select className="input" value={ticket.category} onChange={(e) => patch({ category: e.target.value })}>
                {categories.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Assignee</label>
              <select
                className="input"
                value={ticket.assignee_id || ''}
                onChange={(e) => patch({ assignee_id: e.target.value ? Number(e.target.value) : null })}
              >
                <option value="">Unassigned</option>
                {agents.map((a) => <option key={a.id} value={a.id}>{a.full_name}</option>)}
              </select>
            </div>
          </div>
        )}
      </div>

      {isAgent && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <LinkedPanel
            title="Linked Assets"
            items={ticket.assets}
            renderItem={(a) => `${a.asset_tag} — ${a.type}`}
            onUnlink={(a) => unlinkAsset(a.id)}
            query={assetQuery}
            onQuery={searchAssets}
            results={assetResults}
            renderResult={(a) => `${a.asset_tag} — ${a.type} (${a.status})`}
            onLink={(a) => linkAsset(a.id)}
          />
          <LinkedPanel
            title="Linked Licenses"
            items={ticket.licenses}
            renderItem={(l) => `${l.software_name}`}
            onUnlink={(l) => unlinkLicense(l.id)}
            query={licenseQuery}
            onQuery={searchLicenses}
            results={licenseResults}
            renderResult={(l) => `${l.software_name} (${l.seats_available} seats free)`}
            onLink={(l) => linkLicense(l.id)}
            readOnly={!isAdmin}
          />
        </div>
      )}

      <div className="card p-5">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Attachments</h2>
        <ul className="mb-3 space-y-1 text-sm">
          {attachments.map((a) => (
            <li key={a.id}>
              <a className="text-brand-600 hover:underline" href={`${API_BASE}/tickets/${id}/attachments/${a.id}/download`}>
                {a.filename}
              </a>
              <span className="ml-2 text-xs text-slate-400">{(a.size / 1024).toFixed(0)} KB · {a.uploaded_by} · {a.uploaded_at}</span>
            </li>
          ))}
          {attachments.length === 0 && <li className="text-slate-400">No attachments yet.</li>}
        </ul>
        <input type="file" onChange={uploadFile} disabled={uploading} className="text-sm" />
      </div>

      <div className="card p-5">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Activity</h2>
        <ul className="space-y-3">
          {timeline.map((event, idx) =>
            event.type === 'comment' ? (
              <li key={`c${idx}`} className={`rounded-md border p-3 text-sm ${event.data.is_internal ? 'border-amber-200 bg-amber-50' : 'border-slate-100 bg-slate-50'}`}>
                <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
                  <span className="font-medium text-slate-700">{event.data.author_name}</span>
                  <span>{event.data.created_at}{event.data.is_internal && <span className="ml-2 badge bg-amber-100 text-amber-800">Internal note</span>}</span>
                </div>
                <p className="whitespace-pre-wrap text-slate-700">{event.data.body}</p>
              </li>
            ) : (
              <li key={`a${idx}`} className="text-xs text-slate-400">
                {event.data.changed_by} changed <span className="font-medium text-slate-500">{event.data.field}</span>{' '}
                from "{event.data.old_value || '—'}" to "{event.data.new_value || '—'}" · {event.data.changed_at}
              </li>
            )
          )}
          {timeline.length === 0 && <li className="text-sm text-slate-400">No activity yet.</li>}
        </ul>

        <form onSubmit={submitComment} className="mt-4 space-y-2 border-t border-slate-100 pt-4">
          <textarea
            className="input"
            rows={3}
            placeholder={isAgent ? 'Add a comment or internal note…' : 'Add a comment…'}
            value={commentBody}
            onChange={(e) => setCommentBody(e.target.value)}
          />
          <div className="flex items-center justify-between">
            {isAgent ? (
              <label className="flex items-center gap-1.5 text-xs text-slate-500">
                <input type="checkbox" checked={isInternal} onChange={(e) => setIsInternal(e.target.checked)} />
                Internal note (not visible to requester)
              </label>
            ) : <span />}
            <button type="submit" disabled={posting} className="btn-primary">Post</button>
          </div>
        </form>
      </div>
    </div>
  )
}

function Field({ label, value }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className="text-slate-700">{value}</div>
    </div>
  )
}

function LinkedPanel({ title, items, renderItem, onUnlink, query, onQuery, results, renderResult, onLink, readOnly }) {
  return (
    <div className="card p-5">
      <h2 className="mb-3 text-sm font-semibold text-slate-700">{title}</h2>
      <ul className="mb-3 space-y-1 text-sm">
        {items.map((it) => (
          <li key={it.id} className="flex items-center justify-between">
            <span>{renderItem(it)}</span>
            {!readOnly && <button className="text-xs text-red-500 hover:underline" onClick={() => onUnlink(it)}>Unlink</button>}
          </li>
        ))}
        {items.length === 0 && <li className="text-slate-400">None linked.</li>}
      </ul>
      {!readOnly && (
        <>
          <input className="input" placeholder="Search to link…" value={query} onChange={(e) => onQuery(e.target.value)} />
          {results.length > 0 && (
            <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto rounded-md border border-slate-100 p-2 text-sm">
              {results.map((r) => (
                <li key={r.id}>
                  <button className="w-full text-left hover:text-brand-700" onClick={() => onLink(r)}>{renderResult(r)}</button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}
