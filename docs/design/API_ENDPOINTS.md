# API Endpoints Specification

**Version**: 1.0  
**Status**: Design Phase  
**Base URL**: `https://api.postpilot.com` (production)

---

## Authentication

All endpoints (except `/auth/*`) require Bearer token:

```bash
curl -H "Authorization: Bearer {session_token}" \
  https://api.postpilot.com/api/posts
```

**Token Sources**:
- Clerk JWT (from web dashboard login)
- MCP Bearer token (for Claude connector)

---

## Endpoints by Category

### 1. Authentication Routes (`/auth/*`)

#### `POST /auth/login`
User login via Clerk.

```
Request:
POST /auth/login
Content-Type: application/json

{
  "clerk_token": "eyJhbGc..."  // Clerk JWT
}

Response (200):
{
  "session_token": "sess_xyz...",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "full_name": "John Doe"
  }
}

Response (401):
{
  "error": "Invalid Clerk token"
}
```

#### `POST /auth/logout`
Invalidate session.

```
Request:
POST /auth/logout
Authorization: Bearer {session_token}

Response (200):
{
  "message": "Logged out successfully"
}
```

#### `GET /auth/me`
Get current user profile.

```
Request:
GET /auth/me
Authorization: Bearer {session_token}

Response (200):
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "full_name": "John Doe",
    "avatar_url": "https://...",
    "timezone": "America/New_York",
    "created_at": "2026-08-18T10:00:00Z"
  }
}

Response (401):
{
  "error": "Unauthorized"
}
```

---

### 2. LinkedIn Credential Routes (`/api/linkedin/*`)

#### `POST /api/linkedin/connect`
Initiate LinkedIn OAuth connection.

```
Request:
POST /api/linkedin/connect
Authorization: Bearer {session_token}

Response (200):
{
  "oauth_url": "https://www.linkedin.com/oauth/v2/authorization?client_id=...",
  "state": "state_xyz..."
}
```

#### `POST /api/linkedin/callback`
LinkedIn OAuth callback (internal).

```
Request:
POST /api/linkedin/callback
Content-Type: application/json

{
  "code": "auth_code_from_linkedin",
  "state": "state_xyz..."
}

Response (200):
{
  "success": true,
  "credential_id": 5,
  "linkedin_account": "John Doe",
  "person_urn": "urn:li:person:ABC123"
}

Response (400):
{
  "error": "Invalid OAuth code"
}
```

#### `GET /api/linkedin/status`
Check LinkedIn connection status.

```
Request:
GET /api/linkedin/status
Authorization: Bearer {session_token}

Response (200):
{
  "is_connected": true,
  "account_name": "John Doe",
  "profile_url": "https://linkedin.com/in/johndoe",
  "person_urn": "urn:li:person:ABC123",
  "connected_at": "2026-08-18T10:00:00Z",
  "token_expires_at": "2026-09-18T10:00:00Z"
}

Response (200):
{
  "is_connected": false
}
```

#### `POST /api/linkedin/disconnect`
Revoke LinkedIn connection.

```
Request:
POST /api/linkedin/disconnect
Authorization: Bearer {session_token}

Response (200):
{
  "message": "LinkedIn disconnected"
}

Response (409):
{
  "error": "Not connected"
}
```

#### `POST /api/linkedin/refresh-token`
Manually refresh LinkedIn token.

```
Request:
POST /api/linkedin/refresh-token
Authorization: Bearer {session_token}

Response (200):
{
  "expires_at": "2026-09-18T10:00:00Z",
  "message": "Token refreshed"
}

Response (401):
{
  "error": "LinkedIn connection required"
}
```

---

### 3. Media Upload Routes (`/api/media/*`)

#### `POST /api/media/upload`
Upload media file (video or image).

```
Request:
POST /api/media/upload
Authorization: Bearer {session_token}
Content-Type: multipart/form-data

File upload (100 MB max):
- file: (binary video/image)
- metadata: {
    "title": "My video",
    "description": "About my project"
  }

Response (201):
{
  "id": 42,
  "filename": "my_video.mp4",
  "file_size_bytes": 45000000,
  "media_type": "video",
  "duration_seconds": 30.5,
  "thumbnail_url": "https://storage/thumb_42.jpg",
  "storage_url": "https://storage/media_42.mp4",
  "created_at": "2026-08-18T10:00:00Z",
  "expires_at": "2026-09-18T10:00:00Z"
}

Response (400):
{
  "error": "File too large (max 100MB)"
}

Response (413):
{
  "error": "Payload too large"
}
```

#### `GET /api/media`
List all uploaded media files.

```
Request:
GET /api/media?limit=10&offset=0&sort=created_at_desc
Authorization: Bearer {session_token}

Response (200):
{
  "total": 25,
  "items": [
    {
      "id": 42,
      "filename": "video.mp4",
      "media_type": "video",
      "file_size_bytes": 45000000,
      "duration_seconds": 30.5,
      "thumbnail_url": "https://...",
      "created_at": "2026-08-18T10:00:00Z"
    },
    ...
  ]
}
```

