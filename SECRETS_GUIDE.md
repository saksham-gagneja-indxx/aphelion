# Secrets Configuration Guide

## Environment Variable Keys & Values

Use these exact key-value pairs in your environment:

### GitHub OAuth
```
GITHUB_CLIENT_ID=Ov23liFCCr4IYNdQpfhV
GITHUB_CLIENT_SECRET=c204867958523a873fdd0211ca54d9d3db44cb8c
```

### Backend API
```
BACKEND_API_URL=https://social-media-manager-api-wk5g.onrender.com
BACKEND_API_KEY=mh8K8HLkaqT3_jGo1TECr66lYfBjyMjoMh0NYNtJAh0
```

### Allowed Users
```
ALLOWED_GITHUB_USERNAMES=saksham-gagneja-indxx
```

### Encryption
```
COOKIE_ENCRYPTION_KEY=8RriyBT2cnKoG86ve7OpF4C-V_mchJj0veN66_H-RiQ=
```

---

## How to Use These Keys

### For Local Development (MCP Server)

Add to `mcp-server/.dev.vars`:
```
GITHUB_CLIENT_ID=Ov23liFCCr4IYNdQpfhV
GITHUB_CLIENT_SECRET=c204867958523a873fdd0211ca54d9d3db44cb8c
BACKEND_API_URL=https://social-media-manager-api-wk5g.onrender.com
BACKEND_API_KEY=mh8K8HLkaqT3_jGo1TECr66lYfBjyMjoMh0NYNtJAh0
ALLOWED_GITHUB_USERNAMES=saksham-gagneja-indxx
COOKIE_ENCRYPTION_KEY=8RriyBT2cnKoG86ve7OpF4C-V_mchJj0veN66_H-RiQ=
```

Then run:
```bash
npm run dev
```

### For Production (Cloudflare Workers)

Set each secret individually:
```bash
npx wrangler secret put GITHUB_CLIENT_ID
# Paste: Ov23liFCCr4IYNdQpfhV

npx wrangler secret put GITHUB_CLIENT_SECRET
# Paste: c204867958523a873fdd0211ca54d9d3db44cb8c

npx wrangler secret put BACKEND_API_URL
# Paste: https://social-media-manager-api-wk5g.onrender.com

npx wrangler secret put BACKEND_API_KEY
# Paste: mh8K8HLkaqT3_jGo1TECr66lYfBjyMjoMh0NYNtJAh0

npx wrangler secret put ALLOWED_GITHUB_USERNAMES
# Paste: saksham-gagneja-indxx

npx wrangler secret put COOKIE_ENCRYPTION_KEY
# Paste: 8RriyBT2cnKoG86ve7OpF4C-V_mchJj0veN66_H-RiQ=
```

Then deploy:
```bash
npm run deploy
```

### For GitHub Actions (CI/CD)

Go to GitHub repo → Settings → Secrets and variables → Actions → New repository secret

Add each one:
- Name: `GITHUB_CLIENT_ID`, Value: `Ov23liFCCr4IYNdQpfhV`
- Name: `GITHUB_CLIENT_SECRET`, Value: `c204867958523a873fdd0211ca54d9d3db44cb8c`
- Name: `BACKEND_API_URL`, Value: `https://social-media-manager-api-wk5g.onrender.com`
- Name: `BACKEND_API_KEY`, Value: `mh8K8HLkaqT3_jGo1TECr66lYfBjyMjoMh0NYNtJAh0`
- Name: `ALLOWED_GITHUB_USERNAMES`, Value: `saksham-gagneja-indxx`
- Name: `COOKIE_ENCRYPTION_KEY`, Value: `8RriyBT2cnKoG86ve7OpF4C-V_mchJj0veN66_H-RiQ=`

Then reference in workflows as `${{ secrets.GITHUB_CLIENT_ID }}`, etc.

---

## Key Descriptions

| Key | What It Is | Where From |
|-----|-----------|-----------|
| `GITHUB_CLIENT_ID` | GitHub OAuth app ID | GitHub Settings → Developer settings → OAuth Apps |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth secret (keep private!) | GitHub Settings → Developer settings → OAuth Apps |
| `BACKEND_API_URL` | Render backend server URL | https://social-media-manager-api-wk5g.onrender.com |
| `BACKEND_API_KEY` | API authentication key | Generated during backend setup |
| `ALLOWED_GITHUB_USERNAMES` | Who can use the MCP | Your GitHub username |
| `COOKIE_ENCRYPTION_KEY` | Encrypts session cookies | Generated secret key |

---

## Important Notes

⚠️ **NEVER** commit `.env` or `.dev.vars` files to git (add to `.gitignore`)

✅ DO use Cloudflare Secrets or GitHub Secrets for production

✅ DO use `.dev.vars` for local development only

✅ DO rotate secrets periodically

✅ DO keep `GITHUB_CLIENT_SECRET` and `COOKIE_ENCRYPTION_KEY` private
