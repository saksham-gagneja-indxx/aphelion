# Social Media Manager

A social media automation tool for scheduling and publishing short-form video.
Flask JSON API backend, React (Vite + TypeScript) single-page frontend.

> **Current status:** **LinkedIn publishing works end-to-end** via LinkedIn's
> official versioned REST API using OAuth 2.0. **Instagram publishing is
> scaffolded but disabled** — it is blocked on Meta App Review and an
> architecture change for publicly-hosted media. See
> [Platform support](#platform-support) for exactly what that means.

---

## What it does

| Feature | Status |
|---------|--------|
| **Upload** — drag-and-drop reels, server-side validation, background thumbnail extraction | ✅ Working |
| **Schedule** — pick a reel, set date/time, create an APScheduler job | ✅ Working |
| **Queue** — all posts (draft → scheduled → posted/failed/cancelled) with failure details | ✅ Working |
| **LinkedIn publishing** — video upload + post creation via the official API | ✅ Working |
| **LinkedIn OAuth** — member authorizes the app; no password is ever handled | ✅ Working |
| **API authentication** — bearer token required on every `/api/*` route | ✅ Working |
| **Analytics** — engagement metrics, best posting hours/days | ✅ Working (seeded data) |
| **Settings** — connection status per platform | ✅ Working |
| **Instagram publishing** | ⛔ Disabled — see below |
| **AI captions** — Claude-powered generation | ❌ Not implemented |

---

## Platform support

### LinkedIn ✅

Uses the official **Posts API** and **Videos API** with the `w_member_social`
scope, obtained through the self-serve *Share on LinkedIn* product — no partner
review required.

Publishing flow:
1. `initializeUpload` → video URN + byte-range upload instructions
2. `PUT` each byte range to its pre-signed URL, collecting the `ETag` per part
3. `finalizeUpload` → links the parts together
4. Poll the video until `AVAILABLE` (transcoding is asynchronous)
5. `POST /rest/posts` → the post URN arrives in the `x-restli-id` header

Limits enforced locally before upload: MP4 only, 3s–30min, 75KB–500MB.

### Instagram ⛔

Deliberately disabled. `InstagramPublisher` reports this honestly rather than
failing at post time. Three things block it:

- **Meta App Review** for `instagram_business_basic` and
  `instagram_business_content_publish` — 2–4 weeks, separate submission each
- **Instagram Business account** required; Creator accounts cannot publish
  via API
- **Publicly reachable HTTPS media URLs** — Meta *pulls* the file from a URL
  you host, so local disk storage is insufficient. Needs object storage.

The previous `instagrapi` integration was **removed, not disabled**. It
authenticates with a username and password, which violates Instagram's Terms of
Service and risks suspension of the account being posted to — an unacceptable
risk for client accounts. See [`docs/SECURITY.md`](docs/SECURITY.md).

---

## Architecture

```
┌──────────────────────────────────┐
│  React SPA (Vite, :5173)         │  ← Browser
│  TypeScript + Tailwind CSS       │
│  TanStack Query for server state │
└──────────────┬───────────────────┘
               │ fetch() + Bearer token
               ▼
┌──────────────────────────────────┐
│  Flask JSON API (:5000)          │
│  API key gate (before_request)   │
│  APScheduler (in-process)        │
│  SQLite (data/automation.db)     │
│  Local file storage (data/reels/)│
└──────────────┬───────────────────┘
               │ Publisher interface
       ┌───────┴────────┐
       ▼                ▼
┌─────────────┐  ┌─────────────────┐
│  LinkedIn   │  │  Instagram      │
│  (official  │  │  (scaffolded,   │
│   REST API) │  │   disabled)     │
└─────────────┘  └─────────────────┘
```

### The Publisher seam

Everything above `backend/core/publishers/` talks to the `Publisher` interface
and never to a platform SDK. The scheduler resolves a publisher from
`post.platform` and records the result — it contains no LinkedIn- or
Instagram-specific code.

That is what let LinkedIn ship while Instagram waits on review: adding a
platform is a new class plus a registry entry, not a rewrite.

Implementations must **return** failures as `PublishResult.failure(...)` rather
than raising, so the scheduler can record a useful error on the post instead of
a traceback, and must mark `retryable=True` only for genuinely transient
conditions (5xx, timeouts, rate limits).

---

## Prerequisites

- **Python 3.12+** (developed on 3.13)
- **Node.js 20+** and npm
- **ffmpeg** / **ffprobe** — *optional*. Used for thumbnails and duration
  validation. Without them uploads still work; duration checks are skipped and
  the UI shows a placeholder thumbnail.
  - If not on `PATH`, set `FFMPEG_PATH` and `FFPROBE_PATH` in `.env`

---

## Setup

### 1. Clone

```bash
git clone https://github.com/saksham-gagneja-indxx/social-media-manager.git
cd social-media-manager
```

### 2. Backend

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt          # runtime only
pip install -r requirements-dev.txt      # + pytest, for running tests

cp .env.example .env
```

### 3. Required configuration

Generate two independent secrets:

```bash
python -c "import secrets; print(secrets.token_urlsafe(40))"   # API_ACCESS_KEY
python -c "import secrets; print(secrets.token_urlsafe(48))"   # SECRET_KEY
```

Set them in `.env`:

```ini
API_ACCESS_KEY=<first value>    # bearer token for every /api/* route
SECRET_KEY=<second value>       # signs OAuth state — must differ
CORS_ORIGINS=http://localhost:5173
TIMEZONE=Asia/Kolkata
```

**Without `API_ACCESS_KEY` the app returns 503 for all API requests.** This is
intentional — it fails closed rather than serving openly.

### 4. LinkedIn app

1. Create an app at <https://www.linkedin.com/developers/apps> (requires a
   LinkedIn Company Page)
2. On **Products**, add both:
   - *Sign In with LinkedIn using OpenID Connect* → `openid`, `profile`
   - *Share on LinkedIn* → `w_member_social`
3. On **Auth**, add an authorized redirect URL — matched as an exact string:
   ```
   http://localhost:5000/api/auth/linkedin/callback
   ```
4. Copy the Client ID and Secret into `.env`:
   ```ini
   LINKEDIN_CLIENT_ID=...
   LINKEDIN_CLIENT_SECRET=...
   LINKEDIN_REDIRECT_URI=http://localhost:5000/api/auth/linkedin/callback
   LINKEDIN_API_VERSION=202607
   ```

There is deliberately **no `LINKEDIN_PASSWORD`**. Publishing is OAuth-only.

### 5. Frontend

```bash
cd frontend && npm install && cd ..
```

---

## Running

Two terminals.

```bash
# Terminal 1 — backend
python -m backend.app

# Terminal 2 — frontend
cd frontend && npm run dev
```

Open <http://localhost:5173>.

### Connecting LinkedIn

Visit `/api/auth/linkedin/start?user_id=1`, click **Allow**. The callback stores
an access token (~60 days) and the member's person URN. Verify with:

```bash
curl -H "Authorization: Bearer $API_ACCESS_KEY" \
  "http://localhost:5000/api/auth/linkedin/status?user_id=1"
```

---

## Security

Authentication, credential handling, and known gaps are documented in
**[`docs/SECURITY.md`](docs/SECURITY.md)**. Summary:

- Bearer token on every `/api/*` route, enforced globally so new endpoints are
  protected by default, and **failing closed** when unset
- OAuth CSRF `state` is HMAC-signed and expiring, binding the `user_id` so it
  cannot be replayed against another account
- CORS restricted to configured origins, never `*`
- No social account passwords are stored, transmitted, or accepted anywhere

Read the **Known gaps** section before pointing this at an account you do not
personally own.

---

## Project structure

```
social-media-manager/
├── backend/
│   ├── api/
│   │   ├── routes.py            # Core HTTP endpoints
│   │   └── auth_routes.py       # LinkedIn OAuth flow
│   ├── core/
│   │   ├── publishers/          # ← platform seam
│   │   │   ├── base.py          # Publisher interface + PublishResult
│   │   │   ├── linkedin.py      # Official LinkedIn REST API
│   │   │   ├── instagram.py     # Scaffolded, disabled
│   │   │   └── __init__.py      # get_publisher() registry
│   │   ├── scheduler.py         # APScheduler; platform-agnostic
│   │   ├── reel_manager.py      # Upload validation, thumbnails
│   │   ├── agent.py             # Legacy Instagram agent (optional import)
│   │   └── analytics_engine.py
│   ├── models/                  # SQLAlchemy: User, Post, Analytics
│   ├── utils/
│   │   ├── security.py          # API key gate + signed OAuth state
│   │   ├── config.py            # Pydantic settings
│   │   ├── database.py          # Engine, session, additive migrations
│   │   └── timeutil.py          # utcnow() — naive UTC
│   └── app.py                   # App factory
│
├── frontend/src/
│   ├── api/                     # Fetch wrappers + types
│   ├── components/              # QueryStates, ErrorBoundary
│   └── pages/                   # Upload, Schedule, Queue, Analytics, Settings
│
├── docs/
│   ├── SECURITY.md              # ← authentication, credentials, known gaps
│   ├── ARCHITECTURE.md
│   └── API.md
├── tests/                       # pytest — publishers, security
├── render.yaml                  # Deployment config
└── requirements.txt             # Runtime deps only
```

---

## Testing

```bash
pytest tests/ -q                       # backend (42 tests)
cd frontend && npx vitest run          # frontend
cd frontend && npx tsc --noEmit        # type-check
```

Backend coverage focuses on the parts that are expensive to get wrong: byte-range
slicing and ETag handling in the LinkedIn upload, required API headers,
retryable-vs-permanent error classification, and the security gate (forged
state, expired state, missing key, fail-closed behaviour).

---

## Deployment

`render.yaml` configures a Render web service. Notes that matter:

- **`--workers 1` is required.** APScheduler runs in-process; multiple workers
  would each start a scheduler and fire every scheduled post once per worker.
- **Free tier sleeps after ~15 min idle**, so scheduled jobs will not fire
  reliably. Scheduling needs a paid instance or an external pinger.
- **Free tier storage is ephemeral** — uploads and the SQLite database are lost
  on restart. Production needs managed Postgres and object storage.
- `LINKEDIN_REDIRECT_URI` must match the deployed callback URL *and* be
  registered in the LinkedIn app.

---

## Current limitations

1. **Instagram publishing is disabled** — see [Platform support](#platform-support).
2. **Single shared API key.** No per-operator identity or audit trail. The
   natural next step is LinkedIn OpenID Connect as the identity provider,
   reusing the OAuth integration already built.
3. **`user_id` is a client-supplied parameter**, so any authenticated caller can
   act as any user. Resolved once identity comes from a session.
4. **SQLite only.** Fine for development; production needs Postgres.
5. **In-process scheduler.** Jobs reload from the DB on restart, but timing may
   drift, and the process must stay alive.
6. **No AI features.** Claude integration is scaffolded, not implemented.

---

## License

Private — not open-source at this time.
