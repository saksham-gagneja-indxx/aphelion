# Deploy Now - With Supabase Setup

Your Supabase secret key is ready. Complete deployment in ~40 minutes.

---

## **YOUR SUPABASE CREDENTIALS**

✅ Secret Key Ready:
```
sb_secret_[YOUR_KEY_HERE]
```
(You already have this from Supabase dashboard)

✅ Your Production Secrets Ready:
```
SECRET_KEY=oZdGzUk3OwPujfQ6_nYgswHIrjgFrCgCFxGrqK7PksQ
API_ACCESS_KEY=mh8K8HLkaqT3_jGo1TECr66lYfBjyMjoMh0NYNtJAh0
ENCRYPTION_KEY=8RriyBT2cnKoG86ve7OpF4C-V_mchJj0veN66_H-RiQ=
```

---

## **STEP 1: Set Up Supabase Database - 10 minutes**

### 1.1 Go to Supabase Dashboard
- Open https://app.supabase.com
- Sign in / Select your project

### 1.2 Get Project URL
- Settings → General
- Copy "Project URL" (looks like: `https://xxxxx.supabase.co`)
- Save as `SUPABASE_URL`

### 1.3 Initialize Database
- Go to SQL Editor (left sidebar)
- Click "New Query"
- Copy ALL content from `supabase_init.sql` file in repo
- Paste into SQL editor
- Click "Run"
- Wait for "Success" message (all 6 tables created)

### 1.4 Get Connection String
- Settings → Database → Connection Pooling
- Click on "Connection string"
- Select "Node.js" tab
- Copy the string
- Replace `[YOUR-PASSWORD]` with your Supabase database password

**This is your `DATABASE_URL`**

Example:
```
postgresql://postgres:yourpassword@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

---

## **STEP 2: Create Upstash (Redis) - 5 minutes**

### 2.1 Go to https://upstash.com
- Sign up with GitHub
- Create new Redis database
- Name: `postpilot-cache`
- Region: Closest to you

### 2.2 Get Redis URL
- Click on database
- Copy "REDIS_URL"

Example:
```
redis://:password@host:port
```

**Save this as `REDIS_URL`**

---

## **STEP 3: Get External API Keys - 10 minutes**

### 3.1 Clerk (Authentication)
- https://dashboard.clerk.com
- Select project
- API Keys (left sidebar)
- Copy "Secret Key" (starts with `sk_test_`)
- Save as `CLERK_SECRET_KEY`

### 3.2 LinkedIn (OAuth)
- https://www.linkedin.com/developers/apps
- Select your app
- Settings → App credentials
- Copy "Client ID"
- Copy "Client Secret"
- Save as `LINKEDIN_CLIENT_ID` and `LINKEDIN_CLIENT_SECRET`

### 3.3 NVIDIA (AI)
- https://build.nvidia.com/nim
- API Keys
- Copy your key (starts with `nvapi-`)
- Save as `NVIDIA_API_KEY`

---

## **STEP 4: Deploy Backend to Render - 15 minutes**

### 4.1 Go to https://render.com
- Sign up with GitHub (authorize it)
- Goes to dashboard

### 4.2 Create Web Service
- Click "New +" button
- Select "Web Service"
- Select "postpilot" repository
- Click "Connect"

### 4.3 Configure
```
Name: postpilot-backend
Environment: Python
Build Command: pip install -r requirements.txt
Start Command: gunicorn -w 4 -b 0.0.0.0:5000 "backend.app:create_app()"
Plan: Free
```

### 4.4 Add ALL Environment Variables

```
FLASK_ENV=production
SECRET_KEY=oZdGzUk3OwPujfQ6_nYgswHIrjgFrCgCFxGrqK7PksQ
API_ACCESS_KEY=mh8K8HLkaqT3_jGo1TECr66lYfBjyMjoMh0NYNtJAh0
ENCRYPTION_KEY=8RriyBT2cnKoG86ve7OpF4C-V_mchJj0veN66_H-RiQ=
DATABASE_URL=postgresql://postgres:PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres
REDIS_URL=redis://:password@host:port
CLERK_SECRET_KEY=sk_test_...
LINKEDIN_CLIENT_ID=<your-id>
LINKEDIN_CLIENT_SECRET=<your-secret>
NVIDIA_API_KEY=nvapi-...
CORS_ORIGINS=https://postpilot.vercel.app
SCHEDULER_ENABLED=true
LOG_LEVEL=INFO
```

### 4.5 Deploy
- Click "Create Web Service"
- Wait 2-5 minutes
- Check logs for errors
- Wait for green "Live" status
- Copy URL (like: `https://postpilot-backend.onrender.com`)

**Save as `BACKEND_URL`**

---

## **STEP 5: Update Vercel Frontend - 5 minutes**

### 5.1 Go to https://vercel.com/dashboard
- Select "postpilot" project
- Settings → Environment Variables
- Find `VITE_API_URL`
- Update to: `https://postpilot-backend.onrender.com`
- Save

### 5.2 Redeploy
- Go to Deployments tab
- Click "Redeploy" on latest
- Wait for green checkmark

---

## **STEP 6: Test Everything**

### 6.1 Backend Health
```
https://postpilot-backend.onrender.com/health
```

Should show:
```json
{"status": "healthy", "database": "connected", "version": "1.0.0"}
```

### 6.2 Frontend
```
https://postpilot.vercel.app
```

Should load. Try logging in.

### 6.3 API Test
```bash
curl -H "Authorization: Bearer mh8K8HLkaqT3_jGo1TECr66lYfBjyMjoMh0NYNtJAh0" \
  https://postpilot-backend.onrender.com/api/status
```

Should return status info.

---

## **STEP 7: Keep Alive**

Your cron job should ping:
```
https://postpilot-backend.onrender.com/health
```

Every 10 minutes to keep backend alive.

Verify it's working or set up UptimeRobot backup.

---

## **YOU'RE LIVE! 🚀**

### Verify
- [ ] Backend health = 200
- [ ] Frontend loads
- [ ] API responds
- [ ] Can log in
- [ ] No errors in logs
- [ ] Cron keeps alive

### Your URLs
```
Frontend:  https://postpilot.vercel.app
Backend:   https://postpilot-backend.onrender.com
```

### Cost
```
$0/month ✅
```

### Dashboards
```
Render:    https://dashboard.render.com
Supabase:  https://app.supabase.com
Upstash:   https://console.upstash.com
Vercel:    https://vercel.com/dashboard
```

---

## **Database is Live**

Your Supabase tables:
- ✅ users
- ✅ linkedin_credentials
- ✅ media_files
- ✅ posts
- ✅ analytics
- ✅ audit_log

All ready for data!

---

**Total Time: ~40 minutes**
**Total Cost: $0/month**

You're deployed! 🎉
