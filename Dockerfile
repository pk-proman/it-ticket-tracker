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
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY run.py .
COPY --from=frontend-build /app/frontend/dist frontend/dist

# /data is where the SQLite DB + uploaded attachments live. Mount a persistent
# volume here on whatever platform you deploy to, or they're lost on redeploy.
ENV DATA_DIR=/data
RUN mkdir -p /data

EXPOSE 8000

CMD ["python", "run.py"]
