# Installation Guide

Get Aphelion MCP running in 5 minutes.

## Prerequisites

- GitHub account (for OAuth)
- Cloudflare account (free)
- Claude Desktop, claude.ai, or Claude Code
- A Aphelion backend deployment (or use the public one)

## Step 1: Create a GitHub OAuth App

1. Go to https://github.com/settings/apps
2. Click "New GitHub App"
3. Fill in:
   - **App name**: `aphelion-mcp` (or your name)
   - **Homepage URL**: `https://post-pilot.example.com`
   - **Authorization callback URL**: `https://your-worker.workers.dev/callback`
4. Under "Permissions":
   - Leave defaults (no special permissions needed)
5. Click "Create GitHub App"
6. Copy:
   - Client ID
   - Client Secret (generate one if needed)

## Step 2: Set Up Cloudflare Worker

### 2a. Clone the repository
```bash
git clone https://github.com/saksham-gagneja-indxx/aphelion.git
cd aphelion/mcp-server
```

### 2b. Install dependencies
```bash
npm install
```

### 2c. Create `.env.production`
```bash
cp .env.example .env.production
```

Edit `.env.production` with:
```
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
BACKEND_API_URL=https://social-media-manager-api-wk5g.onrender.com
BACKEND_API_KEY=your_api_key
BACKEND_USER_ID=0
ALLOWED_GITHUB_USERNAMES=your_github_username
```

### 2d. Deploy to Cloudflare
```bash
npx wrangler publish
```

Copy your Worker URL (e.g., `https://post-pilot-abc123.workers.dev`)

## Step 3: Update GitHub OAuth Callback

1. Go to your GitHub App settings (https://github.com/settings/apps)
2. Update "Authorization callback URL":
   - Old: `https://your-worker.workers.dev/callback`
   - New: `https://your-actual-worker-url.workers.dev/callback`
3. Save

## Step 4: Install in Claude

### Claude Desktop
1. Open Claude Desktop settings
2. Under "MCP Servers", add:
   ```json
   {
     "name": "post-pilot",
     "url": "https://your-worker-url.workers.dev/mcp"
   }
   ```
3. Restart Claude Desktop

### Claude Code / claude.ai
1. Go to your deployment URL
2. Click "Add to Claude Code" or paste the URL in the MCP server config

### Browser / Cowork
1. Navigate to your worker URL
2. Follow the OAuth flow

## Step 5: Authenticate

When you first use a Aphelion tool in Claude:
1. Claude will prompt you to authorize
2. Click the GitHub OAuth link
3. Authorize access to your GitHub account
4. You'll be added to the allowlist
5. Return to Claude—you're ready to use Aphelion!

---

## Using Google Drive for Video Upload

Aphelion can upload videos directly from your Google Drive:

### 1. Get a Shareable Link
- Right-click video in Drive → Share
- Set to "Anyone with the link can view"
- Copy the link

### 2. Convert to Direct Download
From: `https://drive.google.com/file/d/ABC123XYZ/view`  
To: `https://drive.google.com/uc?export=download&id=ABC123XYZ`

### 3. Tell Claude
```
Upload this video from Google Drive:
https://drive.google.com/uc?export=download&id=ABC123XYZ
```

Claude will fetch it server-side and upload to Aphelion automatically.

---

## Next Steps

- **Try it out**: Tell Claude "List my reels" or "Upload a video from Google Drive"
- **Read the tools**: Check [README.md](README.md) for full tool reference
- **Deploy updates**: `npm run build && npx wrangler publish`

---

## Troubleshooting

### "Not authorized" error
- Check your GitHub username is in `ALLOWED_GITHUB_USERNAMES`
- Restart Claude Desktop after updating settings

### Worker not responding
- Check Cloudflare dashboard for deployment status
- Run `npx wrangler tail` to see logs

### Google Drive upload fails
- Verify link is public (test in browser)
- Use the `export=download` format
- Check video codec is H.264 (standard format)

### LinkedIn publish fails
- Ensure your backend has valid LinkedIn OAuth credentials
- Check that the account you're posting as is authenticated
- Verify the video uploaded successfully first

---

**Questions?** Check the [Technical Setup Guide](SETUP.md) for deeper details.

Generated: 2026-08-19
