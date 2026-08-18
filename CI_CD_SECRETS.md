# GitHub Actions CI/CD - Secrets Setup

To enable automated deployments, add these secrets to your GitHub repository.

Go to: **Settings → Secrets and variables → Actions**

---

## 🔧 MCP Server Deployment (deploy-mcp.yml)

### Required Secrets

**`CLOUDFLARE_API_TOKEN`**
1. Go to: https://dash.cloudflare.com/profile/api-tokens
2. Click "Create Token"
3. Use template: "Edit Cloudflare Workers"
4. Copy the token
5. Add to GitHub as `CLOUDFLARE_API_TOKEN`

**`CLOUDFLARE_ACCOUNT_ID`**
1. Go to: https://dash.cloudflare.com
2. Copy Account ID from sidebar
3. Add to GitHub as `CLOUDFLARE_ACCOUNT_ID`

### Optional Secret

**`SLACK_WEBHOOK_URL`** (for notifications)
1. Create Slack webhook: https://api.slack.com/messaging/webhooks
2. Copy webhook URL
3. Add to GitHub as `SLACK_WEBHOOK_URL`

---

## 🎨 Frontend Deployment (deploy-frontend.yml)

### Required Secrets

**`VERCEL_TOKEN`**
1. Go to: https://vercel.com/account/tokens
2. Create new token (full scope)
3. Copy token
4. Add to GitHub as `VERCEL_TOKEN`

**`VERCEL_ORG_ID`**
1. Go to: https://vercel.com/account
2. Copy Organization ID from URL or settings
3. Add to GitHub as `VERCEL_ORG_ID`

**`VERCEL_PROJECT_ID`**
1. Go to your Vercel project settings
2. Copy Project ID
3. Add to GitHub as `VERCEL_PROJECT_ID`

**`VITE_CLERK_PUBLISHABLE_KEY`**
1. Copy from your backend `.env` file
2. Add to GitHub as `VITE_CLERK_PUBLISHABLE_KEY`

---

## 🐍 Backend Deployment (deploy-backend.yml)

### Required Secrets

**`RENDER_SERVICE_ID`**
1. Go to: https://dashboard.render.com/services
2. Select your backend service
3. Go to Settings → Copy Service ID from URL
4. Example URL: `https://dashboard.render.com/services/srv-xyz123`
5. The ID is `xyz123`
6. Add to GitHub as `RENDER_SERVICE_ID`

**`RENDER_API_KEY`**
1. Go to: https://dashboard.render.com/account/api-keys
2. Create new API key
3. Copy key
4. Add to GitHub as `RENDER_API_KEY`

---

## 📋 Quick Checklist

Add these to GitHub Secrets:

**MCP (Cloudflare):**
- [ ] `CLOUDFLARE_API_TOKEN`
- [ ] `CLOUDFLARE_ACCOUNT_ID`

**Frontend (Vercel):**
- [ ] `VERCEL_TOKEN`
- [ ] `VERCEL_ORG_ID`
- [ ] `VERCEL_PROJECT_ID`
- [ ] `VITE_CLERK_PUBLISHABLE_KEY`

**Backend (Render):**
- [ ] `RENDER_SERVICE_ID`
- [ ] `RENDER_API_KEY`

**Optional:**
- [ ] `SLACK_WEBHOOK_URL` (for Slack notifications)

---

## 🚀 How It Works

Once secrets are added:

### MCP Server
- **Trigger:** Push to `feat/mcp-deployment` or `main` with changes in `mcp-server/`
- **Action:** 
  1. Install dependencies
  2. Type check
  3. Deploy to Cloudflare Workers
  4. Auto-restart on new commits

### Frontend
- **Trigger:** Push to `main` with changes in `frontend/`
- **Action:**
  1. Install dependencies
  2. Type check
  3. Build Vite app
  4. Deploy to Vercel
  5. Vercel auto-triggers preview on PRs

### Backend
- **Trigger:** Push to `main` with changes in `backend/`
- **Action:**
  1. Run Python tests & linting
  2. Trigger Render deployment
  3. Auto-redeploy Python service

---

## 🔒 Security Notes

- Never commit secrets to GitHub
- Rotate API tokens periodically
- Use minimal required scopes
- Monitor GitHub Actions logs for leaks
- Revoke tokens if compromised

---

## 🐛 Troubleshooting

**"Deployment failed with authentication error"**
→ Check secret value is correct and not expired

**"CLOUDFLARE_ACCOUNT_ID not found"**
→ Make sure you copied the account ID, not project ID

**"Vercel deployment rejected"**
→ Check `VITE_CLERK_PUBLISHABLE_KEY` matches Vercel environment

**"Render deployment not triggering"**
→ Verify `RENDER_SERVICE_ID` and `RENDER_API_KEY` are correct

---

## 📚 More Info

- [GitHub Secrets Docs](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions)
- [Cloudflare API Tokens](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/)
- [Vercel API Tokens](https://vercel.com/docs/rest-api#authentication)
- [Render Deployment API](https://render.com/docs/deploy-api)

---

## Questions?

Contact: sgagneja@indxx.com
