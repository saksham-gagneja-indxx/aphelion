# Post Pilot — System Architecture & Database Schema

This document describes how the backend, database, and integrations of Post Pilot work together. It reflects the current state of the code, not aspirational design.

---

## 1. High-Level Overview

- **Backend:** Python 3.12, Flask (application-factory pattern), SQLAlchemy ORM, APScheduler (in-process job scheduler), gunicorn (single worker in prod), flask-cors.
- **Frontend:** React + TypeScript + Vite, TanStack Query, Tailwind, React Router.
- **Database:** SQLite in dev (`data/automation.db`, WAL mode), Postgres (Supabase) in prod via `DATABASE_URL`.
- **No migration framework** — schema is created/extended at startup via `Base.metadata.create_all()` plus ad-hoc column checks (`inspect()`). `database/schemas.sql` is a hand-maintained reference and is slightly stale versus the live ORM models.
- **MCP server:** a separate Cloudflare Worker (TypeScript) that lets AI agents (e.g. Claude via GitHub identity) drive the same backend through tool calls.

```
                     ┌──────────────────────┐
                     │   Frontend (React)   │
                     │  Vite/Vercel SPA     │
                     └──────────┬───────────┘
                                │ REST (Bearer token)
                     ┌──────────▼───────────┐
                     │   Flask Backend      │
                     │  (backend/app.py)    │
                     │  Blueprints + APScheduler
                     └──┬─────┬─────┬────┬──┘
                        │     │     │    │
              ┌─────────┘     │     │    └─────────┐
              ▼               ▼     ▼               ▼
        SQLite/Postgres   LinkedIn API   LLM Providers   Local/Object Storage
        (users, posts,    (OAuth+publish) (NIM/Gemini/    (media files)
         analytics, etc.)                  Claude)

                     ┌──────────────────────┐
                     │  MCP Server (Worker) │──── GitHub OAuth ──▶ users.github_username
                     │  Cloudflare/wrangler  │──── calls backend REST API
                     └──────────────────────┘
```

---

## 2. Backend Structure

### 2.1 Entry point

`backend/app.py` → `create_app()`. Registers CORS, security headers, rate limiting, all blueprints, and (when built) serves the compiled React SPA from `frontend/dist` with a catch-all route, so API and frontend can share one origin.

### 2.2 Directory layout

```
backend/
  app.py                 Flask app factory, CORS, security headers, rate limits, SPA fallback
  admin_cli.py           CLI for admin ops (GitHub mapping, encrypt LinkedIn tokens, etc.)
  ai/
    llm_provider.py      LLMProvider ABC + ClaudeProvider / GeminiProvider / NvidiaNimProvider
  api/                   Flask blueprints (route handlers)
  core/
    agent.py, analytics_engine.py, cache.py, captions.py, composer.py,
    linkedin_publisher.py, optimal_timing.py, reel_manager.py, scheduler.py, storage.py
    publishers/          base.py (Publisher ABC), instagram.py (stub), linkedin.py
  models/                SQLAlchemy ORM models
  platforms/             platform-specific glue (placeholder)
  utils/
    clerk_auth.py, config.py, crypto.py, database.py, encryption.py,
    http_security.py, linkedin_api.py, logger.py, security.py, timeutil.py
```

### 2.3 Blueprints and URL prefixes

| Blueprint (file) | Prefix |
|---|---|
| `api_bp` (`routes.py`) | `/api` |
| `auth_bp` (`auth_routes.py`) | `/api` |
| `linkedin_bp` (`linkedin_routes.py`) | `/api/linkedin` |
| `media_bp` (`media_routes.py`) | `/api/media` |
| `caption_bp` (`caption_generation_routes.py`) | `/api/captions` |
| `caption_bp_legacy` (`caption_routes.py`) | `/api/captions` |
| `post_bp` (`post_routes.py`) | `/api/posts` |
| `scheduler_bp` (`scheduler_routes.py`) | `/api/scheduler` |
| `admin_bp` (`admin_routes.py`) | `/api/admin` |
| `publish_bp` (`publish_routes.py`) | `/api/posts` |
| `composer_bp` (`composer_routes.py`) | `/api/composer` |
| `guest_bp` (`guest_routes.py`) | `/api/auth/guest` |
| `console_bp` (`console_routes.py`) | `/api/console` |
| `integrations_bp` (`integrations_routes.py`) | `/api/integrations` |

