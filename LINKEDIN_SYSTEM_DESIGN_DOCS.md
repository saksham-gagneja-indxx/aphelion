# LinkedIn Posting System Design & Post Pilot Architecture

Complete technical documentation for POST_PILOT MCP server and LinkedIn social media automation.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Google Drive Integration](#google-drive-integration)
4. [API Reference](#api-reference)
5. [Installation & Setup](#installation--setup)
6. [Deployment](#deployment)
7. [Security Model](#security-model)
8. [Troubleshooting](#troubleshooting)

---

## System Overview

**POST_PILOT** is an MCP (Model Context Protocol) server that enables Claude to manage LinkedIn social media automation through conversation.

### What It Does
- Upload videos from Google Drive, Dropbox, S3, or local files
- Generate AI captions using Claude
- Draft LinkedIn posts with multi-turn conversation
- Schedule posts for future times
- Publish posts immediately to LinkedIn

### Key Features
- **Server-side video processing**: No chat size limits
- **Google Drive seamless integration**: Direct video upload from shared Drive links
- **AI-powered composition**: Same Claude engine as the web app
- **Scheduled publishing**: Optimal timing for engagement
- **Two-factor security**: GitHub OAuth + bearer token authentication

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────┐
│                    Claude (Any Client)                   │
│                    (Desktop/Web/Code)                    │
└────────────────┬────────────────────────────────────────┘
                 │ (MCP Protocol)
┌────────────────▼────────────────────────────────────────┐
│            POST_PILOT MCP Server                         │
│         (Cloudflare Workers)                            │
│  • Tool registration & orchestration                    │
│  • GitHub OAuth flow                                    │
│  • Google Drive link handling                          │
└────────────────┬────────────────────────────────────────┘
                 │ (HTTP/Bearer Token)
┌────────────────▼────────────────────────────────────────┐
│         Post Pilot Backend API                          │
│    (Flask on Render/Heroku)                            │
│  • Video upload & storage (S3)                         │
│  • LinkedIn OAuth & token management                   │
│  • Post scheduling & publishing                        │
│  • Database (PostgreSQL)                               │
└────────────────┬────────────────────────────────────────┘
                 │
     ┌───────────┼───────────┐
     ▼           ▼           ▼
  Google Drive  LinkedIn   AWS S3
  (source)      (publish)  (storage)
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Client** | Claude Desktop/Web | User interface |
| **Protocol** | MCP | Tool definition & execution |
| **Worker** | Cloudflare Workers | Serverless compute (always-on) |
| **Auth** | GitHub OAuth 2.0 | User authentication |
| **Backend** | Flask + Python | API & business logic |
| **Database** | PostgreSQL (Supabase) | Persistent storage |
| **Storage** | AWS S3 | Video/media storage |
| **Integration** | LinkedIn API v2 | Social publishing |
| **Video Source** | Google Drive API | Shareable link handling |

---

## Google Drive Integration

### How It Works

Users can share videos from their Google Drive with POST_PILOT without downloading/re-uploading:

```
User's Google Drive
       │
       ├─ Share video (public link)
       │  e.g., https://drive.google.com/file/d/ABC123XYZ/view
       │
       └─ Convert to direct-download
          https://drive.google.com/uc?export=download&id=ABC123XYZ
          
          │
          ▼
       Claude (via MCP)
          │
       "upload this video from Google Drive"
          │
          ▼
    POST_PILOT MCP Server
          │
       Fetches from converted URL
          │
          ▼
     Post Pilot Backend
          │
       Download video → Store in S3
          │
          ▼
    Ready to Caption/Publish
```

### Implementation Details

**Link Conversion**:
```javascript
function convertDriveLink(shareLink) {
  // Input:  https://drive.google.com/file/d/ABC123XYZ/view
  // Output: https://drive.google.com/uc?export=download&id=ABC123XYZ
  
  const match = shareLink.match(/\/d\/([a-zA-Z0-9-_]+)/);
  if (!match) throw new Error("Invalid Drive link");
  
  const fileId = match[1];
  return `https://drive.google.com/uc?export=download&id=${fileId}`;
}
```

**Backend Processing**:
```python
# In backend/api/media_routes.py
@app.route('/api/media/upload-from-url', methods=['POST'])
def upload_from_url():
    url = request.json.get('url')
    
    # Handle Google Drive links
    if 'drive.google.com' in url:
        url = convert_drive_link(url)
    
    # Fetch video server-side
    response = requests.get(url, stream=True, timeout=30)
    
    # Upload to S3
    s3_key = f"reels/{user_id}/{filename}"
    s3.upload_fileobj(response.raw, bucket, s3_key)
    
    return {"reel_id": reel_id, "url": s3_url}
```

### Security Considerations

- **Public links only**: Users must enable "Anyone with the link" sharing
- **No authentication required**: POST_PILOT doesn't need Google Drive API credentials
- **Server-side fetch**: Video never passes through Claude/MCP channel
- **Size limits**: Backend enforces reasonable video size (e.g., 500MB max)

---

## API Reference

### Tools Available in Claude

#### 1. `upload_reel_from_url`
Upload a video from Google Drive, Dropbox, S3, or any hosted URL.

```javascript
{
  name: "upload_reel_from_url",
  description: "Upload a reel from a direct video URL...",
  inputSchema: {
    type: "object",
    properties: {
      url: { 
        type: "string",
        description: "Direct video URL (e.g., Google Drive export link)"
      },
      filename: {
        type: "string",
        description: "Optional: custom filename"
      }
    },
    required: ["url"]
  }
}
```

**Example Claude Conversation**:
```
User: "Upload my Q4 demo from Google Drive"
Claude: "I'll help. What's the shareable link?"
User: "https://drive.google.com/file/d/ABC123/view"
Claude: [Converts to download link]
        [Uploads to backend]
        "✅ Uploaded: Q4_demo.mp4 (45.3s, 120MB)"
```

#### 2. `list_reels`
List all uploaded reels ready to post.

```javascript
{
  name: "list_reels",
  description: "See all your uploaded reels",
  inputSchema: { type: "object", properties: {} }
}
```

**Response**:
```
Publishing as: john@company.com

- Q4_demo.mp4 (45.3s, 120MB)
- product_walkthrough.mp4 (30.1s, 85MB)
- short_clip.mp4 (15.2s, 42MB)
```

#### 3. `draft_post`
Draft a LinkedIn post with Claude's help.

```javascript
{
  name: "draft_post",
  description: "Chat with AI to plan a post...",
  inputSchema: {
    type: "object",
    properties: {
      message: {
        type: "string",
        description: "What you want posted (e.g., 'share my best reel about AI')"
      },
      priorDraft: {
        type: "object",
        description: "Continue editing a previous draft",
        properties: {
          reel_filename: { type: "string" },
          caption: { type: "string" },
          angle: { type: "string" },
          when: { type: "string" }
        }
      }
    },
    required: ["message"]
  }
}
```

#### 4. `schedule_reel`
Schedule a post for a specific time.

```javascript
{
  name: "schedule_reel",
  description: "Schedule a reel to post at a future time",
  inputSchema: {
    type: "object",
    properties: {
      videoPath: { type: "string" },
      caption: { type: "string" },
      scheduledTime: { 
        type: "string",
        description: "YYYY-MM-DDTHH:MM in local timezone"
      }
    },
    required: ["videoPath", "caption", "scheduledTime"]
  }
}
```

#### 5. `publish_reel`
Publish a post immediately (irreversible).

```javascript
{
  name: "publish_reel",
  description: "Publish a reel to LinkedIn NOW (irreversible)",
  inputSchema: {
    type: "object",
    properties: {
      videoPath: { type: "string" },
      caption: { type: "string" }
    },
    required: ["videoPath", "caption"]
  }
}
```

---

## Installation & Setup

### Local Development

```bash
# Clone repo
git clone https://github.com/saksham-gagneja-indxx/postpilot.git
cd postpilot/mcp-server

# Install
npm install

# Create .dev.vars with secrets
cp .env.example .dev.vars

# Start dev server
npm run dev
```

### Production Deployment

```bash
# Build
npm run build

# Deploy to Cloudflare
npx wrangler publish
```

### Required Environment Variables

```
GITHUB_CLIENT_ID          # From GitHub OAuth App
GITHUB_CLIENT_SECRET      # From GitHub OAuth App
BACKEND_API_URL           # Post Pilot backend (e.g., https://...-wk5g.onrender.com)
BACKEND_API_KEY           # Bearer token for backend API
BACKEND_USER_ID           # User ID to post as (usually 0)
ALLOWED_GITHUB_USERNAMES  # Comma-separated list of allowed users
COOKIE_ENCRYPTION_KEY     # 32-byte base64 key for session encryption
```

---

## Deployment

### Current Deployment Status

- **MCP Server**: Deployed on Cloudflare Workers
- **Backend API**: Deployed on Render (free tier)
- **Database**: Supabase PostgreSQL
- **Storage**: AWS S3 (for videos)

### Deployment Checklist

- [x] GitHub OAuth App created
- [x] Cloudflare Worker deployed
- [x] Backend API running
- [x] Database initialized
- [x] S3 bucket configured
- [x] LinkedIn OAuth credentials configured
- [x] MCP Server registered (Claude Desktop, Web, Code)
- [x] Published to MCP Server Registry
- [x] npm package published (@sakshamgagneja/post-pilot-mcp@0.0.1)

---

## Security Model

### Authentication Flow

```
┌─ User opens Claude ─────────────────────────┐
│                                              │
│  Claude: "I need to use post-pilot tools"  │
│          Opens browser for OAuth            │
│                                              │
└─ Cloudflare Worker (MCP Server)             │
   │                                           │
   ├─ Checks GitHub OAuth (ALLOWED_GITHUB_...) │
   │  Only allowlisted users get real tools    │
   │                                           │
   ├─ On auth success: Issues session token   │
   │                                           │
   └─ Backend validates token on every call   │
```

### Token Security

- **Frontend → Backend**: Bearer token (encrypted)
- **Google Drive access**: Public links only (no OAuth needed)
- **LinkedIn credentials**: Stored encrypted in database
- **Session tokens**: Signed, short-lived, httponly cookies

---

## Troubleshooting

### Common Issues

**"Not authorized" error**
- Check GitHub username is in `ALLOWED_GITHUB_USERNAMES`
- Verify GitHub OAuth app is still valid

**Google Drive upload fails**
- Test link in browser first
- Ensure file is public ("Anyone with the link")
- Try the direct-download format:
  ```
  https://drive.google.com/uc?export=download&id=FILE_ID
  ```

**LinkedIn publish fails**
- Check backend LinkedIn OAuth is current
- Verify account being posted as has valid permissions
- Check video format is LinkedIn-compatible (H.264, .mp4)

**Worker timeout**
- If video > 100MB, may take > 30s
- Increase timeout in wrangler.toml
- Consider compressing video first

---

## Repository Links

- **Main Repo**: https://github.com/saksham-gagneja-indxx/postpilot
- **System Design Repo**: https://github.com/saksham-gagneja-indxx/linkedin-posting-system-design
- **MCP Registry**: https://registry.modelcontextprotocol.io/
- **npm Package**: https://www.npmjs.com/package/@sakshamgagneja/post-pilot-mcp

---

**Generated**: 2026-08-19  
**Version**: 1.0  
**Status**: Production Ready ✅
