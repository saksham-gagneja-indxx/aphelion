# Complete Free Hosting Setup Guide

Deploy everything for free using Render, Supabase, and Upstash.

**Total Cost: $0/month** ✅

---

## **1. Generate Required Secrets**

Run these in Python to generate secure keys:

```python
import secrets
from cryptography.fernet import Fernet

# Generate SECRET_KEY
SECRET_KEY = secrets.token_urlsafe(32)
print(f"SECRET_KEY={SECRET_KEY}")

# Generate API_ACCESS_KEY
API_ACCESS_KEY = secrets.token_urlsafe(32)
print(f"API_ACCESS_KEY={API_ACCESS_KEY}")

# Generate ENCRYPTION_KEY
ENCRYPTION_KEY = Fernet.generate_key().decode()
print(f"ENCRYPTION_KEY={ENCRYPTION_KEY}")
```

**Save these keys safely** - you'll need them in step 5.

---

## **2. Set Up Supabase (Free PostgreSQL Database)**

### **Create Account**
1. Go to https://supabase.com
2. Click "Start your project"
3. Sign up with GitHub or email
4. Create new project
   - Name: `postpilot`
   - Database password: **Save this!**
   - Region: Choose closest to you
   - Pricing: Free

### **Get Connection String**
1. Go to Project Settings → Database
2. Copy "Connection string"
3. Select "Node.js" tab
4. Copy the full string (looks like: `postgresql://[user]:[password]@[host]:[port]/[database]`)

**Save this as DATABASE_URL**

### **Run Database Migrations**
```bash
# Once backend is deployed to Render:
# Render will automatically create tables via SQLAlchemy

# Or manually from your computer:
export DATABASE_URL="postgresql://..."
python -c "from backend.utils.database import init_db; init_db()"
```

---

## **3. Set Up Upstash (Free Redis Cache)**

### **Create Account**
1. Go to https://upstash.com
2. Sign up with GitHub
3. Create new Redis database
   - Name: `postpilot-cache`
   - Region: Choose closest to you
   - Type: Free

### **Get Connection String**
1. Click database name
2. Copy "REDIS_URL" (looks like: `redis://:password@host:port`)

**Save this as REDIS_URL**

---

## **4. Deploy Backend to Render**

### **Create Account & Connect GitHub**
1. Go to https://render.com
2. Sign up with GitHub
3. Authorize Render to access your repositories
4. Click "New Web Service"
5. Select your `postpilot` repository

### **Configure Deployment**
1. **Name**: `postpilot-backend`
2. **Runtime**: Python
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**: `gunicorn -w 4 -b 0.0.0.0:5000 "backend.app:create_app()"`
5. **Plan**: Free

### **Set Environment Variables**
Click "Environment" and add:

```
FLASK_ENV=production
SECRET_KEY=<from step 1>
API_ACCESS_KEY=<from step 1>
DATABASE_URL=<from Supabase>
REDIS_URL=<from Upstash>
CLERK_SECRET_KEY=<your Clerk secret key>
ENCRYPTION_KEY=<from step 1>
LINKEDIN_CLIENT_ID=<your LinkedIn app ID>
LINKEDIN_CLIENT_SECRET=<your LinkedIn app secret>
NVIDIA_API_KEY=<your NVIDIA NIM key>
CORS_ORIGINS=https://postpilot.vercel.app
SCHEDULER_ENABLED=true
LOG_LEVEL=INFO
```

**Where to get each value:**
- `CLERK_SECRET_KEY`: Clerk Dashboard → API Keys → Secret Key
- `LINKEDIN_CLIENT_ID/SECRET`: LinkedIn Developer Portal
- `NVIDIA_API_KEY`: NVIDIA NIM Dashboard

### **Deploy**
1. Click "Create Web Service"
2. Wait for build (2-5 minutes)
3. Once deployed, copy the URL (looks like: `https://postpilot-backend.onrender.com`)

**Save this as your BACKEND_URL**

---

## **5. Update Frontend Deployment**

### **Update Vercel Environment**
1. Go to Vercel dashboard
2. Select `postpilot` project
3. Go to Settings → Environment Variables
4. Update `VITE_API_URL`:
   ```
   VITE_API_URL=https://postpilot-backend.onrender.com
   ```
