# Clerk Authentication Setup - Complete

Your Clerk secret key is configured and ready!

---

## **Your Clerk Credentials**

```
Secret Key: sk_test_NuKFI59kHwWnsOFKAqZTAfqTHnrv1zXZ2oBCtnvzFG
Publishable Key: pk_test_bm9ibGUtZ2xvd3dvcm0tMTQ0LmNsZXJrLmFjY291bnRzLmRldiQ
```

---

## **What This Gives You**

✅ **User Authentication**
- OAuth/Social login (Google, GitHub, etc.)
- Email/password signup
- Session management
- User profile storage
- Automatic user creation

✅ **Security Features**
- JWT tokens with expiration
- Secure session handling
- Rate limiting on auth endpoints
- Password hashing
- CORS-aware

✅ **Integration**
- Frontend: Clerk React component
- Backend: JWT verification
- Database: Auto-user creation
- Analytics: User tracking

---

## **How It Works**

### **1. Frontend Flow**
```
User signs in via Clerk UI
         ↓
Clerk issues JWT token
         ↓
Frontend sends token to backend
         ↓
Backend verifies & creates session
         ↓
App is authenticated!
```

### **2. Backend Flow**
```
POST /auth/login with Clerk token
         ↓
Verify JWT signature
         ↓
Extract clerk_id & email
         ↓
Find or create user in database
         ↓
Create session token (24-hour expiry)
         ↓
Return session token
```

### **3. Protected Endpoints**
```
All /api/* endpoints require:
  Authorization: Bearer {session_token}
         ↓
Middleware verifies token
         ↓
If invalid: 401 Unauthorized
If valid: Route handler executes
```

---

## **Environment Variables**

Add to Render:

```
CLERK_SECRET_KEY=sk_test_NuKFI59kHwWnsOFKAqZTAfqTHnrv1zXZ2oBCtnvzFG
SECRET_KEY=oZdGzUk3OwPujfQ6_nYgswHIrjgFrCgCFxGrqK7PksQ
```

---

## **Frontend Setup**

Already configured in `frontend/src/main.tsx`:

```javascript
import { ClerkProvider } from '@clerk/clerk-react'

<ClerkProvider publishableKey={VITE_CLERK_PUBLISHABLE_KEY}>
  <App />
</ClerkProvider>
```

---

## **Testing Authentication**

### **1. Login Test**
```bash
# Get Clerk token from frontend or dashboard
CLERK_TOKEN="eyJ..."

# Call login endpoint
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"clerk_token\": \"$CLERK_TOKEN\"}"

# Response:
{
  "session_token": "eyJ...",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "full_name": "John Doe"
  }
}
```

### **2. Protected Endpoint Test**
```bash
SESSION_TOKEN="eyJ..."

curl -X GET http://localhost:5000/api/status \
  -H "Authorization: Bearer $SESSION_TOKEN"

# Should return API status with 200 OK
```

### **3. Logout Test**
```bash
SESSION_TOKEN="eyJ..."

curl -X POST http://localhost:5000/auth/logout \
  -H "Authorization: Bearer $SESSION_TOKEN"

# Response:
{
  "message": "Logged out successfully"
}
```

---

## **User Creation Flow**

1. User signs up via Clerk frontend
2. Clerk creates user in Clerk database
3. Clerk issues JWT token
4. User sends token to `/auth/login`
5. Backend verifies token
6. Backend creates entry in `users` table
7. User is now authenticated in your app

---

## **Session Token Details**

### **Token Format**
```
Header: {
  "typ": "JWT",
  "alg": "HS256"
}

Payload: {
  "user_id": 1,          # Database user ID
  "clerk_id": "user_...", # Clerk user ID
  "iat": 1692345600,     # Issued at
  "exp": 1692432000      # Expires in 24 hours
}

Signature: HS256(SECRET_KEY)
```

### **Token Lifetime**
- Valid for: 24 hours
- Auto-refresh: Frontend should handle re-login
- Expiration: Automatic logout after 24 hours

---

## **User Data in Database**

When a user logs in, their data is stored:

```sql
SELECT * FROM users WHERE clerk_id = 'user_...';

-- Columns:
id           → Database user ID
clerk_id     → Clerk user ID
email        → Email address
full_name    → User's full name
avatar_url   → Profile picture URL
created_at   → Account creation date
updated_at   → Last update
```

---

## **Clerk Dashboard**

Monitor users and authentication:
- https://dashboard.clerk.com
- View: Users, sessions, authentication methods
- Manage: API keys, security settings, webhooks

---

## **API Endpoints**

### **Authentication Endpoints**
```
POST /auth/login
  Body: { "clerk_token": "eyJ..." }
  Response: { "session_token": "...", "user": {...} }

POST /auth/logout
  Headers: Authorization: Bearer {session_token}
  Response: { "message": "Logged out successfully" }

GET /auth/me
  Headers: Authorization: Bearer {session_token}
  Response: { "user": {...} }
```

### **All Protected Endpoints**
```
All /api/* endpoints require:
  Headers: Authorization: Bearer {session_token}

Example:
GET /api/status
  Headers: Authorization: Bearer {session_token}
  Response: { "app": "...", "version": "...", ... }
```

---

## **Troubleshooting**

### **"Invalid Clerk token"**
- Verify token is from correct Clerk instance
- Check secret key matches
- Ensure token hasn't expired
- Try getting a fresh token

### **"Unauthorized" on protected endpoint**
- Verify session token in Authorization header
- Check token hasn't expired (24-hour lifetime)
- Try logging in again to get fresh token
- Verify token is session token, not Clerk token

### **User not created in database**
- Check database connection
- Verify user table exists
- Look at backend logs for SQL errors
- Try logging in again

### **Frontend not authenticating**
- Verify Clerk publishable key in environment
- Check CORS_ORIGINS includes frontend URL
- Verify Clerk session is created in browser
- Check browser console for Clerk errors

---

## **Security Best Practices**

✅ **Implemented**
- JWT tokens with expiration
- HS256 signing algorithm
- Automatic logout after 24 hours
- Password hashing (Clerk handles)
- CORS protection
- API key validation

✅ **Next Steps**
- Implement token refresh mechanism
- Add brute-force protection
- Monitor authentication attempts
- Implement audit logging
- Regular secret rotation

---

## **Next: Complete Deployment**

Your stack is now:
- ✅ Supabase (Database)
- ✅ Upstash Redis (Cache)
- ✅ Clerk (Authentication)
- ⏳ Render (Backend) - Ready to deploy
- ⏳ Vercel (Frontend) - Ready to update

**You're 3/5 services complete!**

**Continue with DEPLOY_WITH_SUPABASE.md steps 3-7**

---

## **Cost**

```
Supabase:  $0/month (500MB free)
Upstash:   $0/month (10k cmd/day free)
Clerk:     $0/month (free plan)
Render:    $0/month (free tier)
Vercel:    $0/month (unlimited)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total:     $0/month ✅
```

---

You're almost there! 🚀
