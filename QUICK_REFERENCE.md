# Quick Reference - Free Hosting

## **One-Time Setup**

```bash
# 1. Generate secrets
python generate_secrets.py
# Save all 3 outputs safely

# 2. Create accounts
# - Supabase: https://supabase.com
# - Upstash: https://upstash.com
# - Render: https://render.com
# Get keys from:
# - Clerk: https://clerk.com
# - LinkedIn: https://linkedin.com/developers
# - NVIDIA: https://build.nvidia.com/nim
```

## **Set Environment Variables in Render**

```
FLASK_ENV=production
SECRET_KEY=<from generate_secrets.py>
API_ACCESS_KEY=<from generate_secrets.py>
ENCRYPTION_KEY=<from generate_secrets.py>
DATABASE_URL=<from Supabase>
REDIS_URL=<from Upstash>
CLERK_SECRET_KEY=<from Clerk>
LINKEDIN_CLIENT_ID=<from LinkedIn>
LINKEDIN_CLIENT_SECRET=<from LinkedIn>
NVIDIA_API_KEY=<from NVIDIA>
CORS_ORIGINS=https://postpilot.vercel.app
SCHEDULER_ENABLED=true
```

## **Test After Deployment**

```bash
# Health check
curl https://postpilot-backend.onrender.com/health

# API test (replace with your API key)
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://postpilot-backend.onrender.com/api/status

# Frontend
open https://postpilot.vercel.app
```

## **Monitoring**

```bash
# Render logs
# Dashboard → postpilot-backend → Logs (watch live)

# Database health
# Supabase → SQL Editor → SELECT 1
# Should return success

# Cache health  
# Upstash → Redis Console → PING
# Should return "PONG"
```

## **Keep Backend Alive**

Your cron job must ping this every 10 minutes:
```
https://postpilot-backend.onrender.com/health
```

Verify it's working:
```bash
# Check if backend is responding
curl https://postpilot-backend.onrender.com/health

# If error, cron job isn't running
# Check cron logs or set up UptimeRobot backup
```

## **Update Frontend API URL**

After backend is deployed:
```bash
# In Vercel dashboard:
# Settings → Environment Variables
# Update VITE_API_URL = https://your-backend.onrender.com

# Or update locally and push:
echo "VITE_API_URL=https://your-backend.onrender.com" >> frontend/.env.production
git add frontend/.env.production
git commit -m "chore: update backend URL"
git push origin main
# Vercel auto-redeploys
```

## **Redeploy Backend**

```bash
# Push code changes to GitHub main branch
git push origin main
# Render auto-rebuilds and deploys

# Or manually trigger in Render:
# Dashboard → postpilot-backend → Manual Deploy → Deploy latest commit
```

## **View Logs**

```bash
# Render backend logs
# Go to: dashboard.render.com → postpilot-backend → Logs

# Vercel frontend logs
# Go to: vercel.com/dashboard → postpilot → Deployments → click deployment

# Supabase database logs
# Go to: app.supabase.com → postpilot → Logs → Database

# Upstash cache logs
# Go to: console.upstash.com → Redis → postpilot-cache → Logs
```

## **Troubleshooting**

```bash
# Backend won't start
1. Check Render logs for errors
2. Verify all environment variables are set
3. Check requirements.txt exists
4. Verify Python version (3.12+)

# Database connection fails
1. Test DATABASE_URL locally:
   psql $DATABASE_URL
2. Check Supabase is running
3. Verify IP whitelist (Supabase → Settings → Network)

# Redis connection fails
1. Test REDIS_URL locally:
   redis-cli -u $REDIS_URL ping
2. Check Upstash is running
3. Verify URL format: redis://:password@host:port

# Frontend shows API errors
1. Check VITE_API_URL in Vercel
2. Verify backend health: curl https://your-backend.onrender.com/health
3. Check browser console for CORS errors
4. Verify CORS_ORIGINS matches frontend URL

# Backend keeps sleeping
1. Verify cron job is running
2. Check cron logs
3. Set up UptimeRobot as backup
4. Ping URL manually: curl https://your-backend.onrender.com/health
```

## **Cost Check**

```
Vercel (Frontend): $0/month (unlimited)
Render (Backend): $0/month (free tier + keep-alive)
Supabase (Database): $0/month (500MB free)
Upstash (Redis): $0/month (10k cmd/day free)
Total: $0/month ✅
```

## **Dashboard Links**

- Render: https://dashboard.render.com
- Supabase: https://app.supabase.com
- Upstash: https://console.upstash.com
- Vercel: https://vercel.com/dashboard
- Clerk: https://dashboard.clerk.com
- LinkedIn: https://www.linkedin.com/developers
- NVIDIA: https://build.nvidia.com/nim

## **Files for Reference**

- Setup Guide: `FREE_HOSTING_SETUP.md` (detailed steps)
- Checklist: `DEPLOYMENT_CHECKLIST.md` (step-by-step)
- Secret Generator: `python generate_secrets.py`
- Render Config: `render.yaml`
- Environment Example: `.env.production.example`

## **Next Steps**

1. Run `python generate_secrets.py` and save outputs
2. Follow `DEPLOYMENT_CHECKLIST.md` step by step
3. Test with curl commands above
4. Verify logs in each dashboard
5. Keep backend alive with cron job

You're good to go! 🚀
