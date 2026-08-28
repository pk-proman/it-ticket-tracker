# IT Support Ticket Tracker

A self-hosted IT support ticket tracking system for internal use at a manufacturing
company. Runs entirely on `localhost` (or your local network) with no external
dependencies, no Docker, and no external database server. Everything — API and UI —
is served from a single Python process on one port.

- **Backend:** Python (FastAPI) + SQLite (single file database)
- **Frontend:** React + Vite + Tailwind CSS, built to static files and served by the backend
- **Auth:** built-in username/password login with signed session cookies
- **Storage:** SQLite database + uploaded attachments both live under `/data`

---

## 1. Prerequisites

- **Python 3.10+** (check with `python3 --version`)
- **Node.js 18+** and npm (check with `node --version` / `npm --version`) — only
  needed once, to build the frontend. The running app itself does not need Node.

Nothing else. No Docker, no Postgres/MySQL, no message queue.

---

## 2. First-time setup

From the project root:

```bash
# 1. Backend: create a virtual environment and install Python deps
python3 -m venv .venv
./.venv/bin/pip install -r backend/requirements.txt

# 2. Frontend: install JS deps and build the static production bundle
cd frontend
npm install
npm run build
cd ..

# 3. Run the app
./.venv/bin/python run.py
```

Then open **http://localhost:8000** in your browser.

That's it — steps 1 and 2 are one-time setup. After that, day-to-day you only need:

```bash
./.venv/bin/python run.py
```

### Configuration (optional)

Copy `.env.example` to `.env` and adjust as needed (port, session secret, SLA hours
per priority, max upload size, first-run admin credentials). If you skip this, sane
defaults are used automatically.

```bash
cp .env.example .env
```

**Important:** change `SESSION_SECRET` in `.env` before running this anywhere
beyond your own laptop — the default value is not secret.

---

## 3. First-run admin account

On first run (when the database doesn't exist yet), the app automatically creates:

- One **admin/agent** account: username `admin`, password `admin123` (or whatever
  you set `SEED_ADMIN_USERNAME` / `SEED_ADMIN_PASSWORD` to in `.env` before the
  first run)
- A couple of example accounts, tickets, an asset, a license, and a knowledge base
  article, so the UI isn't empty when you first log in.

**Log in as `admin` and change the password immediately** (Users → Reset Password
on your own account), or set a strong `SEED_ADMIN_PASSWORD` in `.env` before the
very first run.

Admins can create additional agent and requester accounts under **Users** in the
sidebar.

---

## 4. Data & backup

Everything that matters lives in one folder: **`/data`** at the project root.

```
data/
  app.db          <- SQLite database (tickets, users, assets, licenses, etc.)
  uploads/         <- ticket attachments, stored on disk
```

To back up the whole application, just copy or archive the `/data` folder while the
app isn't actively writing (or use SQLite's `.backup` for a live-safe copy):

```bash
# simple offline backup
cp -R data data-backup-$(date +%Y%m%d)

# or, for a consistent backup while the app is running
sqlite3 data/app.db ".backup 'data-backup-$(date +%Y%m%d).db'"
```

To restore, stop the app, replace `/data` with the backed-up copy, and restart.

---

## 5. Running as a background service

### Linux (systemd)

Create `/etc/systemd/system/it-ticket-tracker.service`:

```ini
[Unit]
Description=IT Support Ticket Tracker
After=network.target

[Service]
Type=simple
User=itapp
WorkingDirectory=/opt/it-ticket-tracker
ExecStart=/opt/it-ticket-tracker/.venv/bin/python run.py
Restart=on-failure
EnvironmentFile=/opt/it-ticket-tracker/.env

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now it-ticket-tracker
sudo systemctl status it-ticket-tracker
```

### Windows (as a service via NSSM)

1. Download [NSSM](https://nssm.cc/) and extract it somewhere permanent.
2. Open an admin Command Prompt in that folder and run:
   ```cmd
   nssm install ITTicketTracker
   ```
3. In the dialog:
   - **Path:** `C:\path\to\project\.venv\Scripts\python.exe`
   - **Startup directory:** `C:\path\to\project`
   - **Arguments:** `run.py`
4. Click **Install service**, then start it:
   ```cmd
   nssm start ITTicketTracker
   ```

### Windows (alternative: Scheduled Task, no extra tools)

1. Open **Task Scheduler** → **Create Task**.
2. **General:** name it, check "Run whether user is logged on or not".
3. **Triggers:** New → "At startup".
4. **Actions:** New → Program/script: `C:\path\to\project\.venv\Scripts\python.exe`,
   Arguments: `run.py`, Start in: `C:\path\to\project`.
5. Save.

---

## 6. Resetting an admin password

If you're locked out, reset any user's password from the command line (no need for
the UI):

```bash
./.venv/bin/python backend/reset_password.py admin "NewStrongPassword123"
```

This works for any username, not just `admin`.

---

## 7. Everyday usage notes

- **Roles:** Agents (IT staff, full access) and Requesters (raise/view their own
  tickets). Agents can additionally be marked **Admin**, which unlocks user
  management, category management, and SLA rule configuration under **Settings**.
- **Notifications:** the bell icon polls every ~45 seconds for new comments,
  assignments, and status changes — no email is sent (see below).
- **SLA:** each priority has a configurable target resolution time (hours), set
  under Settings → SLA Rules. Tickets past their due date and still open show an
  "SLA overdue" badge everywhere in the UI.
- **CSV exports:** available from the Tickets list (any filtered view) and from
  the monthly Reports page.

---

## 8. Adding email notifications later (not in v1)

v1 intentionally ships with in-app notifications only, to avoid any external SMTP
dependency for the initial setup. There's a single, clearly marked extension point
to wire in email later: `notify_user()` in
[`backend/app/utils.py`](backend/app/utils.py). See the comment block inside that
function for exactly what to add.

---

## 9. Project structure

```
/backend    FastAPI app, SQLite access, business logic, routers
/frontend   React + Vite + Tailwind source (builds to frontend/dist)
/data       SQLite DB + uploaded attachments (created on first run, back this up)
run.py      Single entrypoint: `python run.py` serves API + built frontend on :8000
```
