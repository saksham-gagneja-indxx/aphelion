# Architecture — React + Flask Split (24h Build)

This replaces the original Bootstrap/Jinja architecture described in `IMPLEMENTATION_COMPLETE.md`. The backend service layer (agent, scheduler, reel manager) is unchanged in concept — only the presentation layer and API contract shift.

---

## High-Level Diagram

```
┌───────────────────────────────────────────┐
│   React SPA (Vite + TypeScript)            │
│   - Upload/Queue page                      │
│   - Schedule page                          │
│   - Analytics page (basic)                 │
│   - Settings page (Instagram connect)      │
│   - TanStack Query for server state        │
│   - Tailwind CSS                           │
└──────────────────┬──────────────────────────┘
                    │ fetch() → JSON over HTTP
                    ↓
┌───────────────────────────────────────────┐
│   Flask JSON API (backend/api/routes.py)   │
│   - No server-rendered templates           │
│   - CORS enabled for local dev             │
│   - Multipart upload endpoint (streaming)  │
└──────────────────┬──────────────────────────┘
                    ↓
┌───────────────────────────────────────────┐
│   Service Layer (unchanged from Phase 1)   │
│   ├─ InstagramAgent (backend/core/agent.py)│
│   ├─ SmartScheduler (core/scheduler.py)    │
│   ├─ ReelManager (core/reel_manager.py)    │
│   └─ AnalyticsEngine (core/analytics_engine.py) │
└──────────────────┬──────────────────────────┘
                    ↓
┌───────────────────────────────────────────┐
│   Data Layer                               │
│   ├─ SQLite (data/automation.db)           │
│   ├─ Local file storage (data/reels/)      │
│   └─ Rotating logs (data/logs/)            │
└───────────────────────────────────────────┘
```

---

## What Changed vs. the Original Build

| Layer | Original (8-week plan) | 24h Build |
|---|---|---|
| Frontend | Flask + Jinja templates, Bootstrap 5, vanilla JS | React + Vite + TypeScript, Tailwind, TanStack Query |
| API | Flask routes returning JSON (already API-shaped) | Same routes, trimmed to what the SPA needs, CORS added |
| Auth | None planned for v1 | Still none — single local user, no login screen |
| Media upload | Basic multipart form | Streaming multipart write + client-side pre-validation + background ffmpeg thumbnailing |
| Analytics | Full engine with confidence scoring, hourly/daily breakdowns | Same engine kept, but UI shows a simplified summary first; full charts are stretch goal |
| Database | SQLite (dev) / PostgreSQL (prod-ready) | SQLite only — Postgres path deferred |

The backend service layer (agent/scheduler/reel_manager/analytics_engine) does **not** need a rewrite — it was already framework-agnostic business logic called from Flask routes. The work is: (1) strip Flask down to JSON-only, (2) add CORS, (3) build the React app against the existing/trimmed API contract, (4) harden the upload path.

---

## Directory Structure (target)

```
social-media-automation/
├── backend/                  # Flask JSON API (existing, trimmed)
│   ├── app.py
│   ├── core/                 # agent.py, scheduler.py, reel_manager.py, analytics_engine.py
│   ├── models/                # user.py, post.py, analytics.py
│   ├── api/routes.py         # trimmed endpoint set
│   └── utils/                # config.py, logger.py, database.py
├── frontend/                 # NEW — React app (replaces templates/ + static/)
│   ├── src/
│   │   ├── pages/            # Upload, Schedule, Analytics, Settings
│   │   ├── components/
│   │   ├── api/               # fetch wrappers / TanStack Query hooks
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
├── data/                      # SQLite DB, uploaded reels, logs (unchanged)
├── docs/                      # this file, API.md, TIMELINE.md, HANDOFF.md, SETUP.md
└── requirements.txt
```

The old `frontend/templates/` and `frontend/static/` (Bootstrap/Jinja) should be removed once the React app covers the same pages — keep them only as reference until parity is confirmed.

---

## Media Upload — Design Notes (highest-risk area)

Since the user explicitly flagged media uploads (images + video) as the core concern:

1. **Client side:** validate file type/extension and rough size limit before upload starts. Show a progress bar using `fetch` with a `ReadableStream` or `XMLHttpRequest.upload.onprogress` (fetch doesn't expose upload progress natively — XHR is the pragmatic choice here).
2. **Server side:** stream the multipart body directly to disk (Flask + `werkzeug` handles this by default when not fully buffering) rather than loading the whole file into memory — important for video files.
3. **Validation after write:** run `ffprobe` on the saved file to confirm duration/codec/resolution meet Instagram reel requirements. Reject and delete on failure, return a clear error to the React UI.
4. **Thumbnail generation:** run `ffmpeg` in a background thread (or a simple task queue) so the upload HTTP response returns quickly; poll or use a "processing" status in the UI until the thumbnail is ready.
5. **Cleanup:** failed/rejected uploads should not linger in `data/reels/` — delete on validation failure.

---

## API Contract

See `API.md` for the full endpoint list. For the 24h build, the React app only needs a subset — the rest of the original 25+ endpoints can stay dormant in `routes.py` (deferred, not deleted) for Phase 2+.
