# Deploy Now - Complete Instructions

Your secrets are generated. Follow these exact steps to go live for free.

---

## **YOUR GENERATED SECRETS**

Copy these values exactly as shown:

```
SECRET_KEY=oZdGzUk3OwPujfQ6_nYgswHIrjgFrCgCFxGrqK7PksQ
API_ACCESS_KEY=mh8K8HLkaqT3_jGo1TECr66lYfBjyMjoMh0NYNtJAh0
ENCRYPTION_KEY=8RriyBT2cnKoG86ve7OpF4C-V_mchJj0veN66_H-RiQ=
```

Save these to a password manager NOW! 🔐

---

## **STEP 1: Create Supabase (Database) - 5 minutes**

### 1.1 Go to https://supabase.com
- Click "Start your project"
- Sign up with GitHub (fast!)
- Create new project:
  - Project name: `postpilot`
  - Region: Closest to you
  - Password: Create strong one, save it

### 1.2 Get Connection String
- Go to Settings → Database
- Look for "Connection string"
- Click on "Node.js" tab
- **Copy the full string** (starts with `postgresql://`)

Example format:
```
postgresql://postgres:PASSWORD@host.supabase.co:5432/postgres
```

**SAVE THIS as `DATABASE_URL`** - You'll need it in 5 minutes

---

## **STEP 2: Create Upstash (Redis Cache) - 5 minutes**

### 2.1 Go to https://upstash.com
- Click "Create Database"
- Sign up with GitHub
- Create new Redis:
  - Name: `postpilot-cache`
  - Region: Closest to you
  - Type: Free

### 2.2 Get Redis URL
- Click on database
- Copy "REDIS_URL" (starts with `redis://`)

Example format:
```
redis://:PASSWORD@host:port
```

**SAVE THIS as `REDIS_URL`** - You'll need it in 5 minutes

---

## **STEP 3: Get External API Keys - 10 minutes**

### 3.1 Clerk (Authentication)
- Go to https://dashboard.clerk.com
- Select your project "postpilot"
- Click "API Keys" (left sidebar)
- Copy "Secret Key" (starts with `sk_test_`)
- **SAVE THIS as `CLERK_SECRET_KEY`**

### 3.2 LinkedIn (OAuth)
- Go to https://www.linkedin.com/developers/apps
- Click your app
- Go to "Settings"
- Copy "Client ID"
- Copy "Client Secret"
- **SAVE THESE as `LINKEDIN_CLIENT_ID` and `LINKEDIN_CLIENT_SECRET`**

### 3.3 NVIDIA (AI)
- Go to https://build.nvidia.com/nim
- Click "API Keys"
- Copy your API key (starts with `nvapi-`)
- **SAVE THIS as `NVIDIA_API_KEY`**

---

## **STEP 4: Deploy Backend to Render - 15 minutes**

### 4.1 Create Render Account
- Go to https://render.com
- Sign up with GitHub (authorize it)
- It should redirect to dashboard

### 4.2 Create Web Service
- Click "New +" button
- Select "Web Service"
- Select your `postpilot` repository from GitHub list
- Click "Connect"

### 4.3 Configure Service
Fill in these exact values:

```
Name: postpilot-backend
Environment: Python
Build Command: pip install -r requirements.txt
Start Command: gunicorn -w 4 -b 0.0.0.0:5000 "backend.app:create_app()"
Plan: Free (select this!)
```

### 4.4 Add Environment Variables
Click "Environment" and add ALL of these:

```
FLASK_ENV=production
SECRET_KEY=oZdGzUk3OwPujfQ6_nYgswHIrjgFrCgCFxGrqK7PksQ
API_ACCESS_KEY=mh8K8HLkaqT3_jGo1TECr66lYfBjyMjoMh0NYNtJAh0
ENCRYPTION_KEY=8RriyBT2cnKoG86ve7OpF4C-V_mchJj0veN66_H-RiQ=
DATABASE_URL=<paste from Supabase>
REDIS_URL=<paste from Upstash>
CLERK_SECRET_KEY=<paste from Clerk>
LINKEDIN_CLIENT_ID=<paste from LinkedIn>
LINKEDIN_CLIENT_SECRET=<paste from LinkedIn>
NVIDIA_API_KEY=<paste from NVIDIA>
CORS_ORIGINS=https://postpilot.vercel.app
SCHEDULER_ENABLED=true
LOG_LEVEL=INFO
```

