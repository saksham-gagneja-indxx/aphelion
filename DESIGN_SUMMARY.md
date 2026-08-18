# LinkedIn Posting via Claude - Design Summary

**Version**: 1.0  
**Status**: Design Complete  
**Date**: 2026-08-18

---

## Executive Summary

A complete system enabling users to:
1. **Authenticate once** via web dashboard
2. **Connect LinkedIn** securely (OAuth tokens stored encrypted)
3. **Upload media to Claude** (video/image)
4. **Get AI captions** automatically
5. **Post to LinkedIn** with one command ("Post it!")
6. **Schedule posts** for optimal timing

---

## What We Designed

### Three Main Components

#### 1. **Web Dashboard** (`/dashboard`)
- **Purpose**: Setup and credential management (one-time)
- **Auth**: Clerk (industry standard)
- **Flow**:
  ```
  User → Login → Connect LinkedIn → Dashboard → Ready for Claude
  ```
- **No more credential entry needed** - all stored securely

#### 2. **Backend API** (`/api/*`)
- **Purpose**: Core business logic
- **Handles**:
  - User authentication via Clerk
  - LinkedIn credential storage (encrypted)
  - File uploads (100MB max)
  - Caption generation via Claude
  - LinkedIn API integration
  - Post scheduling
- **Technology**: Python Flask
- **Database**: PostgreSQL/SQLite

#### 3. **Claude MCP** (Cloudflare Workers)
- **Purpose**: Claude tools for users
- **Tools**:
  - `upload_media` - Accept file from Claude
  - `generate_caption` - Create captions
  - `post_reel` - Publish to LinkedIn
  - `schedule_reel` - Schedule for later
  - `list_posts` - View posts
- **Authentication**: Bearer token to backend

---

## Complete User Flow

### Setup (One-time, ~5 minutes)

```
User: "I want to post to LinkedIn via Claude"
  ↓
Opens connector in Claude
  ↓
Redirected to: https://postpilot.com/mcp/connect
  ↓
Clerk login page
  ↓
User logs in
  ↓
Dashboard: "Connect LinkedIn"
  ↓
LinkedIn OAuth flow
  ↓
Backend stores encrypted token
  ↓
"✅ Ready to use with Claude!"
  ↓
Returns to Claude
```

### Daily Usage (Repeatable)

```
User: "I have a new video"
  ↓
Uploads video to Claude (drag & drop)
  ↓
Claude: "I'll generate captions for you"
Claude calls: generate_caption(video)
  ↓
Returns 3 caption options
  ↓
Claude: "Here are 3 options: [1] ... [2] ... [3] ..."
  ↓
User: "Use #1 and post it"
  ↓
Claude analyzes: "This is a posting request" ✓
Claude calls: post_reel(video, caption_1)
  ↓
Backend:
  ├─ Fetches decrypted LinkedIn token
  ├─ Posts to LinkedIn via API
  ├─ Returns post URL
  └─> Claude receives success
  ↓
Claude: "✅ Posted! Link: https://linkedin.com/feed/update/..."
```

### Scheduling Flow

```
User: "Post this tomorrow at 10 AM"
  ↓
Claude calls: schedule_reel(video, caption, time)
  ↓
Backend:
  ├─ Validates time (future, within 30 days)
  ├─ Stores scheduled post
  ├─ Sets up scheduler job
  └─> Confirmation to Claude
  ↓
At scheduled time:
  ├─ Scheduler wakes up
  ├─ Posts to LinkedIn
  └─> User sees post live
```

---

## Security Architecture

### Credential Storage (Most Important!)

**What we store:**
- LinkedIn OAuth access token (encrypted)
- LinkedIn OAuth refresh token (encrypted)
- Token expiration times
- LinkedIn account info (public)

**What we DON'T store:**
- ❌ User passwords
- ❌ User's LinkedIn username/password
- ❌ Any plaintext credentials

**How we encrypt:**
```python
# Method: Fernet (AES-128 symmetric encryption)
# Key: ENCRYPTION_KEY environment variable
# Salt: Derived from key + random IV
# Decryption: Only when posting to LinkedIn
```

**Security guarantees:**
- ✅ Tokens encrypted at rest
- ✅ Tokens only decrypted when needed
- ✅ Tokens auto-refresh when expired
- ✅ Tokens never logged or exposed
- ✅ Encryption key never in code

