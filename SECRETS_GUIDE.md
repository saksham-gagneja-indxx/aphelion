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

### Encryption & Session Secrets
```
COOKIE_ENCRYPTION_KEY=8RriyBT2cnKoG86ve7OpF4C-V_mchJj0veN66_H-RiQ=
SECRET_KEY=oZdGzUk3OwPujfQ6_nYgswHIrjgFrCgCFxGrqK7PksQ
API_ACCESS_KEY=mh8K8HLkaqT3_jGo1TECr66lYfBjyMjoMh0NYNtJAh0
ENCRYPTION_KEY=8RriyBT2cnKoG86ve7OpF4C-V_mchJj0veN66_H-RiQ=
```

### LinkedIn OAuth
```
LINKEDIN_CLIENT_ID=86hec0jiuraefg
LINKEDIN_CLIENT_SECRET=WPL_AP1.y6JWSy0jUTHCn6D9.GtvN7w==
```

### Database (Supabase)
```
DATABASE_URL=postgresql://postgres.vbh1jwv4UgNCDaQPNwtlIw:pscale_pw_vbh1jwv4UgNCDaQPNwtlIw_Y-5e26_H@aws-0-us-east-1.pooling.supabase.com:6543/postgres
```

### Redis Cache (Upstash)
```
UPSTASH_REDIS_REST_URL=https://trusty-bengal-98742.upstash.io
UPSTASH_REDIS_REST_TOKEN=gQAAAAAAAYG2AAIgcDE3NGIxOTE3YzdjNDk0NDYzOGRmZXk0NjFhODhiMTYzOQ
```

### Authentication (Clerk)
```
CLERK_SECRET_KEY=sk_test_NuKFI59kHwWnsOFKAqZTAfqTHnrv1zXZ2oBCtnvzFG
```

---

## How to Use These Keys

### For Local Development (MCP Server)

Add to `mcp-server/.dev.vars`:
```
# GitHub OAuth
GITHUB_CLIENT_ID=Ov23liFCCr4IYNdQpfhV
GITHUB_CLIENT_SECRET=c204867958523a873fdd0211ca54d9d3db44cb8c

# Backend API
BACKEND_API_URL=https://social-media-manager-api-wk5g.onrender.com
BACKEND_API_KEY=mh8K8HLkaqT3_jGo1TECr66lYfBjyMjoMh0NYNtJAh0

# Access Control
ALLOWED_GITHUB_USERNAMES=saksham-gagneja-indxx

# Encryption & Secrets
COOKIE_ENCRYPTION_KEY=8RriyBT2cnKoG86ve7OpF4C-V_mchJj0veN66_H-RiQ=
SECRET_KEY=oZdGzUk3OwPujfQ6_nYgswHIrjgFrCgCFxGrqK7PksQ
API_ACCESS_KEY=mh8K8HLkaqT3_jGo1TECr66lYfBjyMjoMh0NYNtJAh0
ENCRYPTION_KEY=8RriyBT2cnKoG86ve7OpF4C-V_mchJj0veN66_H-RiQ=

# LinkedIn OAuth
LINKEDIN_CLIENT_ID=86hec0jiuraefg
LINKEDIN_CLIENT_SECRET=WPL_AP1.y6JWSy0jUTHCn6D9.GtvN7w==

# Database (Supabase)
DATABASE_URL=postgresql://postgres.vbh1jwv4UgNCDaQPNwtlIw:pscale_pw_vbh1jwv4UgNCDaQPNwtlIw_Y-5e26_H@aws-0-us-east-1.pooling.supabase.com:6543/postgres

# Redis Cache (Upstash)
UPSTASH_REDIS_REST_URL=https://trusty-bengal-98742.upstash.io
UPSTASH_REDIS_REST_TOKEN=gQAAAAAAAYG2AAIgcDE3NGIxOTE3YzdjNDk0NDYzOGRmZXk0NjFhODhiMTYzOQ

# Authentication (Clerk)
CLERK_SECRET_KEY=sk_test_NuKFI59kHwWnsOFKAqZTAfqTHnrv1zXZ2oBCtnvzFG
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

npx wrangler secret put SECRET_KEY
# Paste: oZdGzUk3OwPujfQ6_nYgswHIrjgFrCgCFxGrqK7PksQ

npx wrangler secret put API_ACCESS_KEY
# Paste: mh8K8HLkaqT3_jGo1TECr66lYfBjyMjoMh0NYNtJAh0

npx wrangler secret put ENCRYPTION_KEY
# Paste: 8RriyBT2cnKoG86ve7OpF4C-V_mchJj0veN66_H-RiQ=

npx wrangler secret put LINKEDIN_CLIENT_ID
# Paste: 86hec0jiuraefg

npx wrangler secret put LINKEDIN_CLIENT_SECRET
# Paste: WPL_AP1.y6JWSy0jUTHCn6D9.GtvN7w==

npx wrangler secret put DATABASE_URL
# Paste: postgresql://postgres.vbh1jwv4UgNCDaQPNwtlIw:pscale_pw_vbh1jwv4UgNCDaQPNwtlIw_Y-5e26_H@aws-0-us-east-1.pooling.supabase.com:6543/postgres

npx wrangler secret put UPSTASH_REDIS_REST_URL
# Paste: https://trusty-bengal-98742.upstash.io

npx wrangler secret put UPSTASH_REDIS_REST_TOKEN
# Paste: gQAAAAAAAYG2AAIgcDE3NGIxOTE3YzdjNDk0NDYzOGRmZXk0NjFhODhiMTYzOQ

npx wrangler secret put CLERK_SECRET_KEY
# Paste: sk_test_NuKFI59kHwWnsOFKAqZTAfqTHnrv1zXZ2oBCtnvzFG
```

