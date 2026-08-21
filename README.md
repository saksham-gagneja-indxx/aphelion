# Aphelion

Upload a video once, and publish or schedule it to LinkedIn from a single
dashboard — with roles, approvals, and an audit trail for every post.

**Frontend:** Vercel · **Backend:** Render (`render.yaml`), or locally with
`python -m backend.app`

> Frontend and backend are on different origins, so three settings have to
> agree or sign-in breaks in ways that do not point at the cause:
> `VITE_API_URL` on Vercel (inlined at **build** time — changing it needs a
> redeploy, not a restart), the Vercel origin in `CORS_ORIGINS` on the backend,
> and `LINKEDIN_REDIRECT_URI` matching the LinkedIn app's authorized redirect
> URL character for character.

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
| Delete a reel or post, reversible for 15 seconds | ✅ working |
| Sign in via Clerk (LinkedIn, Google, GitHub, Apple, Microsoft) | ✅ working |
| Guest accounts — try it without LinkedIn, cannot publish | ✅ working |
| Operations console (`/console`) — scheduler, storage, feature flags | ✅ working |
| Guided setup that checks each step, including the publish scope | ✅ working |
| Roles, user approval, admin panel | ✅ working |
| Audit log (who published what, when) | ✅ working |
| Analytics | ⚠️ scaffolded — no real LinkedIn metrics yet |
| **Scheduled posts firing on time** | ⚠️ needs an always-on instance — a post due while the free instance is asleep publishes when it next wakes (within an hour) or is reported as failed |
| Publish to Instagram | ⛔ blocked on Meta App Review |
| Publish to a **company page** | ⛔ blocked on LinkedIn partner approval |
| AI caption assist | ✅ working — three drafts from your one-line brief; needs a real API key for whichever `LLM_PROVIDER` is set |
| **Assistant** — say what you want, get a finished draft | ✅ working — a popover on New post, not a separate page. Picks the reel, writes the caption, proposes a time, live in the same form. It cannot publish; you press the button |
| Automatic thumbnail choice | ✅ working — samples and scores frames instead of grabbing a black one |
| Reels persist across sign-out, ready for object storage | ✅ working — `MEDIA_BACKEND=local` today |

**Tests:** 253 backend (pytest) + 36 frontend (vitest), all passing. CI runs
both on every push to `main`.

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

One screen (`/compose`): pick a video — a new upload or one already there —
write a caption, then choose *post now* or *schedule for later*.

```
  Video                 Schedule  ──or──  Post now
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
outside React, so leaving and coming back shows the transfer still in progress
rather than an empty dropzone.

Deleting a reel or a post is reversible for 15 seconds: nothing is sent until
the window closes, so the undo is real rather than a compensating delete. A
reel that a not-yet-published post still points at is refused outright.

---

## Quick start

**Prerequisites:** Python 3.12+, Node 20+, and ffmpeg/ffprobe on `PATH`
(without them, uploads still work but duration checks are skipped and no
thumbnail is generated).

```bash
git clone https://github.com/saksham-gagneja-indxx/aphelion.git
cd aphelion

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

### Clerk (sign-in)

