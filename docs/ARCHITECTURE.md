# Architecture

Everything technical about the system: how it is put together, why it is put
together that way, and what is deliberately not solved yet.

For what the product does and how to run it, see the [README](../README.md).

---

## Contents

1. [System shape](#system-shape)
2. [Request lifecycle](#request-lifecycle)
3. [Authentication](#authentication)
4. [Identity and roles](#identity-and-roles)
5. [Data model](#data-model)
6. [The Publisher seam](#the-publisher-seam)
7. [LinkedIn publishing pipeline](#linkedin-publishing-pipeline)
8. [Upload pipeline](#upload-pipeline)
9. [Scheduling](#scheduling)
10. [Audit log](#audit-log)
11. [API reference](#api-reference)
12. [Frontend](#frontend)
13. [Deployment](#deployment)
14. [Branching](#branching)
15. [Testing](#testing)
16. [Security posture](#security-posture)
17. [Operations](#operations)

---

## System shape

One Docker image serves both the API and the compiled SPA from a single origin.

```
                    ┌────────────────────────────────────────┐
   browser  ───────▶│  Flask  (gunicorn, exactly 1 worker)   │
                    │                                        │
                    │  before_request ─ auth gate            │
                    │        │                               │
                    │        ├─ /api/*  ── blueprints        │
                    │        │            routes / auth /    │
                    │        │            admin / publish    │
                    │        │                               │
                    │        └─ everything else ── SPA       │
                    │                    (index.html)        │
                    │                                        │
                    │  APScheduler (in-process)              │
                    │  Publisher interface                   │
                    └───────┬────────────────────┬───────────┘
                            │                    │
                   ┌────────▼────────┐   ┌───────▼────────┐
                   │ Supabase        │   │ LinkedIn REST  │
                   │ Postgres        │   │ API            │
                   └─────────────────┘   └────────────────┘
```

**Why one image rather than separate frontend and backend services.** The API
contract spans both halves: when a response shape changes, the UI consuming it
must change in the same commit. Split across deployments there is always a
window where production is inconsistent, and rolling back fixes only one side.
Same-origin also means CORS stops applying to the SPA entirely, there is one
domain to secure and build reputation for, and it fits in one free instance.

**Why exactly one gunicorn worker.** APScheduler runs inside the process. A
second worker would start a second scheduler, and every scheduled post would
fire once per worker — publishing duplicates to a real person's feed. This
constraint is load-bearing; changing `--workers` without moving the scheduler
out of process is a publishing bug.

---

## Request lifecycle

```
request
  │
  ├─▶ before_request: enforce_authentication()
  │     ├─ public path?            → continue
  │     ├─ valid API key?          → continue as machine caller
  │     ├─ valid session token?    → load user, continue
  │     └─ otherwise               → 401 (or 503 if the key is unconfigured)
  │
  ├─▶ before_request: log_request()
  │
  ├─▶ blueprint route  ── or ──  SPA fallback
  │
  └─▶ after_request: log_response()
```

The auth gate is a global `before_request` hook rather than per-route
decorators. A decorator has to be remembered on every new endpoint; a hook
protects anything added later by default. Endpoints opt *out* via an explicit
allowlist, so forgetting to think about auth fails safe.

### SPA fallback

`static_folder` is disabled on the Flask app. Setting it with
`static_url_path=""` makes Flask register its own `/<path:filename>` rule,
which matches client-side routes like `/admin` *before* the fallback and 404s
because no such file exists — breaking every deep link and hard refresh.
Serving files explicitly keeps routing precedence in one place.

The fallback refuses `/api/*` and `/health` explicitly. Without that, a typo in
an endpoint path would return `index.html` with status 200, and the browser
would report a confusing `unexpected token <` JSON parse error instead of a
clear 404.

---

## Authentication

Two credential types are accepted, both compared in constant time via
`hmac.compare_digest`, both header-only — never query strings, which leak into
logs, browser history, and referrer headers.

| Type | Header | Who uses it |
|---|---|---|
| API key | `Authorization: Bearer <API_ACCESS_KEY>` or `X-API-Key` | scripts, CI, admin tooling |
| Session token | `Authorization: Bearer <signed token>` | the browser, after LinkedIn sign-in |

### Failing closed

If `API_ACCESS_KEY` is unset, every `/api/*` request returns **503** rather
than being allowed through. A misconfigured deployment is unavailable rather
than silently public — the failure mode that gets noticed immediately instead
of the one that gets noticed in a breach report.

### Public paths

Only three, each for a specific reason:

| Path | Why it must be public |
|---|---|
| `/health` | Render's health probe carries no credentials |
| `/api/auth/linkedin/login` | the entry point to signing in — the user has no token yet |
| `/api/auth/linkedin/callback` | LinkedIn redirects the browser here; protected by signed state instead |

### Session tokens

Stateless and self-verifying:

```
token = base64url(payload) . base64url(HMAC-SHA256(payload, SECRET_KEY))
payload = {"uid": <user id>, "exp": <unix expiry>, "typ": "session", "nonce": ...}
```

The signature is verified **before** the payload is parsed, so malformed input
never reaches the JSON decoder. Expiry is checked on every request, and the
user is re-loaded from the database each time — so deactivating an account
takes effect immediately rather than when a cached token expires.

### The `typ` claim

OAuth state tokens are signed with the same key and the same construction, but
carry `"typ": "oauth"` and a 10-minute lifetime. Session verification rejects
anything without `"typ": "session"`.

Without that claim an OAuth state token — which appears in URLs, browser
history, and server logs — could be replayed as a session token. The two
token types are deliberately not interchangeable, and there is a test for it.

### OAuth CSRF

The `state` parameter is a signed token carrying the user id and an expiry,
not a random value stored in a session. That keeps the callback stateless
while still binding the redirect to the request that started it. A forged or
expired state is rejected before any token exchange happens.

---

## Identity and roles

Sign-in is LinkedIn OpenID Connect. The `sub` claim — LinkedIn's stable
subject identifier — is the login key, stored as `users.linkedin_sub`. Names
and emails change; `sub` does not.

Two roles: `admin` and `operator`. Operators manage their own posts; admins
additionally manage users and read the audit log.

### Who becomes an admin

Controlled by `ADMIN_LINKEDIN_SUBS`, a comma-separated allowlist of LinkedIn
`sub` values:

- **Allowlist set** — first-account bootstrap is disabled entirely. Only listed
  subjects get `admin`, and the role is **re-asserted on every sign-in**. This
  self-heals: if the database is wiped or rebuilt, the right person becomes
  admin again simply by signing in.
- **Allowlist empty** — the first account created becomes an active admin, and
  everyone after is created inactive, pending approval. Convenient for local
  development, and safe because an empty allowlist means nobody is claiming
  ownership yet.

### Guard rails

The admin API refuses to demote the last admin, refuses to deactivate the last
active admin, and refuses to let an admin deactivate themselves. Each of these
would otherwise lock everyone out of the admin panel permanently, recoverable
only by direct database access.

---

## Data model

**User** — `linkedin_sub` (unique, the login key), `full_name`, `email`,
`avatar_url`, `role`, `is_active`, `last_seen_at`,
`linkedin_access_token` (~60-day expiry), `linkedin_refresh_token` (~365-day),
`linkedin_person_urn`, `instagram_username` (nullable — users need not have
one).

**Post** — `user_id`, `video_path`, `thumbnail_path`, `video_duration`,
`video_size`, `caption`, `hashtags`, `platform`, `status`, `scheduled_time`,
`posted_at`, `linkedin_post_id`, `instagram_post_id`, `video_url`,
`error_message`, plus engagement counters.

Status flows `draft → scheduled → posted`, with `failed` and `cancelled` as
terminal states. A retracted post becomes `cancelled` rather than being
deleted, so the history still records that it was published and then withdrawn.

**AuditLog** — append-only. See [Audit log](#audit-log).

**Analytics** — per-post engagement snapshots, currently seeded rather than
fetched from LinkedIn.

Schema changes are additive, applied at startup in
`backend/utils/database.py`. There is no migration tool; adding a nullable
column is safe, and anything more involved needs a considered migration.

---

## The Publisher seam

Everything above `backend/core/publishers/` talks to the `Publisher` interface
and never to a platform SDK.

```python
class Publisher(ABC):
    def is_connected(self) -> bool: ...
    def validate_media(self, path) -> tuple[bool, str]: ...
    def publish(self, video_path, caption, thumbnail_path) -> PublishResult: ...
    def delete(self, platform_post_id) -> tuple[bool, str]: ...
    def connection_status(self) -> dict: ...
```

`get_publisher(user, platform)` resolves an implementation from
`post.platform`, so adding a platform means adding a class and registering it
— not editing the scheduler, the routes, or the queue.

This seam is what made the Instagram → LinkedIn pivot survivable. The upload
pipeline, scheduler, queue, and data model were all reusable; only the layer
below the interface was thrown away.

### Failures are returned, never raised

`publish()` returns `PublishResult.failure(...)` rather than throwing.
Publishing fails routinely — expired tokens, rate limits, rejected media — and
those are ordinary outcomes to record against a post, not exceptional control
flow. `retryable=True` is set only for genuinely transient conditions (5xx,
timeouts, rate limits), because it decides whether the scheduler tries again.

### Instagram

`InstagramPublisher` exists and reports `connection_status` as disabled with an
explanation. It is a placeholder that fails honestly rather than a stub that
pretends. `instagrapi` was removed entirely, not merely disabled — it logs in
with a username and password, violates Instagram's Terms of Service, and risks
account suspension.

---

## LinkedIn publishing pipeline

Video posting is a five-step protocol, not a single upload:

```
1. POST /rest/videos?action=initializeUpload
      → video URN + a list of byte ranges, each with a pre-signed upload URL

2. For each range:  PUT the exact byte slice to its URL
      → collect the ETag from every response

3. POST /rest/videos?action=finalizeUpload
      → submit the ETags, in order, to stitch the parts together

4. Poll  GET /rest/videos/{urn}  until status is AVAILABLE
      → LinkedIn transcodes asynchronously; posting before this fails

5. POST /rest/posts   with the video URN as content
      → the new post's URN is returned in the x-restli-id header
```

Every request carries `X-Restli-Protocol-Version: 2.0.0` and
`LinkedIn-Version: YYYYMM`. Omitting either produces errors that do not
mention the missing header.

Media is validated **locally first** — MP4, 3 s to 30 min, 75 KB to 500 MB —
so an invalid file is rejected in milliseconds rather than after uploading
hundreds of megabytes and being refused.

Deletion is `DELETE /rest/posts/{urn}`. Both 204 and 404 count as success:
deletion is idempotent, and the desired end state is "not published", which a
404 already satisfies.

**Proven live.** On 15 Aug 2026 a real post was published to a personal profile
(16.2 s end to end, four upload parts) and deleted 47 seconds later. Until
that run, all of this was tested only against mocks.

---

## Upload pipeline

```
browser                          server
───────                          ──────
validate duration + size
  (fails in ms, no transfer)
    │
    ├─ XHR POST /api/upload ────▶ stream body to disk
    │    with progress events        (never fully buffered in memory)
    │                                    │
    │                                    ├─ ffprobe: real duration + codec
    │                                    │    reject and delete on failure
    │                                    │
    │                                    └─ ffmpeg thumbnail
    │                                         in a background thread
    ◀────────────────────────────── reel metadata
```

**XHR rather than `fetch`.** `fetch` exposes no upload-progress events, and a
progress bar is a requirement for multi-megabyte video. This is the only place
XHR is used, and it is why the upload path attaches its auth header manually
instead of going through `apiFetch`.

**Client validation is a courtesy, not a control.** The server re-validates
everything with `ffprobe` regardless — the browser check exists to save the
user a pointless transfer, not to protect the server.

**Uploads survive navigation.** Upload state lives in a module-level store
(`frontend/src/api/uploadStore.ts`) consumed through `useSyncExternalStore`,
not in component state. Previously, navigating away unmounted the component and
lost all progress and the result — the XHR kept running, so it looked stalled
rather than cancelled.

---

## Scheduling

APScheduler runs in-process with a Postgres-backed job view. Jobs are
reconstructed from the database on startup, so a restart does not lose them,
though timing can drift across a restart.

The scheduler resolves a publisher from `post.platform` and calls the same
`publish()` used by the publish-now endpoint. There is one implementation of
"how do we post to LinkedIn", not two that can drift apart.

**On the free tier the instance sleeps after ~15 minutes idle, and a sleeping
process fires nothing.** Scheduled posting is not reliable until that is fixed
by a paid instance or an external trigger.

---

## Audit log

Append-only. Never updated, never deleted.

Two deliberate choices:

- **`actor_name` is denormalized** and `actor_id` is not a foreign key. When a
  user is deleted, the log still says who did it. A foreign key would either
  block the deletion or cascade away the evidence.
- **Write failures are swallowed.** A failed audit write must never fail the
  publish it was recording. Losing a log line is bad; refusing to publish
  because logging failed is worse.

Recorded actions include `user.signed_up`, `user.signed_in`, `user.signed_out`,
`post.published`, `post.publish_failed`, `post.deleted`, and role/activation
changes.

---

## API reference

Every route requires a bearer token unless marked **public**. Generated from
the live URL map — this is the authoritative list.

### Identity

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/auth/linkedin/login` | **public** — starts sign-in |
| `GET` | `/api/auth/linkedin/callback` | **public** — verifies signed state, exchanges code |
| `GET` | `/api/auth/linkedin/start` | begins authorization for an existing user |
| `GET` | `/api/auth/linkedin/status` | connection state, token expiry |
| `POST` | `/api/auth/linkedin/disconnect` | clears tokens **locally only** — does not revoke at LinkedIn |
| `GET` | `/api/me` | current user identity |
| `POST` | `/api/logout` | client-side sign-out; stateless tokens leave nothing to revoke |

### Posts and publishing

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/posts` | create a draft. `platform` defaults to `linkedin` |
| `GET` | `/api/posts/<id>` | fetch one |
| `DELETE` | `/api/posts/<id>` | delete the local record |
| `POST` | `/api/posts/<id>/publish` | **publish now.** 502 on upstream failure, 409 if already posted |
| `DELETE` | `/api/posts/<id>/published` | retract from the platform; marks the post `cancelled` |
| `POST` | `/api/posts/<id>/schedule` | schedule for a time |
| `POST` | `/api/posts/<id>/schedule-optimal` | schedule at a computed best time |
| `GET` | `/api/users/<id>/posts` | list a user's posts |

Publish and retract enforce ownership from the **session**, never from the
request body. A post belonging to another user returns **404, not 403** —
confirming existence would let post ids be enumerated.

### Media

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/upload` | multipart; streams to disk, validates, thumbnails |
| `GET` | `/api/users/<id>/reels` | list uploaded reels |
| `GET` | `/api/users/<id>/reels/<filename>/thumbnail` | path-traversal guarded |

### Queue and scheduler

| Method | Path |
|---|---|
| `POST` | `/api/queue/add` |
| `DELETE` | `/api/queue/<id>` |
| `GET` | `/api/scheduler/jobs` · `/api/scheduler/pending` · `/api/scheduler/status` |

### Admin — all require the `admin` role

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/admin/users` | users with post counts |
| `POST` | `/api/admin/users/<id>/role` | refuses to demote the last admin |
| `POST` | `/api/admin/users/<id>/active` | refuses self-deactivation |
| `GET` | `/api/admin/audit` | default 100, max 500 |
| `GET` | `/api/admin/stats` | fleet-wide counts |

### Service

| Method | Path | Notes |
|---|---|---|
| `GET` | `/health` | **public** — Render's probe |
| `GET` | `/api/status` | reports the database **dialect only**, never the URL |
| `GET` | `/api/stats` · `/api/users/<id>/analytics` · `/api/users/<id>/optimal-time` | |
| `POST` | `/api/users/<id>/analyze` | recompute analytics |

### Legacy

`POST /api/users` and `POST /api/users/<id>/authenticate` predate LinkedIn SSO
and belong to the Instagram era. `authenticate` reports unavailable because
`instagrapi` is gone. They are candidates for removal — sign-in is
`/api/auth/linkedin/login`.

---

## Frontend

React + TypeScript + Vite, TanStack Query for server state, Tailwind for
styling, React Router for navigation.

### Design system — violet / white / black

Structure, type scale and surface treatment are modelled on render.com; the
accent is the project's own violet, taken from `frontend/public/favicon.svg`.
Four rules, all enforced by `src/index.css` and `src/ui.ts`:

- **Zero border radius.** Nothing is rounded except dots and avatars. There is
  no radius token because there is no radius.
- **Flat surfaces, hairline borders.** `#0D0D0D` cards on a `#0A0A0A` page,
  separated by 1px `#272727` rules. No glass, no backdrop blur, no shadows.
- **The primary button is white with black text.** Violet is an accent, never
  a call to action.
- **Display type is light (300)**, large and tightly tracked — 80px on the
  landing hero, 40px on page titles. Body is 16–18px at 1.6.

`src/ui.ts` holds the twelve class-string recipes (buttons, fields, banners,
type) every screen shares. Add a recipe there rather than re-deriving one.

**Typography is substituted.** render.com uses Roobert and PP Neue Montreal,
both commercially licensed and unavailable to this project. General Sans and
Switzer stand in at matching size, weight and tracking, loaded from Fontshare
(`api.fontshare.com`) — a third-party runtime dependency. If it is slow or
blocked the page falls back to the system sans and the layout holds, but the
design does not. Self-host the two woff2 files under `frontend/public/fonts/`
to remove the dependency.

**Status colour is the one place the palette bends.** Six `PostStatus` values
collapse to violet, white and black by leaning on fill strength and border
style — draft and queued outline in grey and white, scheduled tints violet,
posted fills it, cancelled goes dashed. `failed` keeps a hue of its own
(`--color-danger`), because surfacing a broken post is the reason the Queue
screen exists and a monochrome failure does not catch the eye.

```
src/api/
  auth.ts          apiFetch — attaches the token, clears it on 401
  client.ts        status, user, analytics, uploadReel (XHR)
  schedule.ts      reels, posts, scheduling, publish, retract
  admin.ts         user management, audit
  queue.ts         queue views
  uploadStore.ts   upload state that outlives components
  validation.ts    client-side pre-flight
  types.ts
src/pages/         Upload, Schedule, Queue, Analytics, Settings, Admin
src/components/    Login, shared query states, layout
```

### Every request must go through `apiFetch`

`apiFetch` attaches the session token and clears it on 401. A raw `fetch` call
returns 401 with no explanation to the user.

**This has been the single most common bug in the codebase** — it broke
`client.ts` (uploads, analytics, settings, status) and then `schedule.ts`
(the entire Schedule page) on separate occasions. The upload path is the one
legitimate exception, because it needs XHR for progress events; it sets the
header manually and reads the same `localStorage` key (`smm.session`).

When adding an API module, route it through `apiFetch` before writing anything
else.

---

## Deployment

| Layer | Service | Cost |
|---|---|---|
| App (API + SPA) | Render, Docker runtime, Singapore | free tier |
| Database | Supabase Postgres, Singapore | free, no expiry |
| Media | container filesystem | **ephemeral** |

Co-located in Singapore so the app-to-database round trip stays short.

### The image

Multi-stage. Node 20 builds the SPA; a Python 3.12 runtime installs
dependencies, copies the build output, and runs gunicorn. ffmpeg is installed
in the runtime stage — without it, thumbnails and duration validation silently
degrade, which is exactly what happened before the move to Docker.

Layer order puts dependency manifests before source, so a code change does not
reinstall everything.

### Environment

Secrets live only in Render's environment. `.env` is gitignored and never
committed.

Required: `DATABASE_URL`, `API_ACCESS_KEY`, `SECRET_KEY`, `LINKEDIN_CLIENT_ID`,
`LINKEDIN_CLIENT_SECRET`, `LINKEDIN_REDIRECT_URI`, `CORS_ORIGINS`,
`ADMIN_LINKEDIN_SUBS`, `TIMEZONE`.

> **Render environment changes do not trigger a redeploy.** Updating a variable
> through the API or dashboard leaves the running container on the old values.
> Trigger a deploy explicitly afterwards, then verify the change actually took
> effect — a rotation that appears successful but has not rolled out is worse
> than no rotation, because it is believed.

---

## Branching

| Branch | Purpose | Deploys |
|---|---|---|
| `main` | production — keep green | automatically, on every push |
| `dev` | integration | nothing |
| `design` | frontend design work | nothing — merged to `main` when green |

Before merging to `main`:

```bash
pytest tests/ -q
cd frontend && npx tsc --noEmit && npx vitest run && npm run build
```

`main` deploys straight to production, so a red build there is a live outage
waiting on a fix.

**Running the backend gate takes two workarounds** — neither is a code
problem, but both stop a fresh machine cold:

- `requirements-dev.txt` will not install on Python 3.14: `psycopg2-binary`
  has no wheel for it and the source build fails. Install the rest without it
  (the suite does not touch Postgres), or use Python 3.12.
- Settings validation requires `CLAUDE_API_KEY`, `INSTAGRAM_USERNAME` and
  `INSTAGRAM_PASSWORD` to be set or 65 tests error at collection. Use the same
  placeholders `render.yaml` sets:

```bash
CLAUDE_API_KEY=sk-ant-placeholder-not-used-in-v1 \
INSTAGRAM_USERNAME=your_instagram_username \
INSTAGRAM_PASSWORD=your_instagram_password \
python -m pytest tests/ -q
```

**Parallel sessions.** Two Claude sessions have worked on this repo
concurrently with a file-ownership split — backend, API client modules,
Upload and Schedule pages on one side; app shell, components, and the
Analytics, Settings, Queue, Admin, Login pages on the other. When a change
crosses that boundary, agree the response shape first and build both sides to
it.

**Rollback.** Render can redeploy any previous build from its dashboard, which
skips the build step and is the fastest way out of a broken deploy. For a
permanent fix, `git revert` on `main`.

---

## Testing

93 backend, 27 frontend.

Backend coverage concentrates on what is genuinely risky:

- **LinkedIn publisher (27)** — byte-range slicing, ETag collection quoted and
  unquoted, required headers, validation before any network call, retryable
  versus permanent failure classification
- **Identity (21)** — token round-trip, forged signatures, expiry, the
  `typ: session` claim rejecting OAuth state, immediate effect of
  deactivation, allowlist self-healing, last-admin protection
- **Publish routes (11)** — cross-user publish and delete refused, failure
  marks the post failed, double-publish refused, missing file fails before any
  platform call
- **SPA serving (9)** — deep links return `index.html`, unknown `/api` routes
  return JSON 404, the auth gate is not bypassed by the catch-all
- **Secret leaks (6)** — no response echoes the database password, API key,
  LinkedIn secret, or signing key; a rejected key is not reflected back

The last group exists because `/api/status` was found returning the raw
`DATABASE_URL`, password included. Those tests assert on response *shape* —
no `@`, no `://` in the reported database value — so they fail for any DSN
rather than one known password.

**Mocks are not proof.** The publisher had 27 passing tests while never having
made a real API call, and terminal tests using the API key passed while every
authenticated call from the browser was broken. Both classes of bug were found
by exercising the real path.

---

## Security posture

### Solved

- No passwords anywhere; OAuth 2.0 only, scoped to `w_member_social`
- Every route authenticated by default, failing closed when misconfigured
- Constant-time credential comparison, header-only
- Signed, expiring OAuth state with a type claim preventing replay as a session
- CORS restricted to configured origins, never `*`
- Ownership enforced from the session; cross-user access returns 404
- Admin actions guarded against self-lockout
- Append-only audit trail that survives user deletion
- Oversized uploads rejected before streaming; `secure_filename`;
  path-traversal guard on thumbnails
- Credentials absent from all API responses, with tests

### Not solved

| Gap | Consequence | Fix |
|---|---|---|
| Tokens stored unencrypted | database access reveals LinkedIn tokens | application-level encryption |
| No rate limiting | nothing throttles repeated requests | throttling middleware |
| Some legacy routes accept a client-supplied `user_id` | an authenticated caller could act as another user on those routes | resolve identity from the session everywhere |
| `ALLOW_NEW_SIGNUPS` open | anyone may create a pending account | set false once the team is onboarded |
| Browser flags the shared `onrender.com` domain | users see a full-page warning | custom domain |

---

## Operations

### Rotating credentials

```bash
python -c "import secrets; print(secrets.token_urlsafe(40))"   # API_ACCESS_KEY
python -c "import secrets; print(secrets.token_urlsafe(48))"   # SECRET_KEY
```

Update Render, **trigger a deploy**, then verify: the new key returns 200, the
old one 401, and a previously issued session token 401.

Rotating `SECRET_KEY` invalidates every session — everyone signs in again.
Rotating the LinkedIn client secret does **not** disconnect anyone; existing
access tokens keep working, and only future OAuth exchanges are affected.

The Supabase database password can be rotated through its Management API;
afterwards, confirm the old password is refused rather than assuming it.

### If a secret is exposed

Rotate it, redeploy, verify the old value fails, and check the audit log for
activity in the exposure window.

### Health

`/health` reports database connectivity. `/api/status` reports configuration
state — the database *dialect*, never the URL.
