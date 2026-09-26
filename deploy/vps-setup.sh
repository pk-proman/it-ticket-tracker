#!/usr/bin/env bash
# One-shot setup (and re-run-to-update) script for deploying the IT Support &
# Maintenance Tracker onto a VPS that's already running nginx for other
# sites (Hostinger or any Ubuntu/Debian box). See README.md #5d.
#
# Adds ONE new nginx site (sites-available/<domain>, symlinked into
# sites-enabled -- the same convention your other sites already use) and
# never touches any existing site's config. Runs `nginx -t` before every
# reload so a mistake here can't take down anything else on the box.
#
# Safe to re-run: won't touch your .env if one already exists, won't
# clobber the nginx site file if TLS has already been added to it by
# certbot. Re-running after a `git push` is exactly how you deploy an update.
#
# Usage (as root, or with sudo):
#   ./vps-setup.sh --domain itsupport.yourdomain.com --repo https://github.com/YOU/it-ticket-tracker.git
#
# Both flags can be omitted and you'll be prompted for them instead.

set -euo pipefail

APP_DIR="/opt/it-ticket-tracker"
DOMAIN=""
REPO_URL=""
CERTBOT_EMAIL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --repo) REPO_URL="$2"; shift 2 ;;
    --app-dir) APP_DIR="$2"; shift 2 ;;
    --email) CERTBOT_EMAIL="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "Run this as root (or with sudo) -- it installs system packages." >&2
  exit 1
fi

if [[ -z "$DOMAIN" ]]; then
  read -rp "Domain/subdomain this app will run on (e.g. itsupport.yourdomain.com): " DOMAIN
fi
if [[ -z "$DOMAIN" ]]; then
  echo "A domain is required." >&2
  exit 1
fi

NGINX_SITE_FILE="/etc/nginx/sites-available/${DOMAIN}"
NGINX_SITE_LINK="/etc/nginx/sites-enabled/${DOMAIN}"

# Finds the first free TCP port on localhost, starting from $1 -- used so
# this app never fights another site/service on the same box over a port.
find_free_port() {
  local port=$1
  while ss -tln 2>/dev/null | grep -q ":${port} "; do
    port=$((port + 1))
  done
  echo "$port"
}

echo
echo "=== 1/6: Docker ==="
if ! command -v docker &>/dev/null; then
  apt-get update -y
  apt-get install -y docker.io docker-compose-v2
  systemctl enable --now docker
else
  echo "Docker already installed, skipping."
fi

echo
echo "=== 2/6: certbot (for TLS -- nginx itself is already on this box) ==="
if ! command -v certbot &>/dev/null; then
  apt-get update -y
  apt-get install -y certbot python3-certbot-nginx
else
  echo "certbot already installed, skipping."
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
  echo ".env already exists, leaving its settings untouched."
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
  echo "SLA hours, etc. are all optional) at $APP_DIR/.env any time, then"
  echo "'docker compose up -d --build' again to pick up changes."
fi

# Pick a free host port -- 8000 is a common default that something else on a
# shared box may already be using. Runs even against a pre-existing .env
# from an earlier version of this script that didn't have this line yet.
if ! grep -q "^APP_HOST_PORT=" .env; then
  APP_HOST_PORT="$(find_free_port 8000)"
  echo "APP_HOST_PORT=${APP_HOST_PORT}" >> .env
  echo "Port 8000 (or higher) check: using ${APP_HOST_PORT} for this app on the host side."
fi
APP_HOST_PORT="$(grep "^APP_HOST_PORT=" .env | cut -d= -f2)"

echo
echo "=== 5/6: Build and start the app ==="
mkdir -p "$APP_DIR/data"
docker compose up -d --build

echo
echo "=== 6/6: nginx site + TLS ==="
if [[ -f "$NGINX_SITE_FILE" ]]; then
  echo "nginx site file for ${DOMAIN} already exists -- leaving it as-is"
  echo "(it may already have TLS added by certbot; re-run certbot manually"
  echo "if you need to)."
else
  sed -e "s/YOUR_DOMAIN/${DOMAIN}/" -e "s/APP_HOST_PORT/${APP_HOST_PORT}/" \
    "$APP_DIR/deploy/nginx-site.conf.template" > "$NGINX_SITE_FILE"
  ln -sf "$NGINX_SITE_FILE" "$NGINX_SITE_LINK"
  nginx -t
  systemctl reload nginx
  echo "HTTP site for ${DOMAIN} is live (once DNS points here)."

  SERVER_IP="$(curl -fsS -4 https://api.ipify.org || true)"
  RESOLVED_IP="$(getent hosts "$DOMAIN" 2>/dev/null | awk '{print $1}' | head -1 || true)"
  if [[ -n "$SERVER_IP" && "$RESOLVED_IP" == "$SERVER_IP" ]]; then
    echo "DNS for ${DOMAIN} already resolves here -- requesting a TLS certificate..."
    if [[ -z "$CERTBOT_EMAIL" ]]; then
      CERTBOT_EMAIL="admin@${DOMAIN#*.}"  # guessed -- only used for renewal-expiry notices, pass --email to be exact
    fi
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$CERTBOT_EMAIL" --redirect \
      && echo "TLS enabled." \
      || echo "certbot failed -- once DNS is confirmed pointed here, run: certbot --nginx -d ${DOMAIN}"
  else
    echo "DNS for ${DOMAIN} doesn't resolve to this server yet (server is"
    echo "${SERVER_IP:-unknown}, domain resolves to ${RESOLVED_IP:-nothing}) --"
    echo "skipping TLS for now. Once your DNS A record is live, run:"
    echo "  certbot --nginx -d ${DOMAIN}"
  fi
fi

echo
echo "=================================================================="
echo "Done. Once DNS for ${DOMAIN} points at this server's IP:"
echo "  http://${DOMAIN}   (works immediately)"
echo "  https://${DOMAIN}  (once the certbot step above succeeds)"
echo
echo "To deploy an update later: re-run this same script (or just"
echo "'cd ${APP_DIR} && git pull && docker compose up -d --build')."
echo "=================================================================="