Plus `GET /health`, `GET /api/status`, and the SPA catch-all, defined directly in `app.py`.

### 2.4 Authentication model

Every route requires either a bearer token (`Authorization: Bearer <API_ACCESS_KEY>` / `X-API-Key`) or a signed session token, enforced by a global `before_request` hook in `backend/utils/security.py`. This **fails closed** (returns 503) if `API_ACCESS_KEY` is unset. The only public routes are:
- `GET /health`
- `GET /api/status`
- LinkedIn OAuth login/callback (`GET /api/auth/linkedin/login`, `GET /api/auth/linkedin/callback`)

Ownership checks always resolve the acting user from the token, never from the request body. Cross-user access to a resource returns **404**, not 403, to avoid confirming a resource exists.

### 2.5 Full endpoint list

**Identity / Auth** (`auth_routes.py`, prefix `/api`)
- `GET /api/auth/linkedin/login` *(public)*
- `GET /api/auth/linkedin/start`
- `POST /api/mcp/link-start`, `POST /api/mcp/authorize-connector`, `POST /api/mcp/verify-connector-grant`
- `GET /api/auth/linkedin/callback` *(public)*
- `POST /api/auth/clerk/verify`
- `GET /api/me`
- `POST /api/logout`
- `GET /api/auth/linkedin/status`
- `GET /api/setup/state`
- `POST /api/auth/linkedin/disconnect`

**Guest** (`guest_routes.py`, prefix `/api/auth/guest`)
- `GET /status`, `POST ""`

**LinkedIn OAuth/credentials** (`linkedin_routes.py`, prefix `/api/linkedin`)
- `POST /connect`, `GET /callback`, `POST /callback`, `GET /status`, `POST /disconnect`, `POST /refresh-token`

**Integrations — per-user LinkedIn app credentials** (`integrations_routes.py`, prefix `/api/integrations`)
- `GET /linkedin/credentials/status`, `POST /linkedin/credentials`, `DELETE /linkedin/credentials`

**Posts — legacy path** (`routes.py`, prefix `/api`)
- `GET /users/by-github/<username>`, `POST /users`, `GET /users/<id>`, `POST /users/<id>/authenticate`
- `POST /posts`, `GET /posts/<id>`, `POST /posts/<id>/schedule`, `POST /posts/<id>/schedule-optimal`, `DELETE /posts/<id>`, `DELETE /posts/<id>/delete`
- `GET /users/<id>/posts`
- `POST /upload`, `GET /users/<id>/reels`, `DELETE /users/<id>/reels/<filename>`, `GET /users/<id>/reels/<filename>/thumbnail`
- `GET /users/<id>/analytics`, `POST /users/<id>/analyze`, `GET /users/<id>/optimal-time`
- `GET /scheduler/status`, `GET /scheduler/jobs`, `GET /scheduler/pending`
- `POST /queue/add`, `DELETE /queue/<id>`, `GET /stats`

**Posts — current path** (`post_routes.py`, prefix `/api/posts`)
- `POST ""` (create draft), `POST /<id>/schedule`, `GET ""` (list), `GET /<id>`, `DELETE /<id>`

**Publishing** (`publish_routes.py`, prefix `/api/posts`)
- `POST /<id>/publish`, `DELETE /<id>/published` (retract), `POST /<id>/delete`, `PATCH /<id>`

**Media** (`media_routes.py`, prefix `/api/media`)
- `POST /upload`, `GET ""` (list), `DELETE /<media_id>`

**Captions** (`caption_generation_routes.py` + legacy `caption_routes.py`, prefix `/api/captions`)
- `POST /generate`, `GET /status`, `POST /suggest`

**Composer** (`composer_routes.py`, prefix `/api/composer`)
- `GET /status`, `POST /turn`

**Scheduler** (`scheduler_routes.py`, prefix `/api/scheduler`)
- `GET /optimal-times`, `POST /reschedule`, `GET /jobs`, `DELETE /jobs/<job_id>`, `POST /jobs/<job_id>/execute-now`

**Admin — requires role `admin`** (`admin_routes.py`, prefix `/api/admin`)
- `GET /users`, `POST /users/<id>/role`, `POST /users/<id>/active`, `POST /users/<id>/github`, `DELETE /users/<id>/linkedin-sub`, `POST /users/<id>/backfill-linkedin-sub`, `POST /encrypt-linkedin-tokens`, `GET /audit`, `GET /stats`

