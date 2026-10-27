# Multi-stage build: compile the React frontend, then run it from a plain
# Python image. Used for PaaS deploys (Railway, Render, Fly.io, ...) — you do
# NOT need Docker at all to run this app locally, see README.md.

FROM node:24-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
# Generous retries/timeout: pip's defaults give up fast on a slow or flaky
# route to PyPI ("Could not find a version ... (from versions: none)"), which
# fails the whole build over what is usually a momentary network hiccup.
RUN pip install --no-cache-dir --retries 10 --timeout 60 -r backend/requirements.txt

COPY backend/ backend/
COPY run.py .
COPY --from=frontend-build /app/frontend/dist frontend/dist

# /data is where the SQLite DB + uploaded attachments live. Mount a persistent
# volume here on whatever platform you deploy to, or they're lost on redeploy.
ENV DATA_DIR=/data
RUN mkdir -p /data

EXPOSE 8000

CMD ["python", "run.py"]
