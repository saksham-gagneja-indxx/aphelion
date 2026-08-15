# Social Media Manager

A local-first social media automation tool for scheduling Instagram Reels.
Built with a Flask JSON API backend and a React (Vite + TypeScript) single-page
application frontend.

> **⚠️ Current status:** Instagram posting is **unimplemented and untested**.
> Instagram credentials are accepted in `.env` but are **not yet wired** to any
> real posting flow. Scheduled posts will transition to `failed` status when
> their scheduled time arrives. This project is a working prototype of the
> upload → schedule → queue pipeline — actual social media delivery is not
> yet functional.

---

## What it does

| Feature | Status |
|---------|--------|
| **Upload** — drag-and-drop reels with progress bar, server-side validation, thumbnail extraction via ffmpeg | ✅ Working |
| **Schedule** — pick a reel, set a date/time, create an APScheduler job | ✅ Working |
| **Queue** — see all posts (draft → scheduled → posted/failed/cancelled), with error details for failures | ✅ Working |
| **Analytics** — engagement metrics, best posting hours/days, confidence score | ✅ Working (seeded data) |
| **Settings** — Instagram connection status, account info | ✅ Working |
| **Instagram posting** — actually publishing to Instagram | ❌ Not implemented |
| **LinkedIn** — cross-posting to LinkedIn | ❌ Not implemented |
| **AI captions** — Claude-powered caption generation | ❌ Not implemented |

---

## Architecture

```
┌──────────────────────────────────┐
│  React SPA (Vite, :5173)         │  ← Browser
│  TypeScript + Tailwind CSS       │
│  TanStack Query for server state │
└──────────────┬───────────────────┘
               │ fetch() → JSON
               ▼
┌──────────────────────────────────┐
│  Flask JSON API (:5000)          │  ← Backend
│  APScheduler (in-process)        │
│  SQLite (data/automation.db)     │
│  Local file storage (data/reels/)│
└──────────────────────────────────┘
```

In development, the Vite dev server proxies `/api` and `/health` requests to
the Flask backend on `:5000`, keeping everything same-origin.

---

## Prerequisites

- **Python 3.12+** (3.9+ may work but is untested)
- **Node.js 20+** and npm
- **ffmpeg** and **ffprobe** — required for thumbnail extraction and video
  duration detection during upload
  - If not on your system `PATH`, set `FFMPEG_PATH` and `FFPROBE_PATH` in `.env`
  - On Windows: download from [ffmpeg.org](https://ffmpeg.org/download.html),
    extract, and add the `bin/` directory to PATH or set the env vars

---

## Setup

### 1. Clone

```bash
git clone https://github.com/saksham-gagneja-indxx/social-media-manager.git
cd social-media-manager
```

### 2. Backend

```bash
# Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Create your config
cp .env.example .env
# Edit .env — at minimum, set TIMEZONE to your local timezone.
# Instagram credentials are accepted but NOT yet used for posting.
```

### 3. Frontend

```bash
cd frontend
npm install
cd ..
```

---

## Running

You need **two terminals** — one for each server.

### Terminal 1 — Backend (Flask, port 5000)

```bash
# From the project root, with .venv activated
python -m backend.app
```

### Terminal 2 — Frontend (Vite, port 5173)

```bash
cd frontend
npm run dev
```

Then open **http://localhost:5173** in your browser.

---

## Project structure

```
social-media-manager/
├── backend/                  # Flask JSON API
│   ├── api/routes.py         # All HTTP endpoints
│   ├── core/                 # Business logic
│   │   ├── agent.py          # Instagram agent (stub)
│   │   ├── scheduler.py      # APScheduler integration
│   │   ├── reel_manager.py   # Upload validation + thumbnail extraction
│   │   └── analytics_engine.py
│   ├── models/               # SQLAlchemy models (User, Post, Analytics)
│   ├── utils/                # Config, database, logging
│   └── app.py                # Flask app entry point
│
├── frontend/                 # React SPA (Vite + TypeScript)
│   ├── src/
│   │   ├── api/              # Fetch wrappers + types
│   │   ├── components/       # Shared UI (QueryStates, ErrorBoundary)
│   │   ├── pages/            # Upload, Schedule, Queue, Analytics, Settings
│   │   ├── App.tsx           # Router + nav + ConnectionBadge
│   │   └── main.tsx          # React entry point
│   ├── package.json
│   └── vite.config.ts        # Dev proxy config
│
├── data/                     # Runtime data (SQLite DB, uploaded reels, logs)
├── docs/                     # Architecture, API, setup, timeline docs
├── tests/                    # Backend tests + seed scripts
├── .env.example              # Config template
└── requirements.txt          # Python dependencies
```

---

## Current limitations

1. **No real Instagram posting.** The `InstagramAgent` exists but is not wired
   to a working Instagram API client. Posts will be marked `failed` when their
   scheduled time arrives.

2. **No authentication.** The app assumes a single local user (user ID 1).
   There is no login screen or session management.

3. **SQLite only.** Fine for local dev, not suitable for production.

4. **In-process scheduler.** APScheduler runs inside the Flask process. If the
   server restarts, pending jobs are re-loaded from the DB but timing may drift.

5. **No AI features.** Claude API integration (caption generation, hashtag
   suggestions) is scaffolded but not implemented in the 24h scope.

6. **No LinkedIn support.** LinkedIn cross-posting is deferred to a future phase.

7. **Thumbnail generation requires ffmpeg.** If ffmpeg/ffprobe are not installed
   or not on PATH, uploads will succeed but thumbnails will be missing
   (the UI shows a placeholder).

---

## Development

```bash
# Type-check frontend
cd frontend && npx tsc --noEmit

# Production build
cd frontend && npx vite build

# Run frontend tests
cd frontend && npx vitest run

# Run backend
python -m backend.app
```

---

## License

Private — not open-source at this time.
