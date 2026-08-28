const BASE = '/api'

class ApiError extends Error {
  constructor(message, status, detail) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

async function request(path, { method = 'GET', body, isForm = false } = {}) {
  const opts = {
    method,
    credentials: 'include',
    headers: {},
  }
  if (body !== undefined) {
    if (isForm) {
      opts.body = body
    } else {
      opts.headers['Content-Type'] = 'application/json'
      opts.body = JSON.stringify(body)
    }
  }
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = data.detail ?? detail
    } catch {
      /* ignore */
    }
    // FastAPI validation errors (422) come back as a list of {loc, msg, ...}
    // objects rather than a plain string -- flatten those into readable text.
    if (Array.isArray(detail)) {
      detail = detail.map((d) => (typeof d === 'string' ? d : d.msg || JSON.stringify(d))).join('; ')
    } else if (detail && typeof detail === 'object') {
      detail = detail.msg || JSON.stringify(detail)
    }
    throw new ApiError(detail, res.status, detail)
  }
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return res.json()
  }
  return res
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body }),
  patch: (path, body) => request(path, { method: 'PATCH', body }),
  put: (path, body) => request(path, { method: 'PUT', body }),
  del: (path) => request(path, { method: 'DELETE' }),
  upload: (path, formData) => request(path, { method: 'POST', body: formData, isForm: true }),
}

export function qs(params) {
  const clean = Object.fromEntries(
    Object.entries(params || {}).filter(([, v]) => v !== undefined && v !== null && v !== '')
  )
  const s = new URLSearchParams(clean).toString()
  return s ? `?${s}` : ''
}

export { ApiError }
export const API_BASE = BASE