**Console / ops** (`console_routes.py`, prefix `/api/console`)
- `GET /overview`, `DELETE /guests`, `GET /storage/orphans`, `DELETE /storage/orphans`

**Service**
- `GET /health` *(public)*, `GET /api/status` *(public)*

### 2.6 Frontend structure

`frontend/` — React + TypeScript + Vite, TanStack Query, Tailwind, React Router.
API client modules: `frontend/src/api/{auth,client,schedule,admin,queue,uploadStore,composer,captions,console,validation,types}.ts`.
Pages: `Compose`, `Queue`, `Analytics`, `Settings`, `Admin`, `Console`, `Docs`, `Setup`, `McpAuthorize`, `McpConnected`, `Landing`.

---

## 3. Database Schema

### 3.1 `users` (`backend/models/user.py`)

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| linkedin_sub | String(255), unique, indexed, nullable | legacy login key (LinkedIn OIDC `sub`) |
| clerk_id | String(255), unique, indexed, nullable | Clerk identity |
| github_username | String(255), unique, indexed, nullable | MCP/GitHub identity mapping |
| full_name | String(255), nullable | |
| email | String(255), nullable, indexed | |
| avatar_url | String(1000), nullable | |
| role | String(50), default `"operator"`, indexed | `"admin"` \| `"operator"` |
| last_seen_at | DateTime, nullable | |
| instagram_username | String(255), unique, indexed, nullable | |
| instagram_session_id | String(500), nullable | |
| instagram_user_id | String(255), nullable | |
| instagram_connected | Boolean, default False | |
| linkedin_email | String(255), nullable | |
| linkedin_session_id | String(500), nullable | |
| linkedin_connected | Boolean, default False | |
| linkedin_person_urn | String(255), nullable | e.g. `urn:li:person:abc123` |
| linkedin_access_token_encrypted | Text, nullable | Fernet-encrypted |
| linkedin_refresh_token_encrypted | Text, nullable | Fernet-encrypted |
| linkedin_access_token | String(2000), nullable | legacy plaintext fallback |
| linkedin_refresh_token | String(2000), nullable | legacy plaintext fallback |
| linkedin_token_expires_at | DateTime, nullable | |
| linkedin_scope | String(500), nullable | granted OAuth scopes |
| linkedin_own_client_id | String(255), nullable | per-user "bring your own app" |
| linkedin_own_client_secret_encrypted | String(1000), nullable | Fernet-encrypted |
| is_guest | Boolean, default False, nullable | sandbox accounts — never admin/publish |
| timezone | String(50), default `"Asia/Kolkata"` | |
| account_name | String(255), nullable | |
| is_active | Boolean, default True | |
| preferences | JSON | flags: auto_analyze_engagement, analysis_frequency_days, enable_caption_generation, enable_hashtag_recommendations, enable_comment_monitoring, enable_auto_reply |
| created_at / updated_at | DateTime | |
| last_login | DateTime, nullable | |
| instagram_connected_at / linkedin_connected_at | DateTime, nullable | |

**Relationships:** `posts` (1:N → Post, cascade delete-orphan), `analytics` (1:N → Analytics, cascade), `linkedin_credential` (1:1 → LinkedInCredential, cascade).

### 3.2 `posts` (`backend/models/post.py`)

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| user_id | Integer, FK → `users.id`, not null, indexed | ON DELETE CASCADE |
| media_file_id | Integer, FK → `media_files.id`, nullable | |
| video_path | String(500), not null | |
| video_url | String(500), nullable | |
| thumbnail_path | String(500), nullable | |
| video_duration | Float, nullable | |
| video_size | Integer, nullable | |
| caption | Text, nullable | |
| hashtags | String(500), nullable | comma-separated |
| ai_generated_caption / ai_generated_hashtags | Boolean, default False | |
| status | String(50), default `"draft"`, indexed | enum: `draft, queued, scheduled, posted, failed, cancelled` |
| platform | String(50), default `"instagram"` | enum: `instagram, linkedin, both` |
| scheduled_time | DateTime, nullable, indexed | naive, user's local wall clock |
| posted_at | DateTime, nullable | |
| instagram_post_id / linkedin_post_id | String(255), nullable | |
| views / likes / comments / shares | Integer, default 0 | |
| engagement_rate | Float, nullable | |
| post_metadata (DB column `metadata`) | JSON, default `{}` | renamed attribute to avoid SQLAlchemy reserved name |
| error_message | Text, nullable | |
| retry_count | Integer, default 0 | |
| max_retries | Integer, default 3 | |
| job_id | String(255), unique, nullable | APScheduler job id |
| created_at / updated_at | DateTime | |