Create an app at [dashboard.clerk.com](https://dashboard.clerk.com), then set:

```ini
VITE_CLERK_PUBLISHABLE_KEY=pk_...
CLERK_SECRET_KEY=sk_...
ADMIN_CLERK_EMAILS=you@example.com
```

Two dashboard settings are easy to miss and both fail *silently* — sign-in
just 404s or bounces to a `*.accounts.dev` page with no useful error, on
every provider, which looks exactly like a broken OAuth app and isn't:

1. **Organizations → Settings → "Force organization selection" must be OFF.**
   This app has no use for Clerk's Organizations feature; leaving this on
   sends every sign-in through a hosted "choose an organization" step this
   app never deploys a page for, and it 404s.
2. **To offer LinkedIn as a sign-in option**, open **User & Authentication →
   Social Connections → LinkedIn**, enable **"Use custom credentials,"** and
   paste in the same `LINKEDIN_CLIENT_ID`/`LINKEDIN_CLIENT_SECRET` from the
   section below, with `openid`, `profile`, `email` added under Scopes.
   Clerk has shared dev credentials for Google/GitHub/Microsoft/Apple, but
   not LinkedIn — without this the icon renders but 404s on click. Also add
   the redirect URL that page shows you
   (`https://<your-instance>.clerk.accounts.dev/v1/oauth_callback`) to that
   same LinkedIn app's **Authorized redirect URLs** below — it supports more
   than one.

### LinkedIn app

Needed regardless of Clerk: it's what grants **publish rights** later, in
Setup — a separate permission from signing in. Create an app at
[linkedin.com/developers/apps](https://www.linkedin.com/developers/apps)
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

Open `http://localhost:5173` and sign in. With `ADMIN_CLERK_EMAILS` set to
your email, you land as an active admin immediately; otherwise the first
account becomes admin and everyone after needs approving from the Admin
panel — see [ARCHITECTURE.md](docs/ARCHITECTURE.md#who-becomes-an-admin).

### Tests

```bash
pytest tests/ -q                 # 253 backend tests
cd frontend
npx tsc -b                       # types — NOT `tsc --noEmit`: this repo's root
                                  # tsconfig.json has "files": [], so bare
                                  # --noEmit checks nothing at all and reports
                                  # clean regardless of real errors. `tsc -b`
                                  # (also what `npm run build` runs) is the
                                  # one that actually respects the project
                                  # references and catches something.
npx vitest run                   # 36 frontend tests
npm run build                    # the build Docker will run
```

Run all four before merging to `main` — it deploys straight to production. CI
runs the same checks on every push.

---

## Becoming the administrator

The admin role is pinned to a LinkedIn identity (`ADMIN_LINKEDIN_SUBS`, keyed
on the OIDC `sub` claim). That claim is not knowable until the person has
signed in once, so there is a chicken-and-egg step:

```bash
python -m backend.admin_cli list           # who exists
python -m backend.admin_cli reset-users --yes   # only if the DB has test accounts
# → sign in with LinkedIn. The first account on an empty database becomes an
#   active admin.
python -m backend.admin_cli pin            # writes that account's sub to .env
```

`pin` closes the bootstrap permanently: the "first account wins" rule turns
off, and the role is re-asserted on every sign-in — so editing the database by
hand cannot take it away, and nobody else can claim it even on an empty
database. Restart the server afterwards.

Everyone who signs in after that is created **inactive** and appears in the
Admin panel's approval queue, with a count on the nav item. Until approved,
their session is refused on every request.

Other commands:

```bash
python -m backend.admin_cli promote <id|email>
python -m backend.admin_cli demote  <id|email>   # refuses the last admin
python -m backend.admin_cli sign-out-all --yes   # rotates SECRET_KEY
python -m backend.admin_cli purge-guests --yes
```

`sign-out-all` works because session tokens are stateless and signed with
`SECRET_KEY` — there is no session table to clear, so rotating the key is what
invalidates every issued token at once.

---

## Guest accounts

A visitor can try the tool without a LinkedIn account. A guest is an ordinary
account with an ordinary session — not a bypass — and every existing guard
applies to it unchanged. What makes it safe to offer publicly is what it
cannot reach:

- **Cannot publish.** Publishing acts on a real LinkedIn profile, and a guest
  has not proved they own one. Enforced across the whole publish blueprint, so
  a route added later is covered by default.
- **Can never be an administrator.** `User.is_admin()` returns `False` for a
  guest regardless of the role column, so a guest promoted by a bad migration
  or a future admin screen still reaches nothing.
- **Sees only its own data**, through the same ownership guard as everyone.

Each request creates a *new* account rather than sharing one — two people
trying the tool at once would otherwise see each other's uploads.

Set `ALLOW_GUEST_ACCESS=false` to require LinkedIn for everyone. Guests
accumulate one row per visitor; clear them from `/console` or with
`admin_cli purge-guests --yes`.

---

## Two admin surfaces

They answer different questions, so they are different pages:

| | |
|---|---|
| **`/admin`** | People. Who exists, what role they hold, who is awaiting approval, and the audit log. |
| **`/console`** | The deployment. Scheduler state, storage and orphaned files, database counts, feature flags, maintenance. |

Both are restricted to administrators by a blueprint-level guard on the server,
not only hidden in the UI.

The console reports scheduler **enabled** and scheduler **running** separately.
On a sleeping free instance the config says yes while the process is not there,
which looks configured and silently publishes nothing — that gap is the most
misleading state this system has.

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
| The API is not hosted — it runs locally | **scheduled posts only fire while the process is up**; a missed post publishes on the next start within the grace window, or is marked failed |
| Uploaded videos sit on the local filesystem | they survive sign-out and restarts, but not a cleaned working directory. `MEDIA_BACKEND=object` is the seam for fixing that |
| Access tokens stored unencrypted | anyone with database access can read them |
| Rate limits are counted in one process | accurate today (the app runs a single worker so the scheduler does not double-publish), but they would multiply if that ever changed |
| Anonymous rate limits key on the client IP | an office or campus behind one NAT shares a counter, so the guest sign-in allowance is deliberately generous rather than tight |
| The SPA and the API are on different origins | `CORS_ORIGINS` and `VITE_API_URL` both have to be set, or nothing talks to anything. In production `CORS_ORIGINS` **must** name the real frontend URL — a `localhost` value is now refused and every request is blocked |

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
  pages/        Compose, Queue, Analytics, Setup, Docs, Settings, Admin, Console
  components/
tests/          253 backend tests
docs/
  ARCHITECTURE.md   everything technical
Dockerfile      multi-stage: Node builds the SPA, Python serves it
render.yaml     deployment config (commented out — backend is not hosted)
```
