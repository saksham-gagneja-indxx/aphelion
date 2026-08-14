# 24-Hour Sprint Timeline

## Project Overview
**Project Name:** Social Media Automation Agent (Instagram Reel Automation)
**Scope Change:** Original plan was an 8-week, 4-phase build (Instagram → AI → LinkedIn → Ideation). Deadline changed to **24 hours**, so scope has been cut hard to a single working slice: upload media, schedule it, auto-post to Instagram, see basic analytics.
**Frontend Change:** Original Bootstrap/Jinja templates are replaced with **React + Vite + TypeScript**. The Flask backend becomes a pure JSON API.
**Deployment Target:** Local machine only for the 24-hour build (cloud deploy is explicitly out of scope for v1).

---

## What Got Cut From the 8-Week Plan

These are deliberately deferred, not lost — they're still described in `IMPLEMENTATION_COMPLETE.md` and the original `backend/` modules for later phases:

- LinkedIn integration (Phase 3)
- AI caption/hashtag generation, comment sentiment, auto-reply (Phase 2)
- Content ideation engine (Phase 4)
- JWT auth, PostgreSQL, Docker, Alembic migrations
- Bootstrap/Jinja dashboard (replaced by React)

---

## 24-Hour Build Plan

### Hour 0–1: Environment & Scope Lock
- Confirm folder structure in the local project (the one opened in Claude Code)
- Decide: SQLite only, no auth, single local user, Flask JSON API + React SPA
- Install backend deps (Flask, SQLAlchemy, APScheduler, instagrapi, ffmpeg-python or subprocess ffmpeg)
- Scaffold React app with Vite + TypeScript + Tailwind + TanStack Query

### Hour 1–4: Backend Core (reuse from Phase 1 build)
- Port over `backend/core/agent.py` (Instagram auth/post/fetch) — trim to essentials
- Port over `backend/models/` (User, Post) — drop Analytics complexity if time-constrained, keep basic fields
- Port over `backend/utils/config.py`, `logger.py`, `database.py` — keep, they're small and solid
- Strip `backend/api/routes.py` down to the endpoints the React app actually calls (see API.md)

### Hour 4–8: Media Upload Pipeline (highest risk area)
- Multipart upload endpoint with streaming write-to-disk (avoid loading full file in memory)
- Client-side validation in React (file type, size, duration if readable) before upload starts
- Server-side validation with ffprobe (duration, codec, resolution) — reject fast, don't queue a bad file into the scheduler
- Background thread/queue for thumbnail generation (ffmpeg) — never block the upload response on ffmpeg
- Progress feedback to the user (upload % via XHR/fetch progress or chunked upload)

### Hour 8–12: Scheduling
- Reuse `backend/core/scheduler.py` (APScheduler) — simplify persistence if needed (DB-backed job store is fine, skip anything fancier)
- Manual scheduling (pick a time) working end-to-end first
- Optimal-time suggestion as a secondary feature, not a blocker — a simple "best of last N posts' hour" heuristic is enough for v1, not a full analytics engine

### Hour 12–18: React Frontend
- Pages: Upload/Queue, Schedule view, basic Analytics (recent post stats), minimal Settings (Instagram connect)
- TanStack Query for all API state, no Redux needed at this scope
- Tailwind for styling — skip design polish, prioritize working flows
- Drag-and-drop or file-picker upload component with progress bar

### Hour 18–21: Instagram Auth + End-to-End Test
- Real credential test: login, post one real reel on a schedule, confirm it goes live
- Handle 2FA/challenge flows from instagrapi if they show up (common blocker — budget time here)
- Verify session persistence works across restarts

### Hour 21–23: Hardening
- Error states in the UI (failed upload, failed auth, failed post)
- Basic logging check — confirm logs are actually useful for debugging post-deadline
- Remove/guard any half-built endpoints so they fail loud, not silently

### Hour 23–24: Wrap-up
- Update README/SETUP with the real run steps used
- Note any known gaps for the next session

---

## Explicit Non-Goals for v1 (24h)

- Multi-user support
- Production deployment / HTTPS / real auth
- LinkedIn, AI features, ideation engine
- Polished analytics (charts can come later — raw numbers are enough)
- Comment monitoring / auto-reply

---

## Post-Deadline Roadmap (unchanged from original phases, renumbered)

1. **Phase 2:** AI captions/hashtags, better analytics engine, comment sentiment
2. **Phase 3:** LinkedIn cross-posting
3. **Phase 4:** Content ideation engine, trend monitoring

See `IMPLEMENTATION_COMPLETE.md` for the full original feature list — most of it is still valid reference material, just not in scope for the next 24 hours.