**Indexes:** `idx_posts_user_id`, `idx_posts_status`, `idx_posts_scheduled_time`, `idx_posts_job_id`.
**Relationships:** `user` (N:1), `media_file` (N:1).

### 3.3 `analytics` (`backend/models/analytics.py`)

| Column | Type |
|---|---|
| id | Integer PK |
| user_id | Integer, FK → `users.id`, not null, indexed (ON DELETE CASCADE) |
| analysis_type | String(50), default `"hourly"` |
| platform | String(50), default `"instagram"` |
| analysis_date | DateTime, default now |
| best_posting_hours / best_posting_days | JSON |
| hourly_analytics / daily_analytics / weekly_analytics | JSON |
| total_posts_analyzed | Integer, default 0 |
| average_likes / average_comments / average_shares / average_engagement_rate | Float, nullable |
| trending_hashtags / trending_content_themes | JSON |
| posting_frequency_optimal | Integer, nullable |
| peak_engagement_hour / peak_engagement_day / slowest_hour / slowest_day | Integer, nullable |
| follower_growth_rate / engagement_growth_rate | Float, nullable |
| data_source | String(100), default `"instagram_api"` |
| last_analysis_posts_count | Integer, default 0 |
| created_at / updated_at / last_calculated_at | DateTime |

**Index:** `idx_analytics_user_id`. **Relationship:** `user` (N:1).

### 3.4 `audit_log` (`backend/models/audit.py`) — append-only

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| actor_id | Integer, nullable, indexed | **not a FK** — deliberately denormalized so entries survive user deletion |
| actor_name | String(255), nullable | denormalized |
| action | String(100), not null, indexed | e.g. `user.signed_up`, `post.published`, `post.publish_failed`, `post.deleted` |
| target | String(255), nullable | e.g. `post:42` |
| detail | Text, nullable | |
| ip_address | String(64), nullable | |
| created_at | DateTime, not null, indexed | |

Writes swallow their own exceptions (`record()` helper) so a logging failure never blocks the action being audited.

### 3.5 `media_files` (`backend/models/media_file.py`)

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| user_id | Integer, FK → `users.id`, not null, indexed | |
| filename | String(255), not null | |
| file_size_bytes | Integer, not null | |
| media_type | String(50), not null | `'video'` \| `'image'` |
| mime_type | String(100), not null | |
| file_extension | String(10), not null | |
| storage_path | String(500), not null | `/user_{id}/{uuid}.ext` |
| storage_url | String(1000), nullable | |
| storage_service | String(50), nullable | `'s3'` \| `'local'` |
| duration_seconds | Numeric(10,2), nullable | |
| width / height | Integer, nullable | |
| thumbnail_url | String(1000), nullable | |
| upload_completed_at | DateTime, not null | |
| is_deleted | Boolean, default False, indexed | soft delete |
| deleted_at | DateTime, nullable | |
| expires_at | DateTime, default `now+30d`, indexed | |
| created_at | DateTime, not null, indexed | |

**Relationships:** `user` (backref `media_files`), `posts` (1:N → Post via `Post.media_file_id`).

### 3.6 `linkedin_credentials` (`backend/models/linkedin_credential.py`)

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| user_id | Integer, FK → `users.id`, unique, not null, indexed | 1:1 with User |
| access_token_encrypted | String(2000), not null | Fernet AES-128 |
| refresh_token_encrypted | String(2000), not null | Fernet AES-128 |
| linkedin_person_urn | String(255), nullable | |
| linkedin_account_name | String(255), nullable | |
| linkedin_profile_url | String(500), nullable | |
| token_expires_at | DateTime, nullable | |
| last_refreshed_at | DateTime, nullable | |
| refresh_count | Integer, default 0 | |
| is_connected | Boolean, default True, indexed | |
| connection_verified_at | DateTime, nullable | |
| created_at / updated_at | DateTime | |

**Relationship:** `user` (1:1 back to `User.linkedin_credential`).

> ⚠️ **Note:** This table appears to be a newer, parallel credential store to the encrypted LinkedIn token columns already present on `users`. Both currently exist in the codebase — confirm which one is actually wired into the live auth/publish flow before treating both as canonical, and consider consolidating.

### 3.7 Views (from `database/schemas.sql` — may be stale)

