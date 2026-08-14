# Handoff — Continue This Build in Claude Code

**Context:** This project started as an 8-week phased Instagram automation build in a cloud sandbox session. The deadline changed to **24 hours**, the frontend requirement changed to **React** (from Bootstrap/Jinja), and the core concern is **reliable media (image/video) upload handling**. Cloud sandbox constraints (no real Instagram auth testing, no persistent local server, awkward media pipeline testing) made it impractical to finish there, so the work is continuing here, in Claude Code, on the user's local machine.

Read these in order before making changes:

1. `docs/TIMELINE.md` — the 24-hour build plan (hour-by-hour), what's cut from the original scope
2. `docs/ARCHITECTURE.md` — what's changing (React replaces Bootstrap/Jinja) and what's staying (the Flask service layer)
3. `IMPLEMENTATION_COMPLETE.md` — full inventory of what was already built (23 files, ~5,000 LOC) in the original session — most of the backend is reusable
4. `docs/API.md` — existing endpoint reference (will be trimmed, not rewritten from scratch)
5. `docs/SETUP.md` — original setup instructions (still mostly valid for the backend half)

---

## What Already Exists (from the cloud session)

**Backend — reusable largely as-is:**
- `backend/core/agent.py` — InstagramAgent (auth, post_reel, get_recent_posts, get_engagement_data, get_followers_count, get_status)
- `backend/core/scheduler.py` — SmartScheduler on APScheduler (schedule_post, schedule_at_optimal_time, cancel_post, get_scheduled_posts)
- `backend/core/reel_manager.py` — ReelManager (upload_reel, validate_video, thumbnail generation via ffmpeg, cleanup)
- `backend/core/analytics_engine.py` — AnalyticsEngine (engagement analysis, optimal posting time, confidence scoring)
- `backend/models/user.py`, `post.py`, `analytics.py` — SQLAlchemy models
- `backend/utils/config.py`, `logger.py`, `database.py` — config/logging/DB plumbing
- `backend/api/routes.py` — 25+ Flask endpoints (JSON already — just needs CORS + trimming)

**Frontend — being replaced, not reused:**
- `frontend/templates/*.html` (Bootstrap/Jinja) and `frontend/static/` (CSS/JS) — keep only as a feature-parity reference while building the React app, then delete.

**What's NOT built yet and is the actual remaining work:**
- The React app itself (nothing exists yet — `frontend/` needs a full Vite + TypeScript scaffold)
- CORS setup on the Flask side
- Streaming multipart upload endpoint hardening (current `reel_manager.py` upload path was written for template-based forms, not a decoupled SPA — verify it handles direct multipart POSTs from `fetch`/`XMLHttpRequest` cleanly)
- Client-side upload validation + progress UI
- End-to-end real Instagram auth test (never tested with real credentials in the cloud session — user said they'd provide credentials only during local testing)

---

## Known Risk Areas (budget time here first)

1. **instagrapi + real credentials.** Never tested end-to-end. 2FA/challenge flows are a common failure point — if the user's account triggers a checkpoint, that alone can eat hours. Test this early, not at hour 20.
2. **Media upload pipeline.** User explicitly called this out as the core concern. Don't let it be an afterthought — see the "Media Upload — Design Notes" section in `docs/ARCHITECTURE.md`.
3. **ffmpeg/ffprobe availability.** `reel_manager.py` shells out to these — confirm they're installed on the local machine before relying on thumbnail/validation logic.

---

## Suggested First Actions in Claude Code

1. Confirm the local folder structure matches (or migrate from) what's described above.
2. Install backend deps (`requirements.txt`) and confirm the Flask app boots locally.
3. Scaffold the React app (Vite + TypeScript + Tailwind + TanStack Query) inside `frontend/`.
4. Add CORS to Flask, trim `routes.py` to the endpoints in the "Hour 1–4" section of `TIMELINE.md`.
5. Build the upload flow end-to-end (React → Flask → disk → ffprobe validation) before building the rest of the UI — it's the highest-risk piece and blocks everything downstream (scheduling needs a valid uploaded file to schedule).
6. Only after upload + basic scheduling work: layer in the optimal-time heuristic, analytics display, and settings page.

---

## What NOT to Rebuild From Scratch

The service layer (agent/scheduler/reel_manager/analytics_engine) and DB models represent real, tested design work — reuse them. The only mandatory rewrite is the presentation layer (Bootstrap → React) and the upload path hardening. Don't re-derive the Instagram posting logic or scheduling logic from scratch; read the existing files first.