#### `DELETE /api/media/{id}`
Delete uploaded media.

```
Request:
DELETE /api/media/42
Authorization: Bearer {session_token}

Response (200):
{
  "message": "Media deleted"
}

Response (404):
{
  "error": "Media not found"
}

Response (409):
{
  "error": "Cannot delete media with published posts"
}
```

---

### 4. Caption Generation Routes (`/api/captions/*`)

#### `POST /api/captions/generate`
Generate AI captions for media.

```
Request:
POST /api/captions/generate
Authorization: Bearer {session_token}
Content-Type: application/json

{
  "media_id": 42,              // OR
  "media_url": "https://...",  // file path or URL
  "topic": "AI project demo",
  "count": 3                   // How many captions to generate
}

Response (200):
{
  "captions": [
    {
      "text": "Just launched our AI platform... [full caption]",
      "preview": "Just launched our AI platform...",
      "sentiment": "excited",
      "length": 245
    },
    {
      "text": "Excited to share...",
      "preview": "Excited to share...",
      "sentiment": "positive",
      "length": 189
    },
    {
      "text": "Check out what we've been building...",
      "preview": "Check out what we've been...",
      "sentiment": "proud",
      "length": 267
    }
  ],
  "generation_time_ms": 1250
}

Response (400):
{
  "error": "Media file not found"
}

Response (503):
{
  "error": "Caption generation service unavailable"
}
```

---

### 5. Post Routes (`/api/posts/*`)

#### `POST /api/posts/create`
Create a draft post.

```
Request:
POST /api/posts/create
Authorization: Bearer {session_token}
Content-Type: application/json

{
  "media_id": 42,
  "caption": "Full caption text here",
  "caption_source": "user_written"  // or "ai_generated"
}

Response (201):
{
  "id": 100,
  "user_id": 1,
  "media_id": 42,
  "caption": "Full caption text here",
  "status": "draft",
  "created_at": "2026-08-18T10:00:00Z"
}

Response (400):
{
  "error": "Media file not found"
}
```

#### `GET /api/posts`
List user's posts.

```
Request:
GET /api/posts?status=published&limit=20&offset=0&sort=published_at_desc
Authorization: Bearer {session_token}

Query Parameters:
- status: draft|scheduled|published|failed (optional)
- limit: 1-100 (default 20)
- offset: pagination offset
- sort: published_at_desc|created_at_desc

Response (200):
{
  "total": 15,
  "items": [
    {
      "id": 100,
      "caption": "...",
      "status": "published",
      "published_at": "2026-08-18T10:00:00Z",
      "likes_count": 45,
      "comments_count": 12,
      "views_count": 1200,
      "linkedin_post_url": "https://linkedin.com/feed/update/..."
    },
    ...
  ]
}
```

#### `GET /api/posts/{id}`
Get post details.

```
Request:
GET /api/posts/100
Authorization: Bearer {session_token}

Response (200):
{
  "id": 100,
  "user_id": 1,
  "media_id": 42,
  "caption": "...",
  "status": "published",
  "published_at": "2026-08-18T10:00:00Z",
  "likes_count": 45,
  "comments_count": 12,
  "shares_count": 5,
  "views_count": 1200,
  "linkedin_post_id": "7124567890123456789",
  "linkedin_post_url": "https://linkedin.com/feed/update/...",
  "created_at": "2026-08-18T09:00:00Z",
  "updated_at": "2026-08-18T10:00:00Z"
}
```

#### `PATCH /api/posts/{id}`
Update draft post.

```
Request:
PATCH /api/posts/100
Authorization: Bearer {session_token}
Content-Type: application/json

{
  "caption": "Updated caption text"
}

Response (200):
{
  "id": 100,
  "caption": "Updated caption text",
  "status": "draft",
  "updated_at": "2026-08-18T10:05:00Z"
}

Response (409):
{
  "error": "Cannot edit published post"
}
```

#### `POST /api/posts/{id}/publish`
Publish post to LinkedIn immediately.

```
Request:
POST /api/posts/100/publish
Authorization: Bearer {session_token}

Response (200):
{
  "id": 100,
  "status": "published",
  "published_at": "2026-08-18T10:00:00Z",
  "linkedin_post_id": "7124567890123456789",
  "linkedin_post_url": "https://linkedin.com/feed/update/...",
  "message": "Post published to LinkedIn"
}

Response (409):
{
  "error": "LinkedIn not connected"
}

Response (500):
{
  "error": "LinkedIn API error: {details}"
}
```

#### `POST /api/posts/{id}/schedule`
Schedule post for later publishing.

