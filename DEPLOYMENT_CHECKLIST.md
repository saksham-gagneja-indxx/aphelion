# Free Hosting Deployment Checklist

Follow these steps to deploy for free on Render + Supabase + Upstash.

---

## **Phase 1: Generate Secrets** ⭐

- [ ] Run: `python generate_secrets.py`
- [ ] Save output to secure location (1Password, Vault, etc.)
- [ ] Copy the three values:
  - [ ] `SECRET_KEY`
  - [ ] `API_ACCESS_KEY`
  - [ ] `ENCRYPTION_KEY`

---

## **Phase 2: Create Accounts**

### Supabase (Database)
- [ ] Go to https://supabase.com
- [ ] Sign up with GitHub
- [ ] Create new project named "postpilot"
- [ ] Set database password (save it!)
- [ ] Wait for project creation (2-3 min)
- [ ] Go to Settings → Database → Connection Pooling
- [ ] Copy PostgreSQL connection string
- [ ] Verify format: `postgresql://postgres:password@host:5432/postgres`
- [ ] Save as `DATABASE_URL`

### Upstash (Redis Cache)
- [ ] Go to https://upstash.com
- [ ] Sign up with GitHub
- [ ] Create new Redis database
- [ ] Name: "postpilot-cache"
- [ ] Copy Redis URL
- [ ] Verify format: `redis://:password@host:port`
- [ ] Save as `REDIS_URL`

### Render (Backend)
- [ ] Go to https://render.com
- [ ] Sign up with GitHub
- [ ] Authorize Render to access your GitHub
- [ ] Keep dashboard open for next step

---

## **Phase 3: Get External API Keys**

### Clerk (Authentication)
- [ ] Go to https://clerk.com dashboard
- [ ] Select your project
- [ ] Go to API Keys
- [ ] Copy "Secret Key" (starts with `sk_test_`)
- [ ] Save as `CLERK_SECRET_KEY`

### LinkedIn (OAuth)
- [ ] Go to https://www.linkedin.com/developers
- [ ] Select your app
- [ ] Go to Settings → App credentials
- [ ] Copy "Client ID"
- [ ] Copy "Client secret"
- [ ] Save as `LINKEDIN_CLIENT_ID` and `LINKEDIN_CLIENT_SECRET`

### NVIDIA (AI/ML)
- [ ] Go to https://build.nvidia.com/nim
- [ ] Go to API Keys
- [ ] Copy your API key (starts with `nvapi-`)
- [ ] Save as `NVIDIA_API_KEY`

---

## **Phase 4: Deploy Backend to Render**

### Create Web Service
- [ ] In Render dashboard: "New Web Service"
- [ ] Connect to your GitHub repository
- [ ] Click "postpilot" repo
- [ ] Select branch: "main"

### Configure Build
- [ ] Name: `postpilot-backend`
- [ ] Environment: Python
- [ ] Build Command: `pip install -r requirements.txt`
- [ ] Start Command: `gunicorn -w 4 -b 0.0.0.0:5000 "backend.app:create_app()"`
- [ ] Plan: **Free** ⭐

### Set Environment Variables
In Render environment variables, add:

- [ ] `FLASK_ENV` = `production`
- [ ] `SECRET_KEY` = (from step 1)
- [ ] `API_ACCESS_KEY` = (from step 1)
- [ ] `ENCRYPTION_KEY` = (from step 1)
- [ ] `DATABASE_URL` = (from Supabase)
- [ ] `REDIS_URL` = (from Upstash)
- [ ] `CLERK_SECRET_KEY` = (from Clerk)
- [ ] `LINKEDIN_CLIENT_ID` = (from LinkedIn)
- [ ] `LINKEDIN_CLIENT_SECRET` = (from LinkedIn)
- [ ] `NVIDIA_API_KEY` = (from NVIDIA)
- [ ] `CORS_ORIGINS` = `https://postpilot.vercel.app`
- [ ] `SCHEDULER_ENABLED` = `true`
- [ ] `LOG_LEVEL` = `INFO`

### Deploy
- [ ] Click "Create Web Service"
- [ ] Wait for build (takes 2-5 minutes)
- [ ] Check logs for errors
- [ ] Wait for "Live" status
- [ ] Copy the URL (e.g., `https://postpilot-backend.onrender.com`)
- [ ] Save as `BACKEND_URL`

