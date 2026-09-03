# Changelog

## v1.4.0 — Requester ticket editing, real email notifications, reply-by-email

### Added
- Requesters can now edit their own ticket's title and description at any
  time before it's Closed (previously they could only close an already-
  Resolved ticket). Status/priority/category/assignee remain IT-only.
- Real outbound email (SMTP), off by default — set `SMTP_HOST` +
  `SMTP_FROM_EMAIL` to turn it on. Fires automatically for: ticket created
  (confirmation to requester, alert to every agent), status/progress changes,
  resolution, and new comments. See README §8a.
- Reply-by-email, off by default — set `INBOUND_EMAIL_DOMAIN` +
  `INBOUND_WEBHOOK_TOKEN` (needs SendGrid Inbound Parse configured on a
  subdomain, see README §8b). Replying to any ticket notification email adds
  the reply as a comment, matched to the sender's account (or the original
  walk-up requester's email); replying to a Resolved/Closed ticket reopens
  it. Quoted email history is stripped on a best-effort basis. Unrecognized
  senders/tickets are silently ignored, not errored, so spoofed mail can't
  inject comments.

---

## v1.3.0 — Proman branding, title rename, user delete/import, tightened permissions

### Added
- Proman logo + "IT Support & Maintenance Tracker" branding throughout the UI.
- Admins can delete individual users or bulk-delete via checkboxes, and
  bulk-import users from a CSV file (template downloadable from the Users
  page). A user with existing ticket history can't be deleted (would break
  the audit trail) — disable their account instead.
- Permission model reshaped around `is_admin` rather than role alone:
  non-admins (agent or requester) now only see tickets they raised or are
  assigned to and assets assigned to them (previously requesters had zero
  asset visibility at all); Dashboard, Reports, and Licenses are now
  Admin-only; delete rights (assets, licenses, KB articles, users) are now
  Admin-only. Non-admins land on a personal "My Tickets" + "My Assets" home
  page instead of the org-wide Dashboard.

---

## v1.1.0 — Railway deployment + Microsoft 365 SSO

### Added
- Deployment: multi-stage `Dockerfile`, `railway.toml`, `SESSION_SECURE_COOKIES`
  config, and uvicorn proxy-header trust — for running behind Railway (or any
  reverse proxy that terminates TLS) with a custom subdomain.
- Optional Microsoft 365 / Entra ID single sign-on, alongside (not replacing)
  local username/password login. Off by default; enabled by setting
  `MS_CLIENT_ID` / `MS_CLIENT_SECRET` / `MS_TENANT_ID` / `MS_REDIRECT_URI`.
  First-time SSO sign-ins auto-provision as Requester; existing local accounts
  are matched and linked by email. See README §5c for the Azure setup steps.
- Safe, idempotent DB migration path (`auth_provider`, `sso_subject` columns)
  that runs on every startup without touching existing data.

---

## v1.0.0 — Initial release

### Implemented

**Core**
- Tickets: auto-numbered (`IT-0001`), title/description, category, priority,
  status, requester (name/email/department), assignee, created/updated/resolved
  dates, configurable SLA due date, file attachments, comment thread
  (internal notes vs. requester-visible comments), full audit trail of
  status/priority/assignee changes.
- Assets: tag, type, assigned-to, location, purchase date, warranty expiry,
  status; linkable to one or more tickets.
- Licenses: software/vendor/key, total vs. in-use seats, renewal date, cost,
  owner; auto-flagged when expiring within 30/60/90 days; linkable to tickets.
- Users: Agent and Requester roles; agents can additionally be flagged Admin
  (manage users, categories, SLA rules). First admin/agent seeded on first run.

**Features**
- Configurable SLA rules per priority, with overdue flag shown throughout the UI.
- Agent dashboard: open tickets by priority/category, overdue tickets, tickets
  assigned to me, licenses expiring soon, assets due for warranty renewal,
  created-vs-resolved chart over the last 30 days.
- Filterable/sortable ticket list (status, priority, category, assignee, date
  range, keyword search) with bulk reassign / bulk status change.
- Ticket detail view: activity timeline, comments, status/priority/assignee
  changes, attachment upload, linked assets/licenses.
- Requester portal: raise a ticket, view "my tickets", comment, close own
  resolved tickets.
- In-app notification bell (new comment, assignment, status change), polled
  every 45s — see README for the SMTP extension point for a future v2.
- Knowledge base / canned responses: searchable, tagged by category.
- CSV export of any filtered ticket list, and a monthly summary report
  (tickets by category, avg resolution time, SLA compliance %) viewable
  on-screen and exportable to CSV.
- Full audit trail (who/when) for every status, priority, and assignee change.

**Non-functional**
- Single-port deployment: `python run.py` serves both the API and the built
  React frontend.
- SQLite DB + uploaded attachments both under `/data` for easy backup.
- Responsive layout down to tablet width (and usable on mobile, via a
  collapsible nav, though only laptop/tablet were required).
- Parameterized SQL everywhere (no string-built queries), file upload
  type/size limits, session-based auth, password hashing via PBKDF2
  (stdlib-only, no extra native crypto dependency).
- Seed data: category list + SLA defaults + 5 example tickets (3 seeded, 2
  created during setup verification) + example asset/license/KB article so
  the UI isn't empty on first run.

### Deferred (this section refers to the original v1.0.0 scope; see v1.4.0 above for what has since shipped)

- **Rich text / markdown rendering** for descriptions and comments — currently
  plain text (stored and rendered as-is, safely escaped). Markdown syntax
  support could be added to the description/comment renderer later without
  any schema changes.
- **Multi-tenant / multi-company support.**
- **Native mobile app** — responsive web only.
- **LDAP.** Microsoft 365/Entra ID SSO shipped in v1.1.0 (see above); LDAP
  specifically is still not implemented, though the same auth module
  (`backend/app/deps.py`, `backend/app/oauth.py`) would isolate it similarly.
- **Real-time updates** — notifications and lists use polling (30–60s), not
  websockets, by design.
- **Ticket-to-ticket linking / merging, SLA business-hours calendars** (SLA
  due dates are calendar-hour based, not business-hours-aware) — noted as a
  reasonable v2 candidate if the 24-hour SLA math ever needs to skip nights
  and weekends.
