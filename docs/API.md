# API Documentation

## Overview

The Social Media Automation Agent provides a comprehensive REST API for managing users, posts, scheduling, uploads, and analytics.

**Base URL:** `http://localhost:5000/api`

**Response Format:** JSON

---

## Authentication

Currently no authentication required (development mode). Will add JWT in Phase 2+.

---

## User Management Endpoints

### Create User
**POST** `/users`

Create a new user account for Instagram automation.

**Request Body:**
```json
{
  "instagram_username": "your_username",
  "instagram_password": "your_password",
  "timezone": "Asia/Kolkata",
  "account_name": "My Account"
}
```

**Response (201):**
```json
{
  "id": 1,
  "instagram_username": "your_username",
  "instagram_connected": false,
  "timezone": "Asia/Kolkata",
  "account_name": "My Account",
  "created_at": "2026-08-14T10:00:00"
}
```

---

### Get User
**GET** `/users/<user_id>`

Retrieve user information.

**Response (200):**
```json
{
  "id": 1,
  "instagram_username": "your_username",
  "instagram_connected": true,
  "linkedin_connected": false,
  "timezone": "Asia/Kolkata",
  "preferences": {...}
}
```

---

### Authenticate User
**POST** `/users/<user_id>/authenticate`

Connect Instagram account to the automation system.

**Request Body:**
```json
{
  "password": "your_password"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Authentication successful",
  "user": {...}
}
```

---

## Post/Reel Management

### Create Post
**POST** `/posts`

Create a new post.

**Request Body:**
```json
{
  "user_id": 1,
  "video_path": "/data/reels/video.mp4",
  "caption": "Amazing content! #instagram",
  "hashtags": "instagram,amazing,content",
  "platform": "instagram"
}
```

**Response (201):**
```json
{
  "id": 1,
  "user_id": 1,
  "caption": "Amazing content! #instagram",
  "status": "draft",
  "platform": "instagram",
  "created_at": "2026-08-14T10:00:00"
}
```

---

### Get Post
**GET** `/posts/<post_id>`

Retrieve post details.

**Response (200):**
```json
{
  "id": 1,
  "user_id": 1,
  "caption": "Amazing content! #instagram",
  "status": "posted",
  "posted_at": "2026-08-14T12:00:00",
  "views": 150,
  "likes": 25,
  "comments": 5,
  "engagement_rate": 20.0
}
```

---

### Get User's Posts
**GET** `/users/<user_id>/posts?status=scheduled`

Retrieve all posts for a user. Optional `status` filter: `draft`, `queued`, `scheduled`, `posted`, `failed`.

**Response (200):**
```json
{
  "count": 5,
  "posts": [...]
}
```

---

### Schedule Post
**POST** `/posts/<post_id>/schedule`

Schedule a post for specific time.

**Request Body:**
```json
{
  "scheduled_time": "2026-08-14T18:30:00+05:30"
}
```

**Response (200):**
```json
{
  "success": true,
  "job_id": "post_1_1723635000",
  "post": {...}
}
```

---

### Schedule at Optimal Time
**POST** `/posts/<post_id>/schedule-optimal`

Automatically schedule post at optimal engagement time.

**Request Body:** (empty)

**Response (200):**
```json
{
  "success": true,
  "job_id": "post_1_1723635000",
  "message": "Post scheduled at optimal time",
  "post": {...}
}
```

---

### Cancel Post
**DELETE** `/posts/<post_id>`

Cancel a scheduled post.

**Response (200):**
```json
{
  "success": true,
  "message": "Post cancelled"
}
```

---

## Upload Endpoints

### Upload Reel
**POST** `/upload`

Upload a video reel.

**Form Data:**
- `user_id` (integer, required): User ID
- `file` (file, required): Video file (MP4, MOV, AVI, MKV, WEBM)

**Response (201):**
```json
{
  "success": true,
  "message": "Reel uploaded successfully",
  "reel": {
    "filename": "20260814_100000_video.mp4",
    "size_mb": 45.2,
    "duration_seconds": 60,
    "has_thumbnail": true
  }
}
```

---

### Get User's Reels
**GET** `/users/<user_id>/reels`

List all uploaded reels for a user.

**Response (200):**
```json
{
  "count": 3,
  "reels": [
    {
      "filename": "20260814_100000_video.mp4",
      "size_mb": 45.2,
      "duration_seconds": 60,
      "has_thumbnail": true
    }
  ]
}
```

---

## Analytics Endpoints

### Get User Analytics
**GET** `/users/<user_id>/analytics`

Retrieve analytics summary for a user.

**Response (200):**
```json
{
  "total_posts_analyzed": 25,
  "average_likes": 45,
  "average_comments": 8,
  "best_posting_hours": [18, 19, 12, 13, 20, 14],
  "best_posting_days": [4, 3, 5],
  "peak_engagement_hour": 19,
  "confidence": 85
}
```

