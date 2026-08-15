# Multi-stage build: one image serving both the API and the built SPA.
#
# NOTE: the backend is not currently deployed - see render.yaml. This image is
# kept working so hosting can be switched back on without rebuilding it.
#
# Why Docker rather than a native Python runtime:
#   * the frontend build needs Node, which the Python runtime does not
#     guarantee
#   * ffmpeg/ffprobe can be installed, so thumbnail generation and duration
#     validation work in production instead of silently degrading
#   * the build is reproducible locally and on the host
#
# Why one image rather than separate frontend/backend services:
#   * same origin, so CORS stops applying to the SPA entirely
#   * one custom domain to configure and one reputation to establish
#   * one free instance instead of two

# ---------- stage 1: build the SPA ----------
FROM node:20-slim AS frontend

WORKDIR /build

# Copy manifests first so this layer is cached unless dependencies change.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# In production the SPA is served from the same origin as the API, so requests
# go to relative /api paths and the dev proxy is irrelevant.
RUN npm run build


# ---------- stage 2: runtime ----------
FROM python:3.12-slim AS runtime

# ffmpeg carries ffprobe. Without these, uploads still work but duration
# validation is skipped and thumbnails are never generated.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps before app code, so a code change does not reinstall them.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend /build/dist ./frontend/dist

# Runtime data directories. The application creates these on demand, but
# making them explicit means a permissions or path problem surfaces at build
# time rather than on a user's first upload.
# NOTE: this filesystem is ephemeral in a container - uploaded videos
# do not survive a restart. The database is external and unaffected.
RUN mkdir -p data/uploads data/reels data/logs

# Unbuffered so logs reach the host's log stream immediately rather than sitting
# in a buffer until the process exits.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 10000

# Exactly ONE worker: APScheduler runs in-process, so additional workers would
# each start their own scheduler and fire every scheduled post once per worker.
CMD gunicorn "backend.app:create_app()" \
    --bind "0.0.0.0:${PORT:-10000}" \
    --workers 1 \
    --timeout 180 \
    --access-logfile - \
    --error-logfile -