- `vw_recent_posts` — joins `posts` + `users`, ordered by `created_at desc`.
- `vw_performance_by_hour` — posts grouped by `strftime('%H', posted_at)` with average engagement.

### 3.8 Entity-relationship diagram

```mermaid
erDiagram
    USERS ||--o{ POSTS : "owns (CASCADE)"
    USERS ||--o{ ANALYTICS : "owns (CASCADE)"
    USERS ||--o| LINKEDIN_CREDENTIALS : "owns (CASCADE)"
    USERS ||--o{ MEDIA_FILES : owns
    MEDIA_FILES ||--o{ POSTS : "attached to (nullable FK)"

    USERS {
        int id PK
        string linkedin_sub UK "nullable"
        string clerk_id UK "nullable"
        string github_username UK "nullable"
        string email
        string role "admin | operator"
        bool is_guest
        bool linkedin_connected
        text linkedin_access_token_encrypted
        text linkedin_refresh_token_encrypted
        json preferences
    }

    POSTS {
        int id PK
        int user_id FK
        int media_file_id FK "nullable"
        text caption
        string status "draft/queued/scheduled/posted/failed/cancelled"
        string platform "instagram/linkedin/both"
        datetime scheduled_time
        string linkedin_post_id
        string job_id UK "APScheduler id"
        int retry_count
    }

    ANALYTICS {
        int id PK
        int user_id FK
        string analysis_type
        json best_posting_hours
        float average_engagement_rate
        int peak_engagement_hour
    }

    MEDIA_FILES {
        int id PK
        int user_id FK
        string storage_path
        string media_type "video | image"
        bool is_deleted "soft delete"
        datetime expires_at
    }

    LINKEDIN_CREDENTIALS {
        int id PK
        int user_id FK UK "1:1"
        string access_token_encrypted
        string refresh_token_encrypted
        bool is_connected
        datetime token_expires_at
    }

    AUDIT_LOG {
        int id PK
        int actor_id "NOT a FK - denormalized, survives user deletion"
        string action
        string target
        datetime created_at
    }
```

`AUDIT_LOG` has no relationship line: `actor_id` is deliberately not a foreign key, so audit entries outlive the users they describe.

### 3.9 Cascade summary (text form)

```
users (1) ──< posts (N)            ON DELETE CASCADE
users (1) ──< analytics (N)        ON DELETE CASCADE
users (1) ──1 linkedin_credentials ON DELETE CASCADE
users (1) ──< media_files (N)
media_files (1) ──< posts (N)      posts.media_file_id (nullable)
audit_log                          standalone, actor_id NOT a FK (denormalized)
```

---

## 4. External Integrations

