# IT Support & Maintenance Tracker

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

## 5. Deploying to Railway (with a custom subdomain)

The repo includes a `Dockerfile` and `railway.toml` so this deploys straight from
GitHub with no extra setup:

1. **Push this repo to GitHub** (see your own notes / team process, or GitHub's
   "create a new repository" flow — `git remote add origin <url>` then
   `git push -u origin main`).
2. **In Railway:** New Project → Deploy from GitHub repo → select this repo.
   Railway detects the `Dockerfile` automatically.
3. **Add a persistent volume** (Railway dashboard → your service → Volumes → New
   Volume) mounted at **`/data`**. Without this, the SQLite database and
   uploaded attachments are wiped on every redeploy.
4. **Set environment variables** (service → Variables): at minimum
   - `SESSION_SECRET` — a long random string (`openssl rand -hex 32`)
   - `SESSION_SECURE_COOKIES=true`
   - `SEED_ADMIN_PASSWORD` — a strong password (only used the very first time
     the DB is created, i.e. your first deploy)
   - any `SLA_HOURS_*` overrides you want

   Leave `PORT` alone — Railway injects it automatically and the app already
   reads it.
5. **Deploy.** Railway builds the Docker image and gives you a
   `*.up.railway.app` URL. Confirm it loads and you can log in with `admin` /
   whatever you set `SEED_ADMIN_PASSWORD` to, then change the password.
6. **Connect your subdomain:** Railway dashboard → service → Settings →
   Networking → Custom Domain → enter e.g. `support.yourdomain.com`. Railway
   shows you a CNAME target (something like `xxxx.up.railway.app`). Go to your
   domain's DNS provider (Cloudflare, GoDaddy, Namecheap, wherever you manage
   `yourdomain.com`) and add:
   ```
   Type:  CNAME
   Name:  support            (i.e. the subdomain part only)
   Value: xxxx.up.railway.app   (whatever Railway showed you)
   ```
   DNS propagation is usually minutes, occasionally up to ~24h. Railway
   auto-issues a free TLS certificate for the subdomain once the CNAME
   resolves — no certbot/manual TLS needed.

---

## 5b. Running as a background service (self-hosted alternative)

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

## 5c. Microsoft 365 single sign-on (optional)

Runs alongside local username/password login (never replaces it). Unset, the
app behaves exactly as v1.0.0 did. To turn it on:

1. Go to **[portal.azure.com](https://portal.azure.com) → Microsoft Entra ID →
   App registrations → New registration**.
2. **Name:** anything, e.g. "IT Support Ticket Tracker".
3. **Supported account types:** "Accounts in this organizational directory
   only (Single tenant)" — important, this restricts sign-in to your own
   organization only.
4. **Redirect URI:** platform **Web**, value
   `https://YOUR-DOMAIN/api/auth/sso/callback` (your Railway `*.up.railway.app`
   URL or your custom subdomain, whichever you're actually using).
5. **Register.**
6. From the **Overview** page, copy the **Application (client) ID** and
   **Directory (tenant) ID** — these are not secret.
7. Go to **Certificates & secrets → New client secret**, copy the *value*
   immediately (shown once, never again) — this one **is** secret.
8. Go to **API permissions** and click **Grant admin consent for
   &lt;your org&gt;** (the default `User.Read` / `openid` / `profile` / `email`
   scopes are enough).
9. Set these on your deployment (Railway → Variables, or your `.env`):
   ```
   MS_CLIENT_ID=<application client id>
   MS_TENANT_ID=<directory tenant id>
   MS_REDIRECT_URI=https://YOUR-DOMAIN/api/auth/sso/callback
   MS_CLIENT_SECRET=<the secret value>   # set this directly in your host's
                                          # dashboard, never commit it
   ```
10. Redeploy. A "Sign in with Microsoft" button appears on the login page
    automatically once all four variables are set.

**Provisioning behavior:** the first time someone signs in with Microsoft and
their email doesn't match an existing local account, they're auto-created as
a **Requester**. Nobody gets Agent or Admin access this way — promote them
manually under **Users** afterward. If their email *does* match an existing
local account (e.g. your seeded admin), that account is linked and reused —
no duplicate is created.

---

## 5d. Deploying to your own VPS (e.g. Hostinger)

This gets you from a VPS to the app running at your own domain over HTTPS,
using Docker (the same `Dockerfile` Railway builds from) reverse-proxied by
**nginx** — the same web server most Hostinger VPS boxes already run for
other sites, so this slots in as one more nginx site rather than introducing
a second, competing web server. TLS comes from certbot (free, auto-renewing
Let's Encrypt certificates).

(For a bare-metal setup with no Docker/nginx at all, see §5b instead — that
covers running `run.py` as a background service directly, but without the
reverse-proxy/TLS piece this section adds.)

**Prerequisites:**
- A VPS running Ubuntu or Debian (Hostinger's default templates), with root
  SSH access.
- A domain or subdomain with its DNS **A record** pointed at the VPS's public
  IP address. Doesn't have to be done before running the script below (it
  detects whether DNS has propagated yet and just skips the TLS step if not
  — see "if DNS isn't live yet" below), but the earlier the better.
- This repo pushed to GitHub. If the repo is private, either set up a deploy
  key beforehand or have a GitHub Personal Access Token ready — cloning will
  prompt for it.

**Steps**, run on the VPS itself (SSH in first — this can't be done from your
laptop):

```bash
ssh root@your-vps-ip

git clone https://github.com/YOUR_USERNAME/it-ticket-tracker.git /opt/it-ticket-tracker
cd /opt/it-ticket-tracker
./deploy/vps-setup.sh --domain itsupport.yourdomain.com
```

(Cloning first, rather than `curl`-ing the script directly, works whether the
repo is public or private, and matches the private-repo case which needs
your git credentials anyway.)

The script:
1. Installs Docker, if it isn't already (`docker.io` + `docker-compose-v2`
   from Ubuntu's own package repos — it does **not** add Docker's own apt
   repo, to keep this as unintrusive as possible on a box already running
   other production sites).
2. Installs `certbot` + its nginx plugin, if not already present. Does **not**
   install or touch nginx itself — it's already there.
3. Pulls the latest code if `/opt/it-ticket-tracker` already exists, clones it
   otherwise — **this is also how you deploy every future update**: just
   re-run the same script (or `cd /opt/it-ticket-tracker && git pull &&
   docker compose up -d --build`).
4. Writes a `.env` with a freshly generated `SESSION_SECRET`, prompting you
   once for the initial admin password. Only happens on the very first run —
   review/edit `.env` any time after for SMTP, SSO, SLA hours, etc.
5. Builds and starts the app container, bound to `127.0.0.1` only — never
   directly internet-facing; nginx is the only thing that talks to it. Picks
   the first free port starting from 8000 automatically (a shared box may
   already have something else on 8000) and records it as `APP_HOST_PORT` in
   `.env`, so this can't collide with anything else running there.
6. Adds **one new** nginx site for your domain
   (`/etc/nginx/sites-available/<domain>`, symlinked into `sites-enabled` —
   the same convention your other sites already use) proxying to the app.
   Runs `nginx -t` before every reload, so a mistake here can't take down
   your other sites. Never edits any existing site's config.
7. If DNS for your domain already resolves to this server, requests a TLS
   certificate via certbot automatically.

**If DNS isn't live yet** when you run it: everything above still completes,
`http://itsupport.yourdomain.com` starts working as soon as DNS propagates,
and you just run one more command afterward to add HTTPS:
```bash
certbot --nginx -d itsupport.yourdomain.com
```

Log in as `admin` with the password you set, then change it immediately (see
§3).

**Backups** work exactly as described in §4 — everything is under
`/opt/it-ticket-tracker/data` on the VPS now instead of a Railway volume.

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
  assignments, and status changes. Real email notifications are also
  available (see below) — the two aren't exclusive; the bell works regardless
  of whether email is configured.
- **SLA:** each priority has a configurable target resolution time (hours), set
  under Settings → SLA Rules. Tickets past their due date and still open show an
  "SLA overdue" badge everywhere in the UI.
- **CSV exports:** available from the Tickets list (any filtered view) and from
  the monthly Reports page.

---

## 8. Email notifications (optional)

Off by default (in-app bell only, nothing external required). Turn on outbound
email, and optionally reply-by-email, whenever you're ready. Two ways to send
outbound mail — pick whichever fits your situation (8a-i or 8a-ii), then 8b is
the same regardless of which you picked.

### 8a-i. Outbound email via Microsoft Graph (use this if your M365 tenant has SMTP AUTH disabled)

Many M365 tenants disable legacy SMTP AUTH tenant-wide by default (or
deliberately, as a security policy) — if that's you, plain SMTP against
`smtp.office365.com` will fail with `535 5.7.139 ... disabled for the
Tenant`, and re-enabling that tenant-wide is a real security trade-off you
may not want to make just for this app. Graph-based sending avoids the
question entirely: it uses OAuth2 client-credentials (the same mechanism
Power Automate and most modern M365 integrations use), not legacy SMTP AUTH,
so it's unaffected by that tenant setting either way.

1. Reuse the **same Azure app registration** you already created for SSO
   (§5c) — no need for a second one.
2. In that app registration: **API permissions → Add a permission →
   Microsoft Graph → Application permissions** → search for and add
   **`Mail.Send`**.
3. Click **Grant admin consent for &lt;your org&gt;** — this permission needs
   admin consent, and by default it lets the app send as *any* mailbox in
   your tenant, so it's worth locking down (next step).
4. **Recommended:** restrict which mailbox(es) this app can actually send as,
   via an Exchange Online `ApplicationAccessPolicy` (needs Exchange Online
   PowerShell — this one **is** just a scoping/allow-list step, not the
   tenant-wide SMTP AUTH toggle):
   ```powershell
   New-DistributionGroup -Name "GraphMailSenders" -Members support@yourdomain.com
   New-ApplicationAccessPolicy -AppId <MS_CLIENT_ID> -PolicyScopeGroupId "GraphMailSenders" -AccessRight RestrictAccess -Description "IT Ticket Tracker - mail send only"
   ```
   Without this, the permission works fine but is broader than it needs to
   be — skip it if you're comfortable with that for now, it's not required
   for functionality.
5. Set these on your deployment (`.env` or Railway → Variables) — no new
   client ID/secret needed, just one more variable alongside the SSO ones:
   ```
   MS_CLIENT_ID=<same value as SSO>
   MS_CLIENT_SECRET=<same value as SSO>
   MS_TENANT_ID=<same value as SSO>
   MS_MAIL_SENDER=support@yourdomain.com   # must be a real, licensed mailbox
   APP_BASE_URL=https://support.yourdomain.com
   ```
6. Restart to apply: `docker compose up -d --force-recreate` (VPS) or
   redeploy (Railway).

### 8a-ii. Outbound email via plain SMTP (any provider)

Set these instead of the Graph variables above:

```
SMTP_HOST=smtp.yourprovider.com
SMTP_PORT=587
SMTP_USERNAME=your-smtp-username
SMTP_PASSWORD=your-smtp-password        # set this directly in your host's
                                         # dashboard, never commit it
SMTP_USE_TLS=true
SMTP_FROM_EMAIL=support@yourdomain.com
SMTP_FROM_NAME=IT Support & Maintenance Tracker
APP_BASE_URL=https://support.yourdomain.com   # used to build ticket links in emails
```

Any standard SMTP provider works (Gmail SMTP, SendGrid, Mailgun, Postmark,
Amazon SES, your own mail server, or an M365 mailbox if its tenant *does*
allow legacy SMTP AUTH). If both this and the Graph variables above are set,
Graph takes priority.

---

Either way, once configured, emails go out automatically for: ticket created
(confirmation to the requester, alert to every agent), status/progress
changes, resolution, and new comments — no other configuration needed, and
no code changes if you add categories/statuses later.

### 8b. Reply-by-email (optional, needs 8a done first)

Lets someone reply directly to a notification email to add a comment to that
ticket — no login needed. Requires **SendGrid** for receiving mail (running
your own mail server to receive email reliably isn't practical for a
self-hosted app like this one).

1. Pick a subdomain you'll dedicate to this, e.g. `reply.yourdomain.com`.
2. In SendGrid: **Settings → Inbound Parse → Add Host & URL**.
   - **Domain:** `reply.yourdomain.com`
   - **URL:** `https://support.yourdomain.com/api/email/inbound/<a-random-secret-you-pick>`
     (the random secret in the URL is the only auth SendGrid's Inbound Parse
     supports — treat it like a password)
3. At your DNS provider, add an MX record so mail for that subdomain reaches
   SendGrid:
   ```
   Type: MX
   Name: reply
   Value: mx.sendgrid.net
   Priority: 10
   ```
4. Set these on your deployment:
   ```
   INBOUND_EMAIL_DOMAIN=reply.yourdomain.com
   INBOUND_WEBHOOK_TOKEN=<the same random secret from the URL above>
   ```
5. Redeploy. Every ticket email now has `Reply-To: ticket-it-0001@reply.yourdomain.com`
   (matching the actual ticket), and replying:
   - Adds the reply as a comment on that ticket, from whoever sent it (matched
     by email address — the requester, or an agent/admin's account).
   - **Reopens the ticket** if the requester replies to a Resolved/Closed one
     — the resolution email explicitly invites this ("if it's not actually
     fixed, just reply").
   - Is silently ignored (not an error, just does nothing) if the sender's
     email doesn't match anyone associated with the ticket, or the ticket
     number can't be parsed from the address — this is deliberate, so
     spoofed/unrelated email can't inject comments.

   Quoted email history ("On ... wrote: > ...") is stripped from replies on a
   best-effort basis — this covers the common clients (Gmail, Apple Mail,
   Outlook) but email reply parsing has no fully reliable solution, so an
   unusual client's reply may occasionally include some extra quoted text.

---

## 9. Installing on a phone (PWA)

The app is a installable Progressive Web App — no app store, no separate
build. Once deployed behind HTTPS (Railway gives you this automatically,
see §5), anyone can add it to their home screen:

**Android (Chrome):** open the app, tap the **⋮** menu → **Install app** (or
**Add to Home screen**). Some Android/Chrome versions show an automatic
"Install" banner instead.

**iPhone/iPad (Safari — must be Safari, not Chrome, for this to work):** open
the app, tap the **Share** icon → **Add to Home Screen**.

Either way, it then launches full-screen from the home screen icon like a
native app, with the Proman "IT" icon and no browser address bar. It's still
the same web app underneath — no separate install/update process, everyone
always gets the current deployed version, and there's nothing to publish to
an app store.

A note on **offline behavior**: the app shell (the UI itself) is cached for
fast loading, but ticket/asset/license data is never cached — every screen
always fetches live from the server. That's deliberate: this app already
requires the server for real use, so pretending the data works offline would
just show stale information as if it were current, which is worse than
clearly needing a connection.

---

## 10. Project structure

```
/backend    FastAPI app, SQLite access, business logic, routers
/frontend   React + Vite + Tailwind source (builds to frontend/dist)
/data       SQLite DB + uploaded attachments (created on first run, back this up)
run.py      Single entrypoint: `python run.py` serves API + built frontend on :8000
```