---

## **Phase 5: Test Backend**

### Health Check
- [ ] Open in browser: `https://postpilot-backend.onrender.com/health`
- [ ] Should see: `{"status": "healthy", "database": "connected"}`
- [ ] If error, check Render logs

### API Endpoint
- [ ] Run: `curl -H "Authorization: Bearer <API_ACCESS_KEY>" https://postpilot-backend.onrender.com/api/status`
- [ ] Should see: `{"app": "Social Media Automation Agent", ...}`

---

## **Phase 6: Update Frontend**

### Vercel Environment
- [ ] Go to https://vercel.com/dashboard
- [ ] Select "postpilot" project
- [ ] Settings → Environment Variables
- [ ] Update `VITE_API_URL`:
  - [ ] Value: `https://postpilot-backend.onrender.com` (your Render URL)
  - [ ] Environments: Production, Preview, Development
- [ ] Save

### Redeploy Frontend
- [ ] Go to Deployments tab
- [ ] Click "Redeploy" on latest deployment
- [ ] Wait for build to complete
- [ ] Check for green checkmark

---

## **Phase 7: Test Everything**

### Frontend
- [ ] Open https://postpilot.vercel.app
- [ ] Should load without errors
- [ ] Check browser console (F12) for errors
- [ ] Try logging in with Clerk

### Backend Connectivity
- [ ] Try creating a post (should work)
- [ ] Check Render logs for requests
- [ ] Try uploading media (should work)

### Database
- [ ] Try accessing user data
- [ ] Check Supabase dashboard for data

---

## **Phase 8: Keep Backend Alive**

Since Render free tier sleeps after 15 minutes of inactivity:

### Option A: Your Existing Cron Job ✅
- [ ] Update your cron to ping: `https://postpilot-backend.onrender.com/health`
- [ ] Set interval: Every 10 minutes
- [ ] Verify cron job is running

### Option B: UptimeRobot (Backup)
- [ ] Go to https://uptimerobot.com
- [ ] Sign up (free)
- [ ] Add Monitor:
  - [ ] URL: `https://postpilot-backend.onrender.com/health`
  - [ ] Monitor Type: HTTP(s)
  - [ ] Interval: 5 minutes
- [ ] Save

---

## **Phase 9: Verify Deployment**

- [ ] ✅ Backend health: `https://postpilot-backend.onrender.com/health`
- [ ] ✅ Frontend loads: `https://postpilot.vercel.app`
- [ ] ✅ API responds: `/api/status` with API key
- [ ] ✅ Database connected: Render logs show connection
- [ ] ✅ Cron job pinging: Backend doesn't sleep
- [ ] ✅ All environment variables set
- [ ] ✅ No errors in browser console
- [ ] ✅ No errors in Render logs

---

## **You're Live! 🚀**

**Total Cost: $0/month**

### Quick Stats
- Frontend: Vercel (unlimited free)
- Backend: Render (free with keep-alive)
- Database: Supabase (500MB free)
- Cache: Upstash (10k cmd/day free)
- Cron: Your setup (already configured)

### Useful Links
- Render Dashboard: https://dashboard.render.com
- Supabase Dashboard: https://app.supabase.com
- Upstash Dashboard: https://console.upstash.com
- Vercel Dashboard: https://vercel.com/dashboard

---

## **Troubleshooting**

### Build Fails
1. Check Render build logs
2. Look for Python dependency errors
3. Verify `requirements.txt` exists
4. Check environment variables

### Backend Won't Connect
1. Verify DATABASE_URL is correct
2. Test database connection in Supabase
3. Check Render environment variables
4. Look at Render logs

### Frontend Shows API Errors
1. Check `VITE_API_URL` in Vercel
2. Verify backend is running (health check)
3. Check CORS origin is correct
4. Look at browser network tab

### Keep-Alive Not Working
1. Verify cron job is configured
2. Check cron job logs
3. Test URL manually: `curl https://your-backend.onrender.com/health`
4. Set up UptimeRobot as backup

---

Done! ✅ You now have a complete free production deployment.
