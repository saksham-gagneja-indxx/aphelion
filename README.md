# Reel Automation

Upload a video once, and publish or schedule it to LinkedIn from a single
dashboard — with roles, approvals, and an audit trail for every post.

**Frontend:** deployed on Vercel · **Backend:** run locally (`python -m backend.app`)

> Render deployment is switched off — `render.yaml` is commented out. The
> Vercel build needs `VITE_API_URL` pointing at the backend, and the backend
> needs that Vercel origin in `CORS_ORIGINS`.

For how any of it works internally, see **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

---

## Status

| Capability | State |
|---|---|
| Video upload (drag-drop, progress, validation, thumbnails) | ✅ working |
| **Publish to LinkedIn now** | ✅ **proven against the live API** |
| Schedule a post for later | ✅ working |
| Retract (delete) a published post | ✅ working |
| Queue — every post from draft to published, with failure reasons | ✅ working |
| Sign in with LinkedIn (OAuth 2.0) | ✅ working |
| Roles, user approval, admin panel | ✅ working |
| Audit log (who published what, when) | ✅ working |
| Analytics | ⚠️ scaffolded — no real LinkedIn metrics yet |
| **Scheduled posts firing on time** | ⚠️ needs an always-on instance — a post due while the free instance is asleep publishes when it next wakes (within an hour) or is reported as failed |
| Publish to Instagram | ⛔ blocked on Meta App Review |
| Publish to a **company page** | ⛔ blocked on LinkedIn partner approval |
| AI caption assist | ✅ working — three drafts from your one-line brief; needs a real `CLAUDE_API_KEY` |

**Tests:** 107 backend (pytest) + 27 frontend (vitest), all passing.

---

## How it got here

The project started as an **Instagram** automation agent built on `instagrapi`
— a reverse-engineered client that logs in with a username and password.

That approach was abandoned before it ever ran against a real account. It
violates Instagram's Terms of Service, and automated posting through an
unofficial client is a well-documented route to account suspension. The
requirement was explicitly *no risk of a ban*, and `instagrapi` could not meet
it at any level of care.

The project pivoted to **LinkedIn via its official REST API**, which offers
what Instagram's self-serve tier does not: OAuth 2.0, a scope limited strictly
to publishing (`w_member_social`), a documented video pipeline, and no password
ever touching the application.

Everything above the platform boundary was written against a `Publisher`
interface rather than a specific SDK, so Instagram can be re-enabled later
through the official Graph API without the rest of the system changing. That
scaffold exists today and is deliberately switched off.

### Milestones

| | |
|---|---|
| Instagram agent, scheduler, upload pipeline, analytics scaffold | initial build |
| **Pivot** — LinkedIn publishing via the official API, `instagrapi` removed | `da9042a` |
| API locked down: bearer-token gate, CORS restricted, OAuth state signed | `6033b55` |
| Multi-user: LinkedIn SSO, roles, admin API, audit log, Postgres | `ec66053` |
| Admin pinned to a LinkedIn identity allowlist | `62b580c` |
| SPA served by Flask, one Docker image, deployed | `66f522a` |
| Database password removed from an API response | `7bab260` |
| Publish-now and retraction endpoints | `87253e7` |
| Session token attached to uploads and every client call | `12c2ec3` |
| Schedule page auth fixed; uploads survive navigation; post-now UI | `656bc67` |

---

## The flow

```
  Upload                Schedule  ──or──  Post now
    │                       │                 │
    │  browser validates    │                 │
    │  duration + size      │                 │
    ▼                       ▼                 ▼
  server re-validates    APScheduler      publish immediately
  with ffprobe           fires at the          │
  generates thumbnail    chosen time           │
    │                       └────────┬─────────┘
    ▼                                ▼
  reel on disk                  LinkedIn Publisher
                                     │
                    initialize → upload parts → finalize
                       → poll until transcoded → create post
                                     │
                                     ▼
                          Queue + audit log updated
```

Client-side validation runs before a single byte is uploaded, so an
obviously-wrong file fails in milliseconds instead of after a 16 MB transfer.
The server never trusts it and re-validates with `ffprobe` regardless.

An upload keeps running if you navigate to another page — its state lives
outside React, so leaving the Upload page and coming back shows the transfer
still in progress rather than an empty dropzone.

---

## Quick start

