# Post Pilot MCP Server

**Let Claude manage your LinkedIn social media.** 📱

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that connects Claude to Post Pilot, giving Claude the power to:

- 📤 **Upload reels** — from URLs (Google Drive, Dropbox, S3) or direct files
- 🤖 **Generate AI captions** — Claude-powered caption suggestions  
- ✍️ **Draft posts** — multi-turn conversations with AI for full composition
- 📅 **Schedule reels** — set up posts for future times
- 🚀 **Publish immediately** — push reels live to LinkedIn (with confirmation)
- 📋 **List reels** — see what's available to post

Use it in **Claude Desktop**, **claude.ai**, or **Claude Code** to control Post Pilot entirely through conversation.

---

## Why This Matters

**No UI context switching.** Stay in Claude and say:
```
Upload my presentation demo from Google Drive and schedule it for tomorrow at 9am 
with a caption about our product launch
```

Claude will:
1. Get your Google Drive link
2. Upload the video to Post Pilot
3. Draft a compelling caption
4. Schedule it for optimal engagement time
5. Confirm completion

All without leaving the chat.

---

## Features

### 📤 Smart Video Upload
- **Google Drive connector**: Seamlessly grab videos from your Drive (with shareable links)
- **Direct URLs**: Upload from Dropbox, S3, or any hosted video
- **Local files**: Attach small clips directly (for testing)
- **Server-side fetch**: Videos process on the backend—no chat size limits

### 🤖 AI-Powered Captions
- **Claude composition**: Uses the same AI that powers the web app
- **Multi-turn refinement**: Iterate with Claude until perfect
- **Smart suggestions**: Analyzes your reel and proposes angle, content, timing
- **3 caption options**: Get alternatives in one call

### 📅 Scheduling & Publishing
- **Schedule posts**: Pick a specific date/time in your timezone
- **Publish now**: Go live immediately (irreversible—confirmed before publishing)
- **Reel management**: List all uploaded reels, track what's ready to post

---

## Google Drive Integration

### How It Works
1. **In your Google Drive**: Create a folder for videos you want to post
2. **Share the link**: Right-click → Share → "Anyone with the link can view"
3. **Get the shareable link**: Copy it (e.g., `https://drive.google.com/file/d/...`)
4. **Convert to direct-download link**: Remove `/view` and add `?export=download`
5. **Tell Claude**: "Upload this from Google Drive: [link]"

### Example Workflow
```
You: "Upload my Q4 product demo from Google Drive"
Claude: "What's the shareable link?"
You: "https://drive.google.com/file/d/1xyz123/view"
Claude: Converts link → uploads → lists → suggests caption
Claude: "I'll schedule it for tomorrow 10am with a product-focused angle. Ready?"
You: "Yes"
Claude: ✅ Done. Post queued for 2026-08-20 10:00 AM
```

---

## Tools Reference

### `upload_reel_from_url` 📤
Upload a reel from a direct video link (Google Drive, Dropbox, S3, etc.)

**Parameters:**
- `url` (required): Direct video URL (converts Google Drive links)
- `filename` (optional): Custom filename for storage

**Example:**
```
upload_reel_from_url(
  url="https://drive.google.com/uc?export=download&id=...",
  filename="Q4_demo.mp4"
)
```

**Output:**
```
Uploaded: Q4_demo.mp4 (45.3s, 120MB)
Publishing as: john@company.com
```

### `upload_reel` 📎
Upload a reel by attaching a video file directly (small clips only)

**Parameters:**
- `filename` (required): Original filename
- `base64Data` (required): Video file as base64

**Limitation:** Best for clips < 5MB. For real reels, use `upload_reel_from_url`.

### `list_reels` 📽️
See all your uploaded reels ready to post

**Output:**
```
Publishing as: john@company.com

- Q4_demo.mp4 (45.3s, 120MB)
- product_walkthrough.mp4 (30.1s, 85MB)
- short_clip.mp4 (15.2s, 42MB)
```

### `draft_post` 💬
Draft a LinkedIn post with Claude's help (multi-turn conversation)

**Parameters:**
- `message` (required): What you want posted (e.g., "schedule my best reel about AI for tomorrow at 9am")
- `priorDraft` (optional): Continue editing a previous draft

