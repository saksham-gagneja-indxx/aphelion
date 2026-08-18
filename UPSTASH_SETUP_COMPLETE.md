# Upstash Redis Setup - Complete

Your Upstash Redis "postpilot" cache is ready!

---

## **Your Credentials**

```
REST URL: https://trusty-bengal-98742.upstash.io
REST Token: gQAAAAAAAYG2AAIgcDE3NGIxOTE3YzdjNDk0NDYzOGRmZTk0NjFhODhiMTYzOQ
```

---

## **What This Gives You**

✅ **Redis Caching**
- Session storage
- Post scheduling cache
- User data caching
- LinkedIn token caching
- Rate limiting

✅ **Performance**
- ~50ms latency
- 30MB storage free tier
- 10,000 commands/day free
- Auto-scaling when needed

✅ **Features**
- Automatic expiration
- Key-value operations
- Pub/Sub support
- Persistence enabled

---

## **Backend Integration Ready**

New file created: `backend/core/cache.py`

Features:
- Direct Redis connection support
- Upstash REST API fallback
- Automatic connection pooling
- Error handling & logging
- Session management
- Data caching utilities

---

## **Environment Variables**

Add to Render:

```
UPSTASH_REDIS_REST_URL=https://trusty-bengal-98742.upstash.io
UPSTASH_REDIS_REST_TOKEN=gQAAAAAAAYG2AAIgcDE3NGIxOTE3YzdjNDk0NDYzOGRmZTk0NjFhODhiMTYzOQ
```

Or use Redis protocol:

```
REDIS_URL=redis://:password@host:port
```

---

## **Testing Connection**

```python
from backend.core.cache import get_cache

cache = get_cache()

# Set data
cache.set("test_key", "test_value", ex=3600)

# Get data
value = cache.get("test_key")
print(value)  # Should print: test_value

# Delete
cache.delete("test_key")
```

---

## **Usage in Application**

### Session Caching
```python
from backend.core.cache import get_cache

cache = get_cache()

# Store session
cache.set(f"session:{user_id}", session_data, ex=86400)

# Retrieve session
session = cache.get(f"session:{user_id}")
```

### Post Scheduling
```python
# Cache scheduled post
cache.set(f"post:{post_id}", post_data, ex=3600)

# Update cache on post publish
cache.delete(f"post:{post_id}")
```

### Rate Limiting
```python
# Track API calls
key = f"api:{user_id}:calls"
cache.set(key, calls_count, ex=60)

# Check rate limit
current = cache.get(key)
if int(current or 0) > RATE_LIMIT:
    return 429  # Too Many Requests
```

---

## **Monitoring**

### Upstash Dashboard
- https://console.upstash.com
- View: Commands, memory usage, latency
- Settings: Price, auto-scaling, backup

### Metrics to Watch
- Commands/day: Free tier = 10,000
- Memory: Free tier = 30MB
- Response time: Should be <50ms

---

## **Troubleshooting**

### Connection Fails
1. Verify REST URL and token
2. Check Upstash dashboard is accessible
3. Verify firewall allows HTTPS
4. Test with: `curl https://trusty-bengal-98742.upstash.io`

### Memory Full
1. Check Upstash console for memory usage
2. Implement TTL (auto-expiration)
3. Clear old cache: `cache.flush()`
4. Upgrade plan if needed

### Slow Response
1. Check network latency
2. Verify token is correct
3. Monitor command count (rate limit)
4. Use direct Redis connection if available

---

## **Next: Complete Deployment**

Your stack is now:
- ✅ Supabase (Database)
- ✅ Upstash Redis (Cache)
- ⏳ Render (Backend) - Ready to deploy
- ⏳ Vercel (Frontend) - Ready to update

**Continue with DEPLOY_WITH_SUPABASE.md steps 3-7**

---

## **Cost Summary**

```
Supabase:  $0/month (500MB free)
Upstash:   $0/month (10k cmd/day free)
Render:    $0/month (free tier)
Vercel:    $0/month (unlimited)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total:     $0/month ✅
```

---

You're 2/3 of the way there! Keep going! 🚀
