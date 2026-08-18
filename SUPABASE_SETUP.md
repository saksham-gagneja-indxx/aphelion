# Supabase Database Setup

Complete guide to set up your Supabase PostgreSQL database.

---

## **Your Supabase Credentials**

```
Secret Key: sb_secret_[REPLACE_WITH_YOUR_KEY]
```

You received this from your Supabase project setup email or dashboard.

---

## **Step 1: Find Your Project URL**

### 1.1 Go to Supabase Dashboard
- Open https://app.supabase.com
- Select your "postpilot" project

### 1.2 Get Project URL
- Go to Settings → General
- Copy "Project URL" (looks like: `https://xxxxx.supabase.co`)

**Save this as `SUPABASE_URL`**

---

## **Step 2: Initialize Database**

### 2.1 Open SQL Editor
- In Supabase dashboard
- Go to SQL Editor (left sidebar)
- Click "New Query"

### 2.2 Run Initialization Script
- Copy entire content from `supabase_init.sql`
- Paste into SQL editor
- Click "Run"
- Wait for completion (should see all tables created)

### 2.3 Verify Tables Created
Run this to confirm:
```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

Should see:
```
analytics
audit_log
linkedin_credentials
media_files
posts
users
```

---

## **Step 3: Get Connection String**

### 3.1 Connection Pooling
- Go to Settings → Database → Connection Pooling
- Click on "Connection string"
- Select "Node.js" tab
- Copy the full connection string

Format:
```
postgresql://postgres:[password]@[host]:[port]/postgres
```

### 3.2 Create DATABASE_URL
Replace `[password]` with your Supabase database password.

**This is your `DATABASE_URL`** for Render

---

## **Step 4: Create Anon & Service Role Keys**

### 4.1 Get Service Role Key (if needed)
- Settings → API Keys
- Copy "Service Role Secret Key"

### 4.2 Get Anon Key
- Settings → API Keys
- Copy "Anon Public Key"

These are optional for your setup, but good to have.

---

## **Step 5: Configure Render Environment**

Once you have everything, add to Render:

```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

---

## **Step 6: Test Connection**

### 6.1 From Python
```python
from sqlalchemy import create_engine

engine = create_engine(os.getenv("DATABASE_URL"))
with engine.connect() as connection:
    result = connection.execute("SELECT 1")
    print("Database connected!")
```

### 6.2 From Supabase UI
- Go to SQL Editor
- Run: `SELECT COUNT(*) FROM users;`
- Should return 0

---

## **Step 7: Verify Tables**

In Supabase Table Editor:

- [ ] users - User accounts
- [ ] linkedin_credentials - OAuth tokens
- [ ] media_files - Uploaded media
- [ ] posts - Social media posts
- [ ] analytics - Post analytics
- [ ] audit_log - Action logs

---

## **Your Connection Details**

Save these values:

```
Project URL: https://[project-id].supabase.co
API Key: (from Settings → API Keys)
Database URL: postgresql://postgres:[password]@[host]:6543/postgres
Secret Key: (from Settings → API Keys → Service Role Secret Key)
```

---

## **Database Schema**

### Users Table
- `id` (Primary Key)
- `clerk_id` (from Clerk authentication)
- `email`
- `full_name`
- `avatar_url`
- Timestamps

### LinkedIn Credentials
- `id`
- `user_id` (Foreign Key)
- `access_token_encrypted`
- `refresh_token_encrypted`
- `person_urn`
- `expires_at`
- Connection status flags

### Media Files
- `id`
- `user_id`
- `filename`
- `file_size_bytes`
- `media_type` (video/image)
- `storage_path`
- Duration, dimensions for videos
- Expiration date (30 days)

### Posts
- `id`
- `user_id`
- `media_file_id`
- `caption`
- `status` (draft/scheduled/posted)
- `scheduled_time`
- `linkedin_post_id`
- Analytics: views, likes, comments, shares

### Analytics
- `id`
- `user_id`
- `post_id`
- Date-based metrics
- Engagement tracking

### Audit Log
- `id`
- `user_id`
- `action`
- `target`
- `ip_address`
- Timestamp

---

## **Row Level Security (Optional)**

Tables have RLS enabled by default:
- Users can only view/edit their own data
- Policies prevent cross-user access

To modify RLS policies:
- Go to Authentication → Policies
- Edit policies as needed

---

## **Next Steps**

1. ✅ Find Project URL
2. ✅ Run `supabase_init.sql` in SQL Editor
3. ✅ Get Connection String
4. ✅ Save DATABASE_URL
5. ✅ Add to Render environment
6. ✅ Test connection

---

## **Troubleshooting**

### SQL Script Fails
- Check syntax in SQL editor
- Ensure project exists
- Verify auth token is valid
- Try running tables one at a time

### Connection String Issues
- Copy exact string from Supabase
- Replace `[password]` with actual password
- Verify host matches your region
- Check port is 6543 (pooling) or 5432 (direct)

### Tables Don't Appear
- Refresh page
- Check SQL tab → All Schemas
- Verify "public" schema is selected

### Row Level Security Issues
- Go to Authentication → Policies
- Disable temporarily to test
- Re-enable with correct Clerk integration

---

## **Database Limits (Free Tier)**

- Storage: 500 MB
- Concurrent connections: 2
- Bandwidth: Sufficient for MVP
- Backups: Automatic daily

If you exceed, upgrade to Pro ($25/month)

---

Done! Your Supabase database is ready. 🎉
