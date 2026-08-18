# System Architecture - LinkedIn Reel Posting via Claude MCP

**Version**: 1.0  
**Status**: Design Phase  
**Last Updated**: 2026-08-18

---

## Table of Contents
1. [Overview](#overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Component Descriptions](#component-descriptions)
4. [Data Flow](#data-flow)
5. [Security Model](#security-model)
6. [Tech Stack](#tech-stack)

---

## Overview

A complete system enabling users to authenticate once, then post to LinkedIn through Claude by uploading media and asking Claude to post it.

**Three Main Components:**
1. **Web Dashboard** - Setup and credential management
2. **Backend API** - Handles authentication, storage, LinkedIn integration
3. **Claude MCP** - Tools for upload, caption generation, posting

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                         USER                                      │
└──────────────┬─────────────────────────────────────────────────────┘
               │
        ┌──────┴──────┐
        │             │
        ▼             ▼
   ┌─────────┐  ┌──────────┐
   │  Claude │  │ Website  │
   │   MCP   │  │Dashboard │
   └────┬────┘  └────┬─────┘
        │            │
        │      ┌─────▼─────┐
        │      │  Clerk    │
        │      │(Auth)     │
        │      └─────┬─────┘
        │            │
        └────┬───────┘
             │
        ┌────▼─────────────────┐
        │   Backend API        │
        │  (Flask/Python)      │
        │                      │
        │  ├─ Auth Routes      │
        │  ├─ Upload Routes    │
        │  ├─ Caption API      │
        │  ├─ LinkedIn Routes  │
        │  └─ Manage Routes    │
        └────┬────────────────┘
             │
        ┌────▼──────────────────┐
        │   Database            │
        │  (SQLite/Postgres)    │
        │                       │
        │  ├─ Users             │
        │  ├─ Credentials       │
        │  ├─ Posts             │
        │  └─ Media Files       │
        └───────────────────────┘
             │
        ┌────▼──────────────────┐
        │  External Services    │
        │                       │
        │  ├─ LinkedIn API      │
        │  ├─ Clerk Auth        │
        │  └─ AI/LLM (Claude)   │
        └───────────────────────┘
```

---

## Component Descriptions

### 1. Web Dashboard (`/dashboard`)
**Purpose**: One-time setup interface  
**Access**: Browser (Desktop/Mobile)  
**Features**:
- User authentication
- LinkedIn credential connection
- Dashboard overview
- Credential management (disconnect, refresh)
- Activity log

**Pages**:
```
/login                 - Login/signup page
/dashboard             - Main dashboard
/dashboard/linkedin    - LinkedIn connection page
/dashboard/settings    - User settings
/mcp/connect           - MCP authentication endpoint
```

### 2. Backend API (`/api/*`)
**Purpose**: Core business logic  
**Technology**: Python Flask  
**Responsibilities**:
- User authentication
- Credential encryption/storage
- File upload handling
- Caption generation coordination
- LinkedIn API integration
- Post management

**Key Modules**:
```
api/
├── auth_routes.py       - Login, signup, session
├── linkedin_routes.py   - LinkedIn OAuth, token refresh
├── upload_routes.py     - Media file uploads
├── caption_routes.py    - Caption generation
├── post_routes.py       - Create, publish, schedule posts
└── manage_routes.py     - List, edit, delete posts
```

### 3. Claude MCP Server
**Purpose**: Tools available to Claude  
**Technology**: TypeScript/Node.js on Cloudflare Workers  
**Tools**:
- `upload_media` - Accept file upload
- `generate_caption` - AI caption generation
- `post_reel` - Post to LinkedIn
- `schedule_reel` - Schedule post for later
- `list_posts` - View user's posts

### 4. Database
**Purpose**: Persistent data storage  
**Technology**: SQLite (dev) / PostgreSQL (prod)  
**Tables**: See [Database Schema](DATABASE_SCHEMA.md)

### 5. External Services
- **Clerk**: User authentication
- **LinkedIn API**: Post publishing
- **Claude/LLM**: Caption generation
- **File Storage**: S3 or local filesystem

---

## Data Flow

### Setup Flow (First Time)
```
1. User opens MCP connector in Claude
   └─> Redirect to: https://postpilot.com/mcp/connect
       
2. Check if user is authenticated
   ├─ NO: Show Clerk login page
   │      └─> User logs in
   │          └─> Backend stores session
   │
   └─ YES: Skip to step 3

3. User lands on dashboard
   └─> "Connect LinkedIn" button
       
4. User clicks "Connect LinkedIn"
   └─> LinkedIn OAuth flow
       ├─ User grants permissions
       ├─ Backend receives auth code
       ├─ Exchange for access token
       ├─ Encrypt token
       ├─ Store in database
       └─> Display "✅ Connected"

5. User returns to Claude
   └─> MCP is now activated with credentials
```

### Usage Flow (Daily)
```
1. User: "I have a new video about AI"
   └─> Claude acknowledges

2. User uploads video file to Claude
   └─> Claude receives file (max 100MB)
       
3. Claude calls MCP: upload_media(file_path)
   ├─ MCP receives file from Claude
   ├─ Backend stores file to S3/storage
   ├─ Returns file ID and URL
   └─> Claude has file reference

4. Claude calls MCP: generate_caption(file_id, topic)
   ├─ Backend fetches file from storage
   ├─ Calls Claude API to generate caption
   ├─ Returns 3 caption options
   └─> Claude shows to user

5. User: "Use the first one and post it"
   └─> Claude analyzes command
       ├─ Detects: This is a posting request
       ├─ Extracts: Caption #1
       └─> Calls MCP: post_reel(file_id, caption)

6. MCP posts to LinkedIn
   ├─ Fetch user's encrypted LinkedIn token
   ├─ Decrypt token
   ├─ Call LinkedIn API
   ├─ Post media + caption
   ├─ Receive post URL
   └─> Return success to Claude

7. Claude displays confirmation
   └─> "✅ Posted! Link: https://linkedin.com/..."
```

### Scheduling Flow
```
1. User: "Post this video tomorrow at 10 AM"
   └─> Claude calls: schedule_reel(file_id, caption, time)

2. Backend receives request
   ├─ Validates time (future, within 30 days)
   ├─ Creates scheduled post record
   ├─ Sets up cron job/scheduler
   └─> Returns confirmation

3. At scheduled time
   ├─ Scheduler wakes up
   ├─ Fetches post details
   ├─ Calls LinkedIn API
   └─> Post goes live

4. User can see scheduled posts
   └─> Claude calls: list_posts()
       └─> Shows upcoming scheduled posts
```

---

## Security Model

### Authentication
```
User Login Flow:
├─ User provides email/password to Clerk
├─ Clerk verifies credentials
├─ Returns JWT session token
├─ Backend stores session in database
└─ User can now access protected resources

Session Verification:
├─ Every API request requires Authorization header
├─ Backend validates JWT signature
├─ Checks session expiration
├─ Returns 401 if invalid
└─ Proceeds if valid
```

### Credential Storage
```
LinkedIn Token Storage:
├─ User gets token from LinkedIn OAuth
├─ Backend receives token
├─ Encrypt using Fernet encryption
│  └─ Key = ENCRYPTION_KEY (from environment)
├─ Store encrypted token in database
└─ Never stored in plaintext

Token Usage:
├─ Request comes to backend
├─ Find user's encrypted token
├─ Decrypt using ENCRYPTION_KEY
├─ Use token with LinkedIn API
├─ Discard decrypted token
└─ Never log or expose token
```

### File Upload Security
```
Upload Validation:
├─ Check file size (max 100MB)
├─ Check file type (only video/image)
├─ Scan for malware (optional)
├─ Generate unique filename
├─ Store with user_id prefix
└─ Allow access only to owner

Storage:
├─ Files stored in isolated directory
├─ Named: {user_id}/{random_uuid}.{ext}
├─ Accessible only to authenticated owner
├─ Automatic cleanup after 30 days
└─ Encrypted at rest (S3 with KMS)
```

### API Security
```
Request Validation:
├─ All endpoints require authentication
├─ Rate limiting (100 req/min per user)
├─ CORS restricted to dashboard domain
├─ HTTPS only (no HTTP)
├─ Content-Type validation
└─ SQL injection prevention (ORM)

Response Security:
├─ Never expose token in responses
├─ Never log sensitive data
├─ Set security headers (HSTS, CSP)
├─ Remove stack traces from errors
└─ Audit log all important actions
```

---

## Tech Stack

### Frontend (Dashboard)
```
├─ Next.js / React (Web app)
├─ TypeScript
├─ Tailwind CSS
├─ Clerk Auth (embedded)
└─ Axios (HTTP client)
```

### Backend
```
├─ Python 3.10+
├─ Flask (REST API)
├─ SQLAlchemy (ORM)
├─ Cryptography (Fernet encryption)
├─ LinkedIn OAuth 2.0
├─ APScheduler (Job scheduling)
└─ Gunicorn (Production server)
```

### Database
```
├─ SQLite (development)
├─ PostgreSQL (production)
├─ Alembic (Migrations)
└─ Connection pooling
```

### MCP
```
├─ TypeScript
├─ Cloudflare Workers
├─ Durable Objects (state)
├─ KV Store (sessions)
└─ OpenAI SDK (for Claude API)
```

### Deployment
```
├─ Backend: Render.com or AWS EC2
├─ Frontend: Vercel
├─ Database: AWS RDS or Supabase
├─ Files: AWS S3 or local storage
└─ MCP: Cloudflare Workers
```

---

## Integration Points

### MCP ↔ Backend
```
MCP calls backend endpoints:
├─ GET  /api/users/by-github/{username}
├─ POST /api/upload
├─ POST /api/captions/generate
├─ POST /api/posts/create
└─ GET  /api/posts/list

Authentication:
├─ Bearer token in Authorization header
├─ Token = BACKEND_API_KEY (MCP secret)
└─ Backend validates on every request
```

### Backend ↔ LinkedIn
```
LinkedIn API calls:
├─ POST /v2/assets?action=registerUpload
├─ POST /v2/videoProcessingTasks
├─ POST /v2/ugcPosts (create post)
├─ POST /v2/shares (legacy share)
└─ GET /v2/me (verify permissions)

OAuth:
├─ Client ID: (from env)
├─ Client Secret: (from env, encrypted)
├─ Access Token: (stored encrypted, user-specific)
└─ Refresh Token: (stored encrypted, auto-refresh)
```

### Backend ↔ Claude
```
Caption Generation:
├─ Call Claude API with file content
├─ Request: "Generate 3 LinkedIn captions for this video"
├─ Response: 3 caption options
└─ Cost: ~$0.10 per generation

MCP Context:
├─ Claude knows about user's media
├─ Claude has posting capability
├─ Claude understands confirmation semantics
└─ Claude can generate captions automatically
```

---

## Error Handling & Fallbacks

```
Upload Fails:
├─ File too large → Return 413
├─ Invalid format → Return 400
├─ Storage error → Return 500 + retry message
└─ User gets clear error message

LinkedIn API Fails:
├─ Token expired → Refresh automatically
├─ Rate limited → Queue for retry
├─ Permission denied → Show user error
└─ Network error → Queue for retry

Caption Generation Fails:
├─ AI service down → Use template
├─ Network error → Retry 3 times
├─ Invalid response → Ask user to retry
└─ Cost exceeded → Warn and skip
```

---

## Performance Considerations

```
Optimization:
├─ Cache user credentials in memory (with TTL)
├─ Use connection pooling for database
├─ Queue caption generation (async)
├─ CDN for dashboard assets
├─ Compress media before storage
└─ Lazy load file previews

Scaling:
├─ Database: Read replicas for queries
├─ Backend: Horizontal scaling with load balancer
├─ Storage: S3 auto-scales
├─ MCP: Cloudflare auto-scales globally
└─ Sessions: Redis for distributed cache
```

---

## Monitoring & Logging

```
Metrics:
├─ API response times
├─ Upload success rate
├─ LinkedIn posting success rate
├─ Caption generation latency
├─ Token refresh frequency
└─ Error rates by type

Logging:
├─ All user actions (audit log)
├─ All LinkedIn API calls
├─ All errors with context
├─ Token lifecycle events
├─ Storage operations
└─ Never log actual tokens
```

---

## Next Documents to Read

1. **[DATABASE_SCHEMA.md](DATABASE_SCHEMA.md)** - Table structures and relationships
2. **[API_ENDPOINTS.md](API_ENDPOINTS.md)** - Detailed endpoint specifications
3. **[MCP_TOOLS.md](MCP_TOOLS.md)** - Claude MCP tool definitions
4. **[AUTHENTICATION_FLOW.md](AUTHENTICATION_FLOW.md)** - Security and auth details
5. **[ENCRYPTION_STRATEGY.md](ENCRYPTION_STRATEGY.md)** - Credential encryption approach

---

**Next Step**: Review this architecture. If approved, move to detailed design of each component.