| Integration | Purpose | Key files/config |
|---|---|---|
| **Clerk** | Primary identity provider for the SPA | `backend/utils/clerk_auth.py`; env: `VITE_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `ADMIN_CLERK_EMAILS` |
| **LinkedIn REST API** | OAuth sign-in + publishing | `backend/core/linkedin_publisher.py`, `backend/utils/linkedin_api.py`; env: `LINKEDIN_CLIENT_ID/SECRET/REDIRECT_URI`. Video publish is a 5-step flow: initializeUpload → chunked PUT → finalizeUpload → poll for AVAILABLE → `POST /rest/posts` |
| **Instagram** | Publishing | `InstagramPublisher` is an intentional stub/disabled — `instagrapi` was removed due to ToS/account-suspension risk |
| **LLM providers** (pluggable via `LLM_PROVIDER`) | Caption generation, conversational composer | `backend/ai/llm_provider.py`: NVIDIA NIM (`meta/muse-glimmer-30b`, default), Google Gemini (`gemini-pro-latest`), Anthropic Claude (`claude-haiku-4-5` for captions, `claude-opus-5` for composer) |
| **MCP server** | Lets AI agents drive the backend via tool calls | `mcp-server/` — Cloudflare Worker, TypeScript, `@modelcontextprotocol/sdk`, deployed via `wrangler`. Identity via GitHub OAuth → `/api/mcp/link-start` → `authorize-connector` → `verify-connector-grant` → mapped to `users.github_username`. Tools: `upload_reel_from_url`, `upload_reel`, `list_reels`, `draft_post`, `publish_reel`, `schedule_reel`, `list_posts`, `delete_reel_post`, `edit_reel_post`, `getting_started`, `show_available_commands` |
| **Storage** | Media files | `backend/core/storage.py`: `MediaStore` interface; `LocalMediaStore` (disk, `REELS_FOLDER`) is implemented; `ObjectMediaStore` (S3/R2/GCS, `MEDIA_BACKEND=object`) is a documented stub |
| **Database** | Persistence | SQLite (dev) or Supabase Postgres (prod) via `DATABASE_URL`; `supabase_init.sql` / `setup_supabase.py` for provisioning |
| **Redis** | Optional caching/job queue | `docker-compose.yml` (`REDIS_URL`) — wiring appears partial; scheduler is otherwise in-process/APScheduler |
| **ffmpeg/ffprobe** | Media validation & thumbnails | Validates real duration/codec; extracts a thumbnail by sampling 5 frames scored on detail + exposure |
| **Nginx** | Reverse proxy | `docker-compose.yml` / `nginx.conf` for containerized deployment |
| **Vercel** | Frontend hosting | `frontend/vercel.json`; env: `VITE_API_URL`, `VITE_CLERK_PUBLISHABLE_KEY` |
| **Render** | Backend hosting target | `render.yaml` — currently fully commented out; backend runs locally, not deployed |

---

## 5. Request Flow: Upload → Schedule → Publish

1. **Upload** — `POST /api/upload` (or `/api/media/upload`) streams the video to disk (never fully buffered in memory). `ffprobe` validates real duration/codec; `ffmpeg` generates a scored thumbnail in a background thread. Files live under `REELS_FOLDER/<user_id>/` and persist across sign-out.
2. **Compose** — The user (or the conversational composer via `POST /api/composer/turn`) selects a reel, writes or AI-generates a caption (`POST /api/captions/generate` → `backend/core/captions.py` → active `LLMProvider`), and picks a time. Composer tools (`choose_reel`, `set_caption`, `set_schedule`) only mutate a client-side draft — there is no publish tool inside the LLM loop.
3. **Create post** — `POST /api/posts` creates a `Post` row with `status="draft"`.
4. **Schedule** — `POST /api/posts/<id>/schedule` (or `/schedule-optimal`, using `backend/core/optimal_timing.py` + `Analytics`) sets `scheduled_time`, flips status to `scheduled`, and registers an APScheduler job (`backend/core/scheduler.py`), storing `job_id` on the `Post` row. `_restore_scheduled_jobs` rebuilds timers from the `posts` table on process start, honoring `SCHEDULER_MISFIRE_GRACE_SECONDS`.
5. **Publish** — (scheduled, or manual `POST /api/posts/<id>/publish`) `get_publisher(user, platform)` resolves a `Publisher` implementation purely from `post.platform` (currently `LinkedInPublisher`). It runs the 5-step LinkedIn video protocol and returns a `PublishResult` (never raises), marking failures `retryable` only for transient errors (5xx / timeouts / rate limits).
6. **Result** — On success, `Post.mark_as_posted()` records `linkedin_post_id`/`posted_at` and sets status to `posted`; an audit entry (`post.published`) is written (best-effort, non-blocking). On failure, `mark_as_failed()` records `error_message`, increments `retry_count`, sets status to `failed`, and audits `post.publish_failed`.
7. **Retraction** — `DELETE /api/posts/<id>/published` calls `Publisher.delete()` (idempotent — 204 and 404 both count as success) and sets status to `cancelled`. Posts are never hard-deleted this way, preserving history.
8. **Analytics** — `POST /api/users/<id>/analyze` recomputes `Analytics` rows (currently seeded rather than live-fetched from LinkedIn), which feed optimal-time scheduling.

---

## 6. Known Inconsistencies / Follow-ups

- `database/schemas.sql` predates the Clerk / `linkedin_credentials` / `media_files` additions — treat the ORM models as the source of truth, not the SQL file.
- There is no formal migration tool (Alembic, etc.) — schema evolves via `create_all()` + ad-hoc `inspect()` column checks in `init_db()`. Any manual production schema change needs to be mirrored there.
- LinkedIn tokens are stored in **two places**: encrypted columns directly on `users`, and a separate `linkedin_credentials` table. Confirm which is authoritative before further auth work, and plan to consolidate.
- Instagram publishing is a stub only; `platform="instagram"` posts will not actually publish.
- Redis is present in `docker-compose.yml` but not clearly wired into the scheduler, which is otherwise in-process (APScheduler) and tied to a single gunicorn worker — this is load-bearing (do not scale workers without moving the scheduler out of process first).