### Authentication Layers

```
Layer 1: Clerk (user login)
├─ Industry standard OAuth
├─ No passwords stored by us
├─ JWT session tokens
└─> User authenticated to web dashboard

Layer 2: Session tokens (API access)
├─ JWT signed on backend
├─ 24-hour expiration
├─ Can be revoked
└─> User authenticated to API

Layer 3: Bearer tokens (MCP access)
├─ Static API key for MCP
├─ Separate from user sessions
├─ Rate limited
└─> MCP authenticated to backend
```

### Data Protection

```
In Transit:
├─ HTTPS only (no HTTP)
├─ TLS 1.3 minimum
├─ Certificate pinning (optional)
└─ All APIs encrypted

At Rest:
├─ Database encryption (PostgreSQL native)
├─ File encryption (S3 KMS)
├─ Credential encryption (Fernet)
└─> Defense in depth

Access Control:
├─ Users only see own data
├─ Admin functions protected
├─ Activity logging (audit trail)
└─> Who did what, when
```

---

## Database Design

### Core Tables

| Table | Purpose | Encrypted Fields |
|-------|---------|-----------------|
| `users` | User accounts | None (public data) |
| `linkedin_credentials` | OAuth tokens | access_token, refresh_token |
| `media_files` | Uploaded videos/images | None (files encrypted in storage) |
| `posts` | Published/draft posts | None (captions are user data) |
| `scheduled_posts` | Future posts | None (metadata only) |
| `activity_logs` | Audit trail | None (logs are immutable) |
| `sessions` | Active sessions | None (JWT tokens) |

### Key Design Decisions

✅ **One-to-one relationship** between users and LinkedIn credentials  
✅ **Soft deletes** for media (auto-cleanup after 30 days)  
✅ **Separation of concerns** (credentials, posts, media in different tables)  
✅ **Indexing for performance** (user_id, status, scheduled_for)  
✅ **Audit trail** (all actions logged)  

---

## API Design

### 8 Endpoint Categories

1. **Authentication** (`/auth/*`)
   - Login, logout, current user

2. **LinkedIn Management** (`/api/linkedin/*`)
   - Connect, disconnect, status, refresh token

3. **Media Upload** (`/api/media/*`)
   - Upload, list, delete files

4. **Caption Generation** (`/api/captions/*`)
   - Generate captions via Claude

5. **Posts** (`/api/posts/*`)
   - Create, publish, update, list posts

6. **Scheduling** (`/api/scheduled-posts/*`)
   - Schedule, list, cancel scheduled posts

7. **Activity Logs** (`/api/activity/*`)
   - Audit trail of user actions

8. **Dashboard** (`/dashboard/*`)
   - Web pages for setup

### Authentication & Authorization

```
Public endpoints (no auth required):
  - /auth/login
  - /dashboard (redirects to login)

Protected endpoints (require Bearer token):
  - /api/* (all APIs)

Admin only endpoints:
  - /api/admin/* (future)
```

---

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
- [x] System design documentation
- [x] Database schema design
- [x] API specification
- [ ] Create database tables
- [ ] Set up Flask backend
- [ ] Implement auth routes

**Effort**: 20-30 hours

### Phase 2: Credentials & LinkedIn (Weeks 3-4)
- [ ] Implement LinkedIn OAuth
- [ ] Encrypt/decrypt credentials
- [ ] Create `/api/linkedin/*` routes
- [ ] Token refresh mechanism
- [ ] Test LinkedIn integration

**Effort**: 15-20 hours

### Phase 3: Media & Captions (Weeks 5-6)
- [ ] File upload handling
- [ ] Caption generation API
- [ ] Create `/api/media/*` routes
- [ ] Create `/api/captions/*` routes
- [ ] Test uploads and generation

**Effort**: 12-15 hours

### Phase 4: Posts & Publishing (Weeks 7-8)
- [ ] Create `/api/posts/*` routes
- [ ] LinkedIn publishing API
- [ ] Create `/api/scheduled-posts/*` routes
- [ ] Job scheduler setup
- [ ] Test publishing flow

**Effort**: 15-20 hours

