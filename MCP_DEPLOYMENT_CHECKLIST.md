# MCP Deployment Checklist

## ✅ Code Status
- [x] MCP server code ready in `./mcp-server/`
- [x] All 5 tools implemented
- [x] Security & OAuth configured
- [x] Backend client setup complete

## 🔐 Credentials You Need to Provide

Before we deploy, please gather these:

### 1. Backend Information
From your `.env` file or Render dashboard:
- [ ] `BACKEND_API_URL` = your Render backend URL (e.g., `https://social-media-manager-api-wk5g.onrender.com`)
- [ ] `BACKEND_API_KEY` = your `API_ACCESS_KEY` from backend environment
- [ ] `BACKEND_USER_ID` = your numeric user ID (check `/admin` panel in the app)

### 2. GitHub OAuth Credentials
Create new OAuth app at: https://github.com/settings/developers
- [ ] `GITHUB_CLIENT_ID` = (from OAuth app)
- [ ] `GITHUB_CLIENT_SECRET` = (from OAuth app)
- [ ] Your GitHub username for `ALLOWED_GITHUB_USERNAMES`

### 3. Cloudflare Account
- [ ] Cloudflare account (free) - https://dash.cloudflare.com
- [ ] Logged in and ready

### 4. Encryption Key
Generate a 64-character hex string (run this once):
```bash
openssl rand -hex 32
```
- [ ] `COOKIE_ENCRYPTION_KEY` = (output from above command)

---

## 📋 Deployment Steps

Once you provide all credentials above, I will:

1. ✅ Login to Cloudflare (you click "Approve" in browser)
2. ✅ Create KV namespace for OAuth
3. ✅ Set all 7 secrets
4. ✅ Deploy to Cloudflare Workers
5. ✅ Register in Claude Desktop
6. ✅ Test everything

---

## What to provide

Reply with:
```
BACKEND_API_URL=https://...
BACKEND_API_KEY=...
BACKEND_USER_ID=...
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
GITHUB_USERNAME=...
COOKIE_ENCRYPTION_KEY=...
```

Then I'll deploy everything!
