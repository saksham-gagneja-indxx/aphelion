# Post Pilot MCP Setup Guide

Get the Claude connector working in **15 minutes**.

## What you'll need

- A **Cloudflare account** (free)
- A **GitHub account**
- Your Render backend URL (or local API running)
- Your LinkedIn-connected **user ID** from the app

## Step 1: Sign in to Cloudflare

```bash
cd mcp-server
npx wrangler login
```

Approve in your browser. Done.

## Step 2: Create KV namespace

```bash
npx wrangler kv namespace create OAUTH_KV
```

Copy the returned **id** and update `wrangler.jsonc` line 41:

```jsonc
"id": "paste-id-here"
```

## Step 3: Create GitHub OAuth App

1. Go to [github.com/settings/developers](https://github.com/settings/developers)
2. Click "New OAuth App"
3. Fill in:
   - **Application name**: `Post Pilot MCP`
   - **Homepage URL**: `https://post-pilot.<your-subdomain>.workers.dev`
   - **Authorization callback URL**: `https://post-pilot.<your-subdomain>.workers.dev/callback`
4. Click "Register application"
5. Copy the **Client ID** and click "Generate a new client secret"
6. Copy the **Client Secret**

> **Find your subdomain**: After step 1 (`wrangler login`), run `npx wrangler whoami` — it shows your account.

## Step 4: Set secrets

Replace values in brackets with yours:

```bash
npx wrangler secret put GITHUB_CLIENT_ID
# Paste: [your-client-id]

npx wrangler secret put GITHUB_CLIENT_SECRET
# Paste: [your-client-secret]

npx wrangler secret put COOKIE_ENCRYPTION_KEY
# Paste: openssl rand -hex 32 (or any 64-char hex string)

npx wrangler secret put BACKEND_API_URL
# Paste: https://your-render-domain.onrender.com (or http://localhost:5000)

npx wrangler secret put BACKEND_API_KEY
# Paste: your API_ACCESS_KEY from the backend

npx wrangler secret put BACKEND_USER_ID
# Paste: your numeric user id (check /admin panel)

npx wrangler secret put ALLOWED_GITHUB_USERNAMES
# Paste: your-github-username (comma-separated if multiple)
```

## Step 5: Deploy

```bash
npx wrangler deploy
```

The output shows your Worker URL:
```
https://post-pilot.<your-subdomain>.workers.dev
```

## Step 6: Register in Claude

**Option A: Claude Code CLI**
```bash
claude mcp add post-pilot -- sse https://post-pilot.<your-subdomain>.workers.dev/mcp
```

**Option B: Claude Desktop / Cowork Settings**
Add as a connector:
```
https://post-pilot.<your-subdomain>.workers.dev/mcp
```

## Step 7: Test

Ask Claude:
```
List my reels
```

On first use, you'll be prompted to sign in with GitHub. Done!

## Troubleshooting

| Problem | Fix |
|---|---|
| "Worker not found" after deploy | Wait 30 seconds, then retry. Cloudflare propagates slowly. |
| "Unauthorized" from the API | Check `BACKEND_API_KEY` matches your backend's `API_ACCESS_KEY`. |
| No tools appear in Claude | Did you sign in with GitHub? Check if your username is in `ALLOWED_GITHUB_USERNAMES`. |
| "User not found" error | Verify `BACKEND_USER_ID` exists and is active in your app's `/admin` panel. |
| OAuth loop / keeps asking to sign in | Clear your browser's cookies for `workers.dev`, then retry. |

## What each secret does

| Secret | Purpose |
|---|---|
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | OAuth with GitHub — controls who can access the tools |
| `COOKIE_ENCRYPTION_KEY` | Secures the OAuth session state |
| `BACKEND_API_URL` | Where your Post Pilot backend is running |
| `BACKEND_API_KEY` | Bearer token for the backend API |
| `BACKEND_USER_ID` | Which account the tools act as (fixed, not per-user) |
| `ALLOWED_GITHUB_USERNAMES` | GitHub usernames allowed to use the tools (fail-closed if empty) |

## Done?

Your Claude connector is live. Try:
- `List my reels`
- `Draft a post about [topic]`
- `Schedule my reel for tomorrow at 9am`

Enjoy!