### Phase 5: Dashboard UI (Weeks 9-10)
- [ ] Build dashboard layout
- [ ] Create login page
- [ ] Create LinkedIn connection page
- [ ] Create main dashboard
- [ ] Integrate Clerk auth

**Effort**: 20-25 hours

### Phase 6: MCP Integration (Weeks 11-12)
- [ ] Update MCP tools
- [ ] Integrate with backend APIs
- [ ] Test full flow
- [ ] Deploy to Cloudflare
- [ ] Security audit

**Effort**: 12-15 hours

### Phase 7: Testing & Polish (Weeks 13-14)
- [ ] Integration testing
- [ ] Load testing
- [ ] Security testing
- [ ] Documentation
- [ ] Production deployment

**Effort**: 15-20 hours

---

## Total Effort Estimate

```
Foundation:       20-30 hours
LinkedIn:         15-20 hours
Media/Captions:   12-15 hours
Posts/Publishing: 15-20 hours
Dashboard UI:     20-25 hours
MCP Integration:  12-15 hours
Testing/Polish:   15-20 hours

TOTAL:            109-145 hours
                  ~3-4 months (one developer)
                  ~6-8 weeks (two developers)
```

---

## Technology Choices & Rationale

### Clerk for Auth
✅ **Why**: Industry standard, handles OAuth, no passwords to manage  
✅ **Alternative**: Auth0, but Clerk simpler for our use case  

### Fernet for Encryption
✅ **Why**: Symmetric AES, built-in HMAC, time-based expiration  
✅ **Alternative**: RSA, but symmetric simpler for this use case  

### Flask for Backend
✅ **Why**: Lightweight, familiar, good ecosystem  
✅ **Alternative**: FastAPI (faster), Django (heavier), but Flask sufficient  

### PostgreSQL for Production
✅ **Why**: Open source, reliable, great SQL support  
✅ **Alternative**: MySQL (good), MongoDB (not SQL)  

### Cloudflare Workers for MCP
✅ **Why**: Serverless, global distribution, KV + Durable Objects  
✅ **Alternative**: AWS Lambda (fine), but Workers better for this  

---

## Risk Assessment

### High Risks
1. **LinkedIn API Changes**
   - Mitigation: Version API endpoints, maintain compatibility layer
   
2. **Token Expiration**
   - Mitigation: Auto-refresh, clear error messages

3. **File Storage Limits**
   - Mitigation: Clean up old files, warn users

### Medium Risks
1. **Caption Generation Cost**
   - Mitigation: Cache results, rate limiting

2. **User Credential Mishandling**
   - Mitigation: Encryption, audit logging, regular security audits

### Low Risks
1. **Database Downtime**
   - Mitigation: Backups, replicas, alerting

2. **API Rate Limiting**
   - Mitigation: Queue system, retry logic

---

## Success Criteria

✅ Users can authenticate once  
✅ LinkedIn tokens stored securely  
✅ File uploads work (video & image)  
✅ Captions generated automatically  
✅ Posts publish in <5 seconds  
✅ Scheduling works reliably  
✅ Dashboard is intuitive  
✅ MCP integration seamless  
✅ Security audit passes  
✅ <5 minute setup time  

---

## Next Steps

### Immediate (This Week)
1. ✅ Review & approve this design
2. Get stakeholder sign-off
3. Allocate development resources

### Phase 1 (Next 2 Weeks)
1. Create database
2. Set up Flask project
3. Implement basic auth

### Ongoing
1. Weekly design reviews
2. Bi-weekly demo iterations
3. Monthly security audits

---

## Documents Included

| Document | Purpose |
|----------|---------|
| [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | High-level system design |
| [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) | Complete database structure |
| [API_ENDPOINTS.md](API_ENDPOINTS.md) | Detailed REST API spec |
| [DESIGN_SUMMARY.md](DESIGN_SUMMARY.md) | This document (overview) |

---

## Questions?

**For clarifications on:**
- Database design → See DATABASE_SCHEMA.md
- API details → See API_ENDPOINTS.md
- System architecture → See SYSTEM_ARCHITECTURE.md
- Overall plan → See DESIGN_SUMMARY.md (this file)

---

**Status**: Design phase complete. Ready for development approval.

**Next**: Waiting for stakeholder sign-off before starting Phase 1 implementation.