**Output:**
```
I'd recommend posting your Q4 demo with a focus on the new features...

Draft:
{
  "reel_filename": "Q4_demo.mp4",
  "caption": "Just dropped: 3 features reshaping how teams...",
  "angle": "product-focused",
  "when": "2026-08-20T09:00:00Z"
}

Ready to publish? (current: not ready)
```

### `publish_reel` 🚀
Publish a reel to LinkedIn **immediately** (irreversible!)

**Parameters:**
- `videoPath` (required): Path to uploaded reel
- `caption` (required): Post caption text

**⚠️ Warning:** This is LIVE and cannot be undone.

### `schedule_reel` ⏰
Schedule a reel to post at a future time

**Parameters:**
- `videoPath` (required): Path to uploaded reel
- `caption` (required): Post caption
- `scheduledTime` (required): `YYYY-MM-DDTHH:MM` in your local timezone

**Example:**
```
schedule_reel(
  videoPath="Q4_demo.mp4",
  caption="Just dropped: 3 features reshaping how teams collaborate...",
  scheduledTime="2026-08-20T09:00"
)
```

### `show_available_commands` 📋
Get a full reference of all available commands and pro tips

---

## Typical Workflow

```
1. getting_started 
   ↓
2. upload_reel_from_url(url="https://drive.google.com/...") 
   ↓
3. list_reels (verify upload)
   ↓
4. draft_post(message="Share this with a focus on our new feature") 
   ↓
5. (Multi-turn conversation to refine caption & timing)
   ↓
6. publish_reel OR schedule_reel
   ↓
7. ✅ Posted to LinkedIn!
```

---

## Quick Start

**Install in 5 minutes:** [👉 INSTALLATION.md](INSTALLATION.md)

**Technical setup:** [👉 SETUP.md](SETUP.md)

---

## Security & Safety

**Two-factor protection:**
- **GitHub OAuth** gates who can call these tools (allowlist only)
- **Bearer token auth** ensures calls act as one fixed backend account
- **publish_reel** is irreversible and requires explicit confirmation

**Privacy:**
- Videos upload server-side—no file size limits tied to chat
- Your LinkedIn credentials never leave the backend
- All communication uses OAuth 2.0 and HTTPS

---

## Built On

- [Cloudflare Workers](https://workers.cloudflare.com) — free, always-on (no idle sleep)
- [Model Context Protocol](https://modelcontextprotocol.io/) — Anthropic's open standard for tool integration
- [GitHub OAuth](https://docs.github.com/en/developers/apps/building-oauth-apps) — secure authentication
- [Post Pilot Backend API](https://github.com/saksham-gagneja-indxx/postpilot)
- [Claude AI](https://claude.ai/) — for caption generation and composition

---

## Troubleshooting

### Google Drive Links Not Working
**Problem:** "Invalid repository URL" error

**Solution:** 
1. Copy your Drive share link: `https://drive.google.com/file/d/ABC123/view`
2. Convert to direct-download: `https://drive.google.com/uc?export=download&id=ABC123`
3. Pass to `upload_reel_from_url`

### Video Upload Fails
**Problem:** "Could not fetch video"

**Solution:**
- Check link is public (shareable link works)
- For Drive links, use the `export=download` format
- Test link in browser first—it should download or play

### Post Already Published?
**Problem:** Can't undo a published post

**Solution:**
- Use `schedule_reel` instead of `publish_reel` to plan ahead
- Always review draft before confirming publish
- LinkedIn doesn't provide an API to delete posts from Post Pilot

---

## Documentation

- **[Installation Guide](INSTALLATION.md)** — 5-minute setup
- **[Technical Setup](SETUP.md)** — Secrets, Cloudflare, GitHub OAuth
- **[Integration Testing](INTEGRATION_TEST.md)** — Verify your setup
- **[Publishing Guide](PUBLISHING.md)** — Deploy to the MCP Registry

---

## What's Next?

- Add analytics dashboard
- Support for video editing/trimming
- Multi-account management
- LinkedIn article composition
- Hashtag optimization

---

**Ready to get started?** [👉 Installation](INSTALLATION.md)

Generated: 2026-08-19  
Registry: [MCP Server Registry](https://registry.modelcontextprotocol.io/)  
npm: [@sakshamgagneja/post-pilot-mcp](https://www.npmjs.com/package/@sakshamgagneja/post-pilot-mcp)
