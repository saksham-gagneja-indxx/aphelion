# Database Schema Design

**Version**: 1.0  
**Status**: Design Phase  
**Database**: PostgreSQL (production) / SQLite (development)

---

## Table of Contents
1. [Users Table](#users-table)
2. [LinkedIn Credentials Table](#linkedin-credentials-table)
3. [Media Files Table](#media-files-table)
4. [Posts Table](#posts-table)
5. [Scheduled Posts Table](#scheduled-posts-table)
6. [Activity Log Table](#activity-log-table)
7. [Sessions Table](#sessions-table)
8. [Relationships & Indexes](#relationships--indexes)

---

## Users Table

Stores user account information.

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    
    -- Identity
    clerk_id VARCHAR(255) UNIQUE NOT NULL,  -- From Clerk Auth
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    
    -- Profile
    avatar_url VARCHAR(1000),
    timezone VARCHAR(50) DEFAULT 'UTC',
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP,
    
    -- Settings
    preferences JSONB DEFAULT '{}'  -- User preferences, notification settings, etc.
);

-- Indexes
CREATE INDEX idx_users_clerk_id ON users(clerk_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_is_active ON users(is_active);
```

**Columns**:
- `id` - Unique identifier
- `clerk_id` - Clerk's user ID (for authentication)
- `email` - User's email address
- `full_name` - Display name
- `avatar_url` - Profile picture
- `timezone` - For scheduling posts
- `is_active` - Soft delete flag
- `preferences` - JSON for user settings
- `created_at` - Account creation time
- `updated_at` - Last modification
- `last_login_at` - Track usage

---

## LinkedIn Credentials Table

Stores encrypted LinkedIn OAuth credentials (one-to-one with users).

```sql
CREATE TABLE linkedin_credentials (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL,
    
    -- LinkedIn OAuth Token (ENCRYPTED)
    access_token_encrypted VARCHAR(2000) NOT NULL,
    refresh_token_encrypted VARCHAR(2000) NOT NULL,
    
    -- LinkedIn Account Info
    linkedin_person_urn VARCHAR(255),        -- e.g., "urn:li:person:ABC123"
    linkedin_account_name VARCHAR(255),      -- LinkedIn display name
    linkedin_profile_url VARCHAR(500),       -- LinkedIn profile URL
    
    -- Token Lifecycle
    token_expires_at TIMESTAMP,
    last_refreshed_at TIMESTAMP,
    refresh_count INTEGER DEFAULT 0,
    
    -- Status
    is_connected BOOLEAN DEFAULT true,
    connection_verified_at TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Key
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_linkedin_creds_user_id ON linkedin_credentials(user_id);
CREATE INDEX idx_linkedin_creds_is_connected ON linkedin_credentials(is_connected);
CREATE UNIQUE INDEX idx_linkedin_creds_unique ON linkedin_credentials(user_id);
```

**Columns**:
- `access_token_encrypted` - OAuth access token (AES-128 encrypted)
- `refresh_token_encrypted` - OAuth refresh token (encrypted)
- `linkedin_person_urn` - LinkedIn's unique person ID
- `token_expires_at` - When token expires
- `last_refreshed_at` - Last token refresh time
- `is_connected` - Whether connection is active
- `connection_verified_at` - Last verification time

**Security Note**: 
- Both tokens are encrypted using Fernet
- Encryption key stored in environment: `ENCRYPTION_KEY`
- Never stored or logged in plaintext
- Decrypted only when needed for LinkedIn API calls

---

## Media Files Table

Stores uploaded media (videos, images).

```sql
CREATE TABLE media_files (
    id SERIAL PRIMARY KEY,
    
    -- File Info
    user_id INTEGER NOT NULL,
    filename VARCHAR(255) NOT NULL,          -- Original filename
    file_size_bytes INTEGER NOT NULL,
    media_type VARCHAR(50) NOT NULL,         -- 'video' or 'image'
    mime_type VARCHAR(100) NOT NULL,         -- 'video/mp4', 'image/jpeg'
    file_extension VARCHAR(10) NOT NULL,     -- 'mp4', 'jpg', etc.
    
    -- Storage
    storage_path VARCHAR(500) NOT NULL,      -- Full path: /user_{id}/{uuid}.mp4
    storage_url VARCHAR(1000),                -- Public URL if applicable
    storage_service VARCHAR(50),              -- 's3', 'local', etc.
    
    -- File Details
    duration_seconds DECIMAL(10, 2),         -- For videos
    width INTEGER,                            -- Image/video width
    height INTEGER,                           -- Image/video height
    thumbnail_url VARCHAR(1000),              -- Generated thumbnail
    
    -- Metadata
    upload_completed_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Lifecycle
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP,
    expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '30 days'),
    
    -- Foreign Key
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_media_user_id ON media_files(user_id);
CREATE INDEX idx_media_created_at ON media_files(created_at);
CREATE INDEX idx_media_expires_at ON media_files(expires_at);
CREATE INDEX idx_media_is_deleted ON media_files(is_deleted);
```

**Columns**:
- `filename` - Original uploaded filename
- `file_size_bytes` - Size in bytes
- `storage_path` - Where file is stored
- `storage_url` - URL to access file
- `duration_seconds` - Video duration
- `thumbnail_url` - Generated preview image
- `expires_at` - Auto-cleanup date
- `is_deleted` - Soft delete flag

**Auto-Cleanup**: Files automatically deleted after 30 days (or when post is published)

---

## Posts Table

Stores published and draft posts.

```sql
CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    
    -- Ownership
    user_id INTEGER NOT NULL,
    media_file_id INTEGER NOT NULL,
    
    -- Content
    caption TEXT NOT NULL,                   -- Post caption/text
    caption_source VARCHAR(50),              -- 'user_written' or 'ai_generated'
    
    -- LinkedIn Info
    linkedin_post_id VARCHAR(255),           -- LinkedIn's post ID after publishing
    linkedin_post_url VARCHAR(500),          -- Full LinkedIn post URL
    
    -- Status
    status VARCHAR(50) NOT NULL,             -- 'draft', 'scheduled', 'published', 'failed'
    published_at TIMESTAMP,
    
    -- Engagement (optional, refreshed periodically)
    likes_count INTEGER DEFAULT 0,
    comments_count INTEGER DEFAULT 0,
    shares_count INTEGER DEFAULT 0,
    views_count INTEGER DEFAULT 0,
    engagement_updated_at TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Keys
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (media_file_id) REFERENCES media_files(id) ON DELETE RESTRICT
);

-- Indexes
CREATE INDEX idx_posts_user_id ON posts(user_id);
CREATE INDEX idx_posts_status ON posts(status);
CREATE INDEX idx_posts_published_at ON posts(published_at);
CREATE INDEX idx_posts_created_at ON posts(created_at);
CREATE UNIQUE INDEX idx_posts_linkedin_id ON posts(linkedin_post_id) WHERE linkedin_post_id IS NOT NULL;
```

**Columns**:
- `status` - Post lifecycle state
  - `draft` - Created but not published
  - `scheduled` - Waiting for scheduled time
  - `published` - Live on LinkedIn
  - `failed` - Publishing failed
- `caption_source` - Track if AI-generated or user-written
- `linkedin_post_id` - LinkedIn's post ID (for tracking)
- `engagement_*` - Stats (refreshed daily)

---

## Scheduled Posts Table

Stores scheduled post details (one-to-one with posts).

```sql
CREATE TABLE scheduled_posts (
    id SERIAL PRIMARY KEY,
    
    -- Reference
    post_id INTEGER UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,
    
    -- Scheduling
    scheduled_for TIMESTAMP NOT NULL,        -- When to publish
    timezone VARCHAR(50) NOT NULL,           -- User's timezone
    
    -- Status
    is_executed BOOLEAN DEFAULT false,
    execution_attempts INTEGER DEFAULT 0,
    last_execution_attempt_at TIMESTAMP,
    execution_error VARCHAR(500),            -- Error message if failed
    executed_at TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Keys
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_scheduled_posts_user_id ON scheduled_posts(user_id);
CREATE INDEX idx_scheduled_posts_scheduled_for ON scheduled_posts(scheduled_for);
CREATE INDEX idx_scheduled_posts_is_executed ON scheduled_posts(is_executed);
CREATE INDEX idx_scheduled_posts_next_batch ON scheduled_posts(scheduled_for) 
    WHERE is_executed = false AND scheduled_for <= CURRENT_TIMESTAMP;
```

**Columns**:
- `scheduled_for` - When to execute
- `timezone` - Respect user's timezone
- `is_executed` - Completion flag
- `execution_attempts` - Retry count
- `execution_error` - Failure reason

**Auto-Publish**: Scheduler queries posts where `scheduled_for <= NOW()` and `is_executed = false`

---

## Activity Log Table

Audit trail for all important actions.

```sql
CREATE TABLE activity_logs (
    id SERIAL PRIMARY KEY,
    
    -- Who
    user_id INTEGER NOT NULL,
    
    -- What
    action_type VARCHAR(50) NOT NULL,       -- 'upload', 'post_published', 'post_scheduled', etc.
    resource_type VARCHAR(50),              -- 'media', 'post', 'credential'
    resource_id INTEGER,
    
    -- Details
    description TEXT,
    metadata JSONB,                         -- Additional context
    
    -- Status
    success BOOLEAN DEFAULT true,
    error_message VARCHAR(500),
    
    -- Network
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    
    -- Timestamp
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Key
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_activity_user_id ON activity_logs(user_id);
CREATE INDEX idx_activity_action_type ON activity_logs(action_type);
CREATE INDEX idx_activity_created_at ON activity_logs(created_at);
CREATE INDEX idx_activity_resource ON activity_logs(resource_type, resource_id);
```

**Logged Actions**:
- `linkedin_connected` - LinkedIn account connected
- `linkedin_disconnected` - LinkedIn account disconnected
- `media_uploaded` - File uploaded
- `caption_generated` - AI caption generated
- `post_created` - Post created as draft
- `post_published` - Post published to LinkedIn
- `post_scheduled` - Post scheduled
- `post_deleted` - Post deleted
- `token_refreshed` - LinkedIn token refreshed
- `error_*` - Various error conditions

---

## Sessions Table

Stores user sessions (for API/MCP access).

```sql
CREATE TABLE sessions (
    id VARCHAR(255) PRIMARY KEY,             -- Session token (JWT)
    
    -- User
    user_id INTEGER NOT NULL,
    
    -- Session Details
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    
    -- Lifecycle
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_valid BOOLEAN DEFAULT true,
    
    -- Foreign Key
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);
CREATE INDEX idx_sessions_is_valid ON sessions(is_valid);
```

**Columns**:
- `id` - JWT token
- `expires_at` - Token expiration
- `is_valid` - Revocation flag
- `last_activity_at` - Track usage

---

## Relationships & Indexes

### Entity Relationship Diagram

```
┌─────────┐
│ Users   │
└────┬────┘
     │ 1
     │
     ├─────────── 1:1 ──────────┬───────────────────────────┐
     │                          │                           │
     │                   LinkedIn_Credentials         Activity_Logs
     │                          │                           │
     │                          │ 1                    Many│
     │                          │                           │
     │                          └────────────────┬──────────┘
     │
     ├─────────── 1:Many ────────────────┬──────────────────┐
     │                                    │                  │
     │                              Media_Files          Sessions
     │                                    │                  │
     │                                    │ 1                │
     │                                    │                  │
     │                                    │              (API access)
     │
     └─────────── 1:Many ──────┬──────────────────────┐
                               │                      │
                            Posts         Scheduled_Posts
                               │                      │
                               │ 1                 │ 1
                               │                      │
                               │          (extends)───┘
```

### Index Summary

| Table | Index | Purpose |
|-------|-------|---------|
| users | clerk_id | Fast auth lookups |
| users | is_active | Filter active users |
| linkedin_credentials | user_id (UNIQUE) | One credential per user |
| linkedin_credentials | is_connected | Find connected users |
| media_files | user_id | List user's files |
| media_files | expires_at | Auto-cleanup jobs |
| posts | user_id | User's posts |
| posts | status | Query by state |
| posts | linkedin_post_id (UNIQUE) | Prevent duplicates |
| scheduled_posts | scheduled_for | Find next batch to execute |
| scheduled_posts | is_executed | Find pending |
| activity_logs | user_id | Audit trail per user |
| activity_logs | action_type | Analytics |
| sessions | user_id | Active sessions |
| sessions | expires_at | Cleanup expired |

---

## Data Types & Constraints

### File Size Limits
```
Max upload: 100 MB
Max database: 1 GB per user (enforced at application level)
Max session size: 1 KB
```

### Character Encoding
```
Database: UTF-8 (supports all languages)
File names: Sanitized, ASCII safe
Captions: Up to 3,000 characters
```

### Encryption
```
Encrypted columns:
- linkedin_credentials.access_token_encrypted
- linkedin_credentials.refresh_token_encrypted

Method: Fernet (symmetric AES-128)
Key: ENCRYPTION_KEY environment variable
Salt: Derived from ENCRYPTION_KEY + random IV
```

---

## Migration Strategy

### Version 1.0 (Initial)
- Create all tables
- Set up indexes
- Create constraints

### Future Migrations
- Add columns without breaking changes
- Use `DEFAULT` values for backwards compatibility
- Use Alembic for database versioning

### Migration Script Example
```bash
# Create new database
alembic upgrade head

# Verify
psql -U user -d postpilot -c "\dt"  # List tables
psql -U user -d postpilot -c "\di"  # List indexes
```

---

## Performance Considerations

### Query Patterns
```sql
-- Get user's recent posts
SELECT * FROM posts 
WHERE user_id = ? AND status = 'published'
ORDER BY published_at DESC 
LIMIT 10;

-- Find posts to schedule
SELECT p.*, s.scheduled_for 
FROM posts p
JOIN scheduled_posts s ON p.id = s.post_id
WHERE p.user_id = ? 
  AND s.is_executed = false 
  AND s.scheduled_for <= NOW()
ORDER BY s.scheduled_for;

-- Get user's media files
SELECT * FROM media_files 
WHERE user_id = ? AND is_deleted = false
ORDER BY created_at DESC;
```

### Connection Pooling
```
Pool size: 10 connections
Max overflow: 5 connections
Pool pre-ping: true (verify alive)
Timeout: 30 seconds
```

### Caching
```
Cache by: User ID
TTL: 5 minutes
Invalidate on: Insert, update, delete
Items cached:
  - User profile
  - LinkedIn credentials
  - Active sessions
```

---

## Backup & Recovery

### Backup Strategy
```
Frequency: Daily at 2 AM UTC
Retention: 30 days
Method: Full + incremental
Encryption: AES-256 at rest

In S3:
s3://backups/postpilot/{date}.sql.gz.enc
```

### Recovery Testing
```
Test monthly:
- Full restore
- Point-in-time recovery
- Table recovery
```

---

## Next Document

→ **[API_ENDPOINTS.md](API_ENDPOINTS.md)** - Detailed API specifications