---

### Analyze Engagement
**POST** `/users/<user_id>/analyze`

Fetch and analyze recent posts for engagement patterns.

**Request Body:** (empty)

**Response (200):**
```json
{
  "success": true,
  "analytics": {
    "total_posts_analyzed": 30,
    "average_likes": 52.5,
    "average_comments": 9.2,
    "best_posting_hours": [18, 19, 12, 13, 20, 14],
    "best_posting_days": [4, 3, 5],
    "peak_engagement_hour": 19,
    "peak_engagement_day": 4
  }
}
```

---

### Get Optimal Posting Time
**GET** `/users/<user_id>/optimal-time`

Get the next optimal time to post.

**Response (200):**
```json
{
  "optimal_time": "2026-08-14T18:00:00+05:30",
  "optimal_hour": 18,
  "optimal_day": "Wednesday",
  "wait_hours": 4.5,
  "wait_minutes": 270,
  "confidence": 85,
  "best_hours": [18, 19, 12],
  "best_days": [2, 3]
}
```

---

## Scheduler Endpoints

### Get Scheduler Status
**GET** `/scheduler/status`

Get current scheduler status.

**Response (200):**
```json
{
  "total_jobs": 5,
  "running": true,
  "initialized": true
}
```

---

### Get Scheduled Jobs
**GET** `/scheduler/jobs?user_id=1`

List all scheduled jobs. Optional `user_id` filter.

**Response (200):**
```json
{
  "count": 3,
  "jobs": [
    {
      "id": 1,
      "user_id": 1,
      "caption": "Amazing content! #instagram",
      "scheduled_time": "2026-08-14T18:00:00+05:30",
      "job_id": "post_1_1723635000",
      "platform": "instagram"
    }
  ]
}
```

---

### Get Pending Posts
**GET** `/scheduler/pending?user_id=1`

List all pending/queued posts. Optional `user_id` filter.

**Response (200):**
```json
{
  "count": 2,
  "posts": [
    {
      "id": 2,
      "user_id": 1,
      "status": "queued",
      "caption": "Another post...",
      "created_at": "2026-08-14T10:00:00"
    }
  ]
}
```

---

## Queue Endpoints

### Add to Queue
**POST** `/queue/add`

Add a post to the posting queue.

**Request Body:**
```json
{
  "post_id": 1
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Post added to queue",
  "post": {...}
}
```

---

### Remove from Queue
**DELETE** `/queue/<post_id>`

Remove a post from the queue.

**Response (200):**
```json
{
  "success": true,
  "message": "Post removed from queue"
}
```

---

## Statistics Endpoints

### Get System Stats
**GET** `/stats`

Get overall system statistics.

**Response (200):**
```json
{
  "users": 5,
  "posts": {
    "total": 45,
    "posted": 30,
    "scheduled": 10,
    "pending": 5
  },
  "scheduler": {
    "total_jobs": 10,
    "running": true,
    "initialized": true
  }
}
```

---

## Health Check

### Health Check
**GET** `/health`

Check application health.

**Response (200):**
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0"
}
```

---

### API Status
**GET** `/api/status`

Get API status and configuration.

**Response (200):**
```json
{
  "app": "Social Media Automation Agent",
  "version": "1.0.0",
  "environment": "development",
  "debug": true,
  "database": "sqlite:///data/automation.db",
  "instagram_configured": true,
  "claude_configured": true
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "error": "Invalid request parameters"
}
```

### 401 Unauthorized
```json
{
  "error": "Instagram not connected"
}
```

### 404 Not Found
```json
{
  "error": "Post not found"
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error"
}
```

---

## Rate Limiting

Not implemented yet. Will be added in Phase 2.

---

## Pagination

Not implemented yet. Will be added in Phase 2.

---

## Example Workflow

### 1. Create User
```bash
curl -X POST http://localhost:5000/api/users \
  -H "Content-Type: application/json" \
  -d '{
    "instagram_username": "myaccount",
    "instagram_password": "mypassword",
    "timezone": "Asia/Kolkata"
  }'
```

### 2. Authenticate
```bash
curl -X POST http://localhost:5000/api/users/1/authenticate \
  -H "Content-Type: application/json" \
  -d '{"password": "mypassword"}'
```

### 3. Upload Reel
```bash
curl -X POST http://localhost:5000/api/upload \
  -F "user_id=1" \
  -F "file=@video.mp4"
```

### 4. Create Post
```bash
curl -X POST http://localhost:5000/api/posts \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "video_path": "/data/reels/video.mp4",
    "caption": "Check this out!",
    "platform": "instagram"
  }'
```

### 5. Schedule at Optimal Time
```bash
curl -X POST http://localhost:5000/api/posts/1/schedule-optimal
```

---

**API Version:** 1.0.0  
**Last Updated:** 2026-08-14  
**Status:** Phase 1 Complete