### 4.5 Deploy
- Click "Create Web Service"
- Wait 2-5 minutes for build
- Check logs for errors
- Wait for green "Live" status
- **Copy the URL** (looks like: `https://postpilot-backend.onrender.com`)

**SAVE THIS as `BACKEND_URL`**

---

## **STEP 5: Update Frontend - 5 minutes**

### 5.1 Vercel Dashboard
- Go to https://vercel.com/dashboard
- Click "postpilot" project
- Go to Settings → Environment Variables
- Find `VITE_API_URL`
- Change value to: `https://postpilot-backend.onrender.com` (your actual URL)
- Click "Save"

### 5.2 Redeploy
- Go to "Deployments" tab
- Click "Redeploy" on latest deployment
- Wait for build complete (shows green checkmark)

---

## **STEP 6: Test Everything - 5 minutes**

### 6.1 Backend Health
Open in browser:
```
https://postpilot-backend.onrender.com/health
```

Should show:
```json
{"status": "healthy", "database": "connected", "version": "1.0.0"}
```

### 6.2 Frontend
Open in browser:
```
https://postpilot.vercel.app
```

Should load without errors. Try logging in with Clerk.

### 6.3 API Test
Run in terminal (replace YOUR_API_KEY):
```bash
curl -H "Authorization: Bearer mh8K8HLkaqT3_jGo1TECr66lYfBjyMjoMh0NYNtJAh0" \
  https://postpilot-backend.onrender.com/api/status
```

Should return API status.

---

## **STEP 7: Keep Backend Alive - 2 minutes**

Your cron job should already be configured to ping every 10 minutes.

**Just verify it's hitting:**
```
https://postpilot-backend.onrender.com/health
```

If not, set up UptimeRobot (backup):
1. Go to https://uptimerobot.com
2. Sign up (free)
3. Create monitor:
   - URL: `https://postpilot-backend.onrender.com/health`
   - Interval: 5 minutes

---

## **YOU'RE LIVE! 🚀**

### Check These
- [ ] Backend health returns 200
- [ ] Frontend loads without errors
- [ ] API endpoint responds
- [ ] Can log in with Clerk
- [ ] Render logs show no errors
- [ ] Database is connected
- [ ] Cron keeps backend alive

### Your URLs
- **Frontend**: https://postpilot.vercel.app
- **Backend**: https://postpilot-backend.onrender.com
- **API**: https://postpilot-backend.onrender.com/api/*

### Total Cost
- **$0/month** ✅

### Dashboards to Monitor
- Render: https://dashboard.render.com
- Supabase: https://app.supabase.com
- Upstash: https://console.upstash.com
- Vercel: https://vercel.com/dashboard

---

## **If Something Breaks**

### Backend won't start
1. Check Render Logs tab
2. Look for error messages
3. Verify all environment variables are set
4. Check DATABASE_URL format is correct

### Can't connect to database
1. Test on Supabase: SQL Editor → SELECT 1
2. Verify DATABASE_URL is correct
3. Check IP whitelist (Supabase → Settings → Network)

### Redis not working
1. Test on Upstash: Redis Console → PING
2. Verify REDIS_URL is correct

### Frontend shows API errors
1. Check browser console (F12)
2. Verify VITE_API_URL is correct
3. Test backend health manually

### Backend keeps sleeping
1. Verify cron job is running
2. Check cron logs
3. Set up UptimeRobot as backup

---

Done! Your app is now deployed for free. 🎉

**Total time: ~50 minutes**
**Total cost: $0/month**

Need help? Check QUICK_REFERENCE.md for commands.