5. Redeploy (automatic or manual)

Or update in `.env`:
```
VITE_API_URL=https://postpilot-backend.onrender.com
```

Then push to GitHub:
```bash
git add .env
git commit -m "chore: update API URL for production"
git push origin main
```

---

## **6. Test Everything**

### **Backend Health Check**
```bash
curl https://postpilot-backend.onrender.com/health
# Should return: {"status": "healthy", "database": "connected"}
```

### **Frontend**
1. Go to https://postpilot.vercel.app
2. Should load without errors
3. Try logging in with Clerk

### **API Endpoint**
```bash
curl -H "Authorization: Bearer <API_ACCESS_KEY>" \
  https://postpilot-backend.onrender.com/api/status

# Should return: {"app": "Social Media Automation Agent", ...}
```

---

## **7. Keep Backend Alive (Important!)**

Since Render free tier sleeps after 15 minutes of inactivity:

### **Option A: Use Existing Cron Job** ✅
Your existing cron job should ping:
```
https://postpilot-backend.onrender.com/health
```

### **Option B: Set Up UptimeRobot (Free)**
1. Go to https://uptimerobot.com
2. Create account
3. Add monitor:
   - URL: `https://postpilot-backend.onrender.com/health`
   - Interval: 5 minutes
4. Free tier allows 50 monitors

---

## **Free Tier Limits & Usage**

### **Render (Backend)**
- ✅ Web service: Free
- ⚠️ Sleeps after 15 min inactivity (keep-alive solves this)
- ✅ Auto-redeploy on push

### **Supabase (Database)**
- ✅ PostgreSQL: 500MB free
- ✅ 2 concurrent connections
- ✅ Enough for MVP/testing
- 📊 Current usage: ~5MB (plenty of room)

### **Upstash (Redis)**
- ✅ Free: 10,000 commands/day
- ✅ 30MB storage
- 📊 Current usage: ~100 cmd/day (plenty)

---

## **Cost Breakdown**

| Service | Free Tier | Cost | After Upgrade |
|---------|-----------|------|---|
| Vercel (Frontend) | Unlimited | $0 | $0 |
| Render (Backend) | Yes | $0 | $7/mo |
| Supabase (Database) | 500MB | $0 | $25/mo |
| Upstash (Redis) | 10k cmd/day | $0 | $25/mo |
| **Total** | | **$0** | **~$60/mo** |

---

## **Troubleshooting**

### **Backend shows "Build Failed"**
Check Render logs:
1. Go to Render dashboard
2. Select service
3. Click "Logs" tab
4. Look for errors (usually missing environment variables)

### **"Database connection failed"**
1. Verify DATABASE_URL is correct in Render environment
2. Check Supabase is running (go to supabase.com dashboard)
3. Verify IP whitelist (Supabase → Settings → Network)

### **"Redis connection failed"**
1. Verify REDIS_URL is correct in Render environment
2. Check Upstash dashboard is running
3. Try pinging: `redis-cli -u $REDIS_URL ping`

### **Frontend shows API errors**
1. Check `VITE_API_URL` in Vercel environment
2. Verify backend health: `curl https://your-backend.onrender.com/health`
3. Check CORS headers in browser console

### **Backend keeps falling asleep**
1. Verify cron job is actually pinging the endpoint
2. Check cron job logs
3. Set up UptimeRobot as backup (every 5 minutes)

---

## **Next Steps**

1. ✅ Generate secrets (step 1)
2. ✅ Create Supabase account (step 2)
3. ✅ Create Upstash account (step 3)
4. ✅ Deploy to Render (step 4)
5. ✅ Update Vercel (step 5)
6. ✅ Test everything (step 6)
7. ✅ Set up keep-alive (step 7)

**You're live!** 🚀

---

## **Useful Links**

- Render Dashboard: https://dashboard.render.com
- Supabase Dashboard: https://app.supabase.com
- Upstash Dashboard: https://console.upstash.com
- Vercel Dashboard: https://vercel.com/dashboard
- GitHub Repo: https://github.com/saksham-gagneja-indxx/postpilot

---

## **Support**

If you get stuck:
1. Check Render/Supabase/Upstash logs
2. Verify all environment variables are set correctly
3. Test individual components (database, cache, API)
4. Review this guide for your specific service
