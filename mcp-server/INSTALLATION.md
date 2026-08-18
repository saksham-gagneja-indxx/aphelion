# Post Pilot MCP - Installation Guide

**For end users:** Follow these steps to connect the Post Pilot MCP to your Claude.

## Prerequisites

You'll need:
- ✅ A **Cloudflare account** (free) — https://dash.cloudflare.com
- ✅ A **GitHub account** with a username
- ✅ A running **Post Pilot backend** with credentials
- ✅ **Your Post Pilot user ID** (from the admin panel)

## Installation (5 minutes)

### 1. Fork or Clone this Repo

```bash
git clone https://github.com/saksham-gagneja-indxx/Social-Media-Manager.git
cd Social-Media-Manager/mcp-server
```

### 2. Install Dependencies

```bash
npm install
```

### 3. Login to Cloudflare

```bash
npx wrangler login
```

Browser popup → click "Authorize" → done.

### 4. Create KV Namespace

```bash
npx wrangler kv namespace create oauth_states
```

**Copy the `id`** from the output. Update `wrangler.jsonc` line 40:

```jsonc
{
  "kv_namespaces": [
    {
      "binding": "OAUTH_KV",
      "id": "paste-your-id-here"  // ← Your ID from step 4
    }
  ]
}
```

### 5. Create GitHub OAuth App

Go to: https://github.com/settings/developers

1. Click **"New OAuth App"**
2. Fill in:
   - **Application name:** `Post Pilot MCP`
   - **Homepage URL:** `https://post-pilot.your-workers-subdomain.workers.dev`
   - **Authorization callback URL:** `https://post-pilot.your-workers-subdomain.workers.dev/callback`
3. Click **"Register application"**
4. Copy **Client ID**
5. Click **"Generate a new client secret"**
6. Copy **Client Secret**

> Don't know your Workers subdomain? Run `npx wrangler whoami` — it shows your account info.

### 6. Set 7 Secrets on Cloudflare

Run these commands one by one. When prompted, paste the values:

```bash
npx wrangler secret put GITHUB_CLIENT_ID
# Paste: <your-client-id-from-step-5>

npx wrangler secret put GITHUB_CLIENT_SECRET
# Paste: <your-client-secret-from-step-5>

npx wrangler secret put BACKEND_API_URL
# Paste: https://your-backend.onrender.com (or http://localhost:5000)

npx wrangler secret put BACKEND_API_KEY
# Paste: <your-api-key-from-post-pilot-backend>

npx wrangler secret put BACKEND_USER_ID
# Paste: <your-numeric-user-id>

npx wrangler secret put ALLOWED_GITHUB_USERNAMES
# Paste: <your-github-username>

npx wrangler secret put COOKIE_ENCRYPTION_KEY
# Paste: <run: openssl rand -hex 32>
```

### 7. Deploy to Cloudflare Workers

```bash
npx wrangler deploy
```

Output shows:
```
Deployed post-pilot triggers
  https://post-pilot.<your-subdomain>.workers.dev
```

**Copy this URL** — you'll need it next.

### 8. Update GitHub OAuth Redirect URI

Go back to: https://github.com/settings/developers/applications/your-app-id

Update **Authorization callback URL** to your deployed URL:
```
https://post-pilot.<your-subdomain>.workers.dev/callback
```

Click **"Update application"**.

### 9. Add to Claude Desktop

**On Windows/Mac:**
- Create file `~/.claude/mcp_config.json`
- Add:

```json
{
  "mcpServers": {
    "post-pilot": {
      "url": "https://post-pilot.<your-subdomain>.workers.dev",
      "auth": "oauth",
      "type": "http"
    }
  }
}
```

Replace `<your-subdomain>` with your actual Cloudflare Workers subdomain.

**On Claude.ai or Claude Code CLI:**
- Settings → MCP Servers
- Add: `https://post-pilot.<your-subdomain>.workers.dev`
- Auth type: OAuth

### 10. Restart Claude & Test

1. **Close Claude completely** (all windows)
2. **Reopen Claude Desktop / Claude.ai**
3. **Ask Claude:** `List my reels`
4. **You'll see:** GitHub login prompt → Claude connects → Lists your reels ✨

---

## Troubleshooting

| Issue | Solution |
|---|---|
| "Worker not found" | Wait 30-60 seconds. Cloudflare is slow. Try again. |
| "Unauthorized" after deploy | Check `BACKEND_API_KEY` matches your backend's actual key in settings. |
| No tools show up in Claude | Did you sign in with GitHub? Your username must be in `ALLOWED_GITHUB_USERNAMES`. |
| "User not found" error | Go to Post Pilot `/admin` → find your numeric user ID → update `BACKEND_USER_ID`. |
| Stuck on "Sign in with GitHub" | Clear browser cookies for `*.workers.dev`, then retry. |
| "Secret not set" error | Re-run `npx wrangler secret put SECRETNAME` for missing secret. |

---

## What Each Secret Does

| Secret | What It Controls |
|---|---|
| `GITHUB_CLIENT_ID` / `SECRET` | **Authentication** — who can access the tools (GitHub OAuth gating) |
| `ALLOWED_GITHUB_USERNAMES` | **Authorization** — which GitHub users get access (comma-separated) |
| `BACKEND_API_URL` | **Backend location** — where your Post Pilot API runs |
| `BACKEND_API_KEY` | **Backend auth** — the API key (get from Post Pilot backend settings) |
| `BACKEND_USER_ID` | **Which account** — all tools act as this user ID |
| `COOKIE_ENCRYPTION_KEY` | **Session security** — encrypts OAuth state between GitHub and Claude |

---

## Local Development (Optional)

Want to test locally before deploying?

```bash
# Create .dev.vars with all 7 secrets (copy from wrangler secret list)
npx wrangler dev

# In another terminal:
npx @modelcontextprotocol/inspector@latest
# Enter: http://localhost:8788
```

---

## Next Steps

Once installed:
- ✅ `List my reels` — see your uploaded reels
- ✅ `Draft a post about [topic]` — AI-powered caption drafting
- ✅ `Suggest captions for [brief]` — three caption options
- ✅ `Schedule my reel for tomorrow at 9am` — auto-posting
- ✅ `Publish my reel now` — immediate LinkedIn publish

---

## Questions?

- 📖 **Technical help:** Check [SETUP.md](SETUP.md) for more details
- 🐛 **Report issues:** https://github.com/saksham-gagneja-indxx/Social-Media-Manager/issues
- 💬 **Feedback:** sgagneja@indxx.com

Happy posting! 🚀
