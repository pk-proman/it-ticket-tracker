#!/usr/bin/env bash
# One-shot setup (and re-run-to-update) script for deploying the IT Support &
# Maintenance Tracker to a plain Ubuntu/Debian VPS (Hostinger's default VPS
# templates are Ubuntu/Debian-based). See README.md #5d for the full walkthrough.
#
# Safe to re-run: it won't touch your .env if one already exists, won't
# clobber any OTHER site's Caddy config on this box, and re-running after a
# `git push` is exactly how you deploy an update.
#
# Usage (as root, or with sudo):
#   ./vps-setup.sh --domain support.yourdomain.com --repo https://github.com/YOU/it-ticket-tracker.git
#
# Both flags can be omitted and you'll be prompted for them instead.

set -euo pipefail

APP_DIR="/opt/it-ticket-tracker"
CADDY_SITE_FILE="/etc/caddy/conf.d/it-ticket-tracker.caddy"
DOMAIN=""
REPO_URL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --repo) REPO_URL="$2"; shift 2 ;;
    --app-dir) APP_DIR="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "Run this as root (or with sudo) -- it installs system packages." >&2
  exit 1
fi

if [[ -z "$DOMAIN" ]]; then
  read -rp "Domain/subdomain this app will run on (e.g. support.yourdomain.com): " DOMAIN
fi
if [[ -z "$DOMAIN" ]]; then
  echo "A domain is required (Caddy needs it to issue a TLS certificate)." >&2
  exit 1
fi

echo
echo "=== 1/6: Docker ==="
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sh
else
  echo "Docker already installed, skipping."
fi

echo
echo "=== 2/6: Caddy (reverse proxy + automatic HTTPS) ==="
if ! command -v caddy &>/dev/null; then
  apt-get update -y
  apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    | tee /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y
  apt-get install -y caddy
else
  echo "Caddy already installed, skipping."
fi

echo
echo "=== 3/6: Application code ==="
if [[ -d "$APP_DIR/.git" ]]; then
  echo "Existing checkout found at $APP_DIR -- pulling latest instead of cloning."
  git -C "$APP_DIR" pull
else
  if [[ -z "$REPO_URL" ]]; then
    read -rp "Git URL to clone (e.g. https://github.com/YOU/it-ticket-tracker.git): " REPO_URL
  fi
  if [[ -z "$REPO_URL" ]]; then
    echo "A repo URL is required for the first-ever run on this box." >&2
    exit 1
  fi
  echo "If this is a private repo, cloning will prompt for GitHub credentials"
  echo "(a Personal Access Token, not your GitHub password) -- or pre-configure"
  echo "a deploy key/SSH remote yourself before running this script."
  git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

echo
echo "=== 4/6: Environment (.env) ==="
if [[ -f .env ]]; then
  echo ".env already exists, leaving it untouched."
else
  cp .env.example .env
  SESSION_SECRET="$(openssl rand -hex 32)"
  sed -i "s#^SESSION_SECRET=.*#SESSION_SECRET=${SESSION_SECRET}#" .env
  sed -i "s#^SESSION_SECURE_COOKIES=.*#SESSION_SECURE_COOKIES=true#" .env
  sed -i "s#^APP_BASE_URL=.*#APP_BASE_URL=https://${DOMAIN}#" .env
  sed -i "s#^DATA_DIR=.*#DATA_DIR=/data#" .env

  echo
  read -rsp "Set the initial admin password (used only on this very first run): " ADMIN_PW
  echo
  if [[ -n "$ADMIN_PW" ]]; then
    sed -i "s#^SEED_ADMIN_PASSWORD=.*#SEED_ADMIN_PASSWORD=${ADMIN_PW}#" .env
  fi
  echo "Wrote a fresh .env with a random SESSION_SECRET. Review it (SMTP, SSO,"
  echo "SLA hours, etc. are all optional) at $APP_DIR/.env before going further,"
  echo "then re-run this script -- or just continue now, you can edit .env and"
  echo "run 'docker compose up -d --build' again at any time."
fi

echo
echo "=== 5/6: Build and start the app ==="
mkdir -p "$APP_DIR/data"
docker compose up -d --build

echo
echo "=== 6/6: Reverse proxy ==="
mkdir -p /etc/caddy/conf.d
if ! grep -q "import /etc/caddy/conf.d/\*.caddy" /etc/caddy/Caddyfile 2>/dev/null; then
  # Only touch the main Caddyfile if it doesn't already import our directory
  # -- this box may serve other sites too; never clobber their config.
  echo "import /etc/caddy/conf.d/*.caddy" >> /etc/caddy/Caddyfile
fi
sed "s/YOUR_DOMAIN/${DOMAIN}/" "$APP_DIR/deploy/Caddyfile.template" > "$CADDY_SITE_FILE"
systemctl reload caddy || systemctl restart caddy

echo
echo "=================================================================="
echo "Done. Once DNS for ${DOMAIN} points at this server's IP, it's live at:"
echo "  https://${DOMAIN}"
echo
echo "To deploy an update later: re-run this same script (or just"
echo "'cd ${APP_DIR} && git pull && docker compose up -d --build')."
echo "=================================================================="