**Prerequisites:** Python 3.12+, Node 20+, and ffmpeg/ffprobe on `PATH`
(without them, uploads still work but duration checks are skipped and no
thumbnail is generated).

```bash
git clone https://github.com/saksham-gagneja-indxx/social-media-manager.git
cd social-media-manager

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
pip install -r requirements-dev.txt   # pytest, for running the tests

cp .env.example .env
```

Generate two **different** secrets and put them in `.env`:

```bash
python -c "import secrets; print('API_ACCESS_KEY=' + secrets.token_urlsafe(40))"
python -c "import secrets; print('SECRET_KEY='    + secrets.token_urlsafe(48))"
```

The app refuses every API request with `503` if `API_ACCESS_KEY` is unset. That
is deliberate — see [ARCHITECTURE.md](docs/ARCHITECTURE.md#failing-closed).

### LinkedIn app

Create an app at [linkedin.com/developers/apps](https://www.linkedin.com/developers/apps)
(it must be attached to a Company Page), then add **both** products:

- *Sign In with LinkedIn using OpenID Connect* → grants `openid`, `profile`
- *Share on LinkedIn* → grants `w_member_social`

Register the redirect URL **exactly**, including scheme and path:

```
http://localhost:5000/api/auth/linkedin/callback
```

Then fill in `.env`:

```ini
LINKEDIN_CLIENT_ID=...
LINKEDIN_CLIENT_SECRET=...
LINKEDIN_REDIRECT_URI=http://localhost:5000/api/auth/linkedin/callback
LINKEDIN_API_VERSION=202607
CORS_ORIGINS=http://localhost:5173
TIMEZONE=Asia/Kolkata
```

There is deliberately **no `LINKEDIN_PASSWORD`**. Publishing authority comes
from the member granting `w_member_social` through OAuth. Never add one.

### Run it

```bash
python -m backend.app                 # API on :5000
cd frontend && npm install && npm run dev   # SPA on :5173
```

Open `http://localhost:5173` and sign in with LinkedIn. The first account
becomes an active admin; everyone after that is created inactive and needs
approving from the Admin panel.

### Tests

```bash
pytest tests/ -q                 # 107 backend tests
cd frontend
npx tsc --noEmit                 # types
npx vitest run                   # 27 frontend tests
npm run build                    # the build Docker will run
```

Run all four before merging to `main` — it deploys straight to production.

---

## What it cannot do yet

**Instagram publishing** needs Meta App Review for
`instagram_business_content_publish` (2–4 weeks, and a separate submission per
scope), an Instagram *Business* account — Creator accounts cannot publish via
the API — and publicly reachable HTTPS media URLs, because Meta fetches the
file itself rather than accepting an upload. Local disk storage cannot satisfy
that; it needs object storage first.

**Company page publishing** needs `w_organization_social`, part of LinkedIn's
partner-gated Community Management API — a registered company, a verified
Page, and a two-tier review. Personal-profile publishing is the self-serve
tier and is what works today. The code difference is one field: the author URN
becomes `urn:li:organization:{id}` instead of `urn:li:person:{id}`.

**Real analytics** — the Analytics page is scaffolded against a seeded
engagement model, not live LinkedIn metrics.

---

## Known limitations

| Limitation | Impact |
|---|---|
| Free Render tier sleeps after ~15 min idle | **scheduled posts cannot fire while asleep** — the paid tier fixes this |
| Uploaded videos sit on ephemeral disk | media is lost on redeploy; the database is external and unaffected |
| Access tokens stored unencrypted | anyone with database access can read them |
| No rate limiting | nothing throttles repeated requests |
| Browser flags the `onrender.com` domain | a custom domain is the real fix |

---

## Repository layout

```
backend/
  api/          routes, auth, admin, publish endpoints
  core/
    publishers/ the platform seam — base, linkedin, instagram
    scheduler.py, reel_manager.py, analytics_engine.py
  models/       User, Post, Analytics, AuditLog
  utils/        security, config, database, logging, time
frontend/src/
  api/          typed client modules, upload store
  pages/        Upload, Schedule, Queue, Analytics, Settings, Admin
  components/
tests/          107 backend tests
docs/
  ARCHITECTURE.md   everything technical
Dockerfile      multi-stage: Node builds the SPA, Python serves it
render.yaml     deployment config
```