```
Request:
POST /api/posts/100/schedule
Authorization: Bearer {session_token}
Content-Type: application/json

{
  "scheduled_for": "2026-08-20T10:00:00",  // ISO 8601
  "timezone": "America/New_York"             // User's timezone
}

Response (201):
{
  "id": 100,
  "status": "scheduled",
  "scheduled_for": "2026-08-20T10:00:00Z",
  "scheduled_post_id": 50,
  "message": "Post scheduled for 2026-08-20 10:00 AM"
}

Response (400):
{
  "error": "Scheduled time must be in the future"
}
```

#### `DELETE /api/posts/{id}`
Delete post (only drafts and scheduled).

```
Request:
DELETE /api/posts/100
Authorization: Bearer {session_token}

Response (200):
{
  "message": "Post deleted"
}

Response (409):
{
  "error": "Cannot delete published post"
}
```

---

### 6. Scheduled Posts Routes (`/api/scheduled-posts/*`)

#### `GET /api/scheduled-posts`
List scheduled posts.

```
Request:
GET /api/scheduled-posts?limit=10&offset=0
Authorization: Bearer {session_token}

Response (200):
{
  "total": 5,
  "items": [
    {
      "id": 50,
      "post_id": 100,
      "caption": "...",
      "scheduled_for": "2026-08-20T10:00:00Z",
      "timezone": "America/New_York",
      "is_executed": false,
      "execution_attempts": 0
    },
    ...
  ]
}
```

#### `PATCH /api/scheduled-posts/{id}`
Update scheduled post.

```
Request:
PATCH /api/scheduled-posts/50
Authorization: Bearer {session_token}
Content-Type: application/json

{
  "scheduled_for": "2026-08-21T15:00:00"
}

Response (200):
{
  "id": 50,
  "scheduled_for": "2026-08-21T15:00:00Z"
}
```

#### `DELETE /api/scheduled-posts/{id}`
Cancel scheduled post.

```
Request:
DELETE /api/scheduled-posts/50
Authorization: Bearer {session_token}

Response (200):
{
  "message": "Scheduled post cancelled"
}

Response (409):
{
  "error": "Post already executed"
}
```

---

### 7. Activity Log Routes (`/api/activity/*`)

#### `GET /api/activity`
List user's activity log (audit trail).

```
Request:
GET /api/activity?limit=50&offset=0&action=post_published
Authorization: Bearer {session_token}

Query Parameters:
- limit: 1-100 (default 50)
- offset: pagination
- action: Filter by action type (optional)

Response (200):
{
  "total": 127,
  "items": [
    {
      "id": 1001,
      "action_type": "post_published",
      "resource_type": "post",
      "resource_id": 100,
      "description": "Published post #100 to LinkedIn",
      "success": true,
      "created_at": "2026-08-18T10:00:00Z"
    },
    {
      "id": 1000,
      "action_type": "media_uploaded",
      "resource_type": "media",
      "resource_id": 42,
      "description": "Uploaded video_demo.mp4",
      "success": true,
      "created_at": "2026-08-18T09:30:00Z"
    },
    ...
  ]
}
```

---

### 8. Dashboard Routes (`/dashboard/*`)

#### `GET /dashboard`
Main dashboard page (HTML).

```
Request:
GET /dashboard
Authorization: Bearer {session_token}

Response: HTML page with:
- User profile card
- LinkedIn connection status
- Recent posts list
- Quick stats (total posts, engagement)
- Call-to-action buttons
```

#### `GET /dashboard/linkedin`
LinkedIn connection page.

```
Request:
GET /dashboard/linkedin
Authorization: Bearer {session_token}

Response: HTML page with:
- Connection status
- "Connect LinkedIn" button
- Account details if connected
- Disconnect option
```

---

## Error Responses

All endpoints return standard error format:

```json
{
  "error": "Error message",
  "error_code": "ERROR_CODE",
  "details": "Additional context (optional)",
  "timestamp": "2026-08-18T10:00:00Z"
}
```

### Common Status Codes

| Code | Meaning | When |
|------|---------|------|
| 200 | Success | Request successful |
| 201 | Created | Resource created |
| 400 | Bad Request | Invalid input |
| 401 | Unauthorized | Missing/invalid token |
| 403 | Forbidden | No permission |
| 404 | Not Found | Resource not found |
| 409 | Conflict | State conflict (e.g., already published) |
| 413 | Payload Too Large | File too large |
| 429 | Too Many Requests | Rate limited |
| 500 | Server Error | Internal error |
| 503 | Service Unavailable | External service down |

---

## Rate Limiting

```
Rate limits per user:
- General: 100 requests/minute
- Upload: 10 requests/minute
- LinkedIn API: 50 requests/hour (LinkedIn's limit)

Headers:
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1660815600
```

---

## Next Document

→ **[MCP_TOOLS.md](MCP_TOOLS.md)** - Claude MCP tool specifications