Then deploy:
```bash
npm run deploy
```

### For GitHub Actions (CI/CD)

Go to GitHub repo → Settings → Secrets and variables → Actions → New repository secret

Add each one:

**GitHub OAuth:**
- Name: `GITHUB_CLIENT_ID`, Value: `Ov23liFCCr4IYNdQpfhV`
- Name: `GITHUB_CLIENT_SECRET`, Value: `c204867958523a873fdd0211ca54d9d3db44cb8c`

**Backend API:**
- Name: `BACKEND_API_URL`, Value: `https://social-media-manager-api-wk5g.onrender.com`
- Name: `BACKEND_API_KEY`, Value: `mh8K8HLkaqT3_jGo1TECr66lYfBjyMjoMh0NYNtJAh0`

**Access Control:**
- Name: `ALLOWED_GITHUB_USERNAMES`, Value: `saksham-gagneja-indxx`

**Encryption & Secrets:**
- Name: `COOKIE_ENCRYPTION_KEY`, Value: `8RriyBT2cnKoG86ve7OpF4C-V_mchJj0veN66_H-RiQ=`
- Name: `SECRET_KEY`, Value: `oZdGzUk3OwPujfQ6_nYgswHIrjgFrCgCFxGrqK7PksQ`
- Name: `API_ACCESS_KEY`, Value: `mh8K8HLkaqT3_jGo1TECr66lYfBjyMjoMh0NYNtJAh0`
- Name: `ENCRYPTION_KEY`, Value: `8RriyBT2cnKoG86ve7OpF4C-V_mchJj0veN66_H-RiQ=`

**LinkedIn OAuth:**
- Name: `LINKEDIN_CLIENT_ID`, Value: `86hec0jiuraefg`
- Name: `LINKEDIN_CLIENT_SECRET`, Value: `WPL_AP1.y6JWSy0jUTHCn6D9.GtvN7w==`

**Database:**
- Name: `DATABASE_URL`, Value: `postgresql://postgres.vbh1jwv4UgNCDaQPNwtlIw:pscale_pw_vbh1jwv4UgNCDaQPNwtlIw_Y-5e26_H@aws-0-us-east-1.pooling.supabase.com:6543/postgres`

**Redis Cache:**
- Name: `UPSTASH_REDIS_REST_URL`, Value: `https://trusty-bengal-98742.upstash.io`
- Name: `UPSTASH_REDIS_REST_TOKEN`, Value: `gQAAAAAAAYG2AAIgcDE3NGIxOTE3YzdjNDk0NDYzOGRmZXk0NjFhODhiMTYzOQ`

**Authentication:**
- Name: `CLERK_SECRET_KEY`, Value: `sk_test_NuKFI59kHwWnsOFKAqZTAfqTHnrv1zXZ2oBCtnvzFG`

Then reference in workflows as `${{ secrets.GITHUB_CLIENT_ID }}`, etc.

---

## Key Descriptions

| Key | What It Is | Where From |
|-----|-----------|-----------|
| `GITHUB_CLIENT_ID` | GitHub OAuth app ID | GitHub Settings → Developer settings → OAuth Apps |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth secret | GitHub Settings → Developer settings → OAuth Apps |
| `BACKEND_API_URL` | Render backend server URL | https://social-media-manager-api-wk5g.onrender.com |
| `BACKEND_API_KEY` | API authentication key | Generated during backend setup |
| `ALLOWED_GITHUB_USERNAMES` | Who can use the MCP | Your GitHub username |
| `COOKIE_ENCRYPTION_KEY` | Encrypts session cookies | Generated secret key |
| `SECRET_KEY` | Flask session secret | Generated secret key |
| `API_ACCESS_KEY` | API endpoint authentication | Generated secret key |
| `ENCRYPTION_KEY` | Credential encryption (Fernet) | Generated secret key |
| `LINKEDIN_CLIENT_ID` | LinkedIn OAuth app ID | LinkedIn Developers → App Settings |
| `LINKEDIN_CLIENT_SECRET` | LinkedIn OAuth secret | LinkedIn Developers → App Settings |
| `DATABASE_URL` | PostgreSQL connection string | Supabase Dashboard → Connection Strings |
| `UPSTASH_REDIS_REST_URL` | Upstash Redis endpoint | Upstash Console → Database Details |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash REST API token | Upstash Console → Database Details |
| `CLERK_SECRET_KEY` | Clerk authentication secret | Clerk Dashboard → API Keys |

---

## Important Notes

⚠️ **NEVER** commit `.env` or `.dev.vars` files to git (add to `.gitignore`)

✅ DO use Cloudflare Secrets or GitHub Secrets for production

✅ DO use `.dev.vars` for local development only

✅ DO rotate secrets periodically

✅ DO keep these private (never share):
  - `GITHUB_CLIENT_SECRET`
  - `GITHUB_CLIENT_ID` (if app is not public)
  - `COOKIE_ENCRYPTION_KEY`
  - `SECRET_KEY`
  - `API_ACCESS_KEY`
  - `ENCRYPTION_KEY`
  - `LINKEDIN_CLIENT_SECRET`
  - `DATABASE_URL` (contains credentials)
  - `UPSTASH_REDIS_REST_TOKEN`
  - `CLERK_SECRET_KEY`
