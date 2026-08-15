# Security

How this application authenticates callers, handles credentials, and what is
deliberately *not* protected yet. Read this before deploying anywhere that a
client account's data could reach.

---

## Threat model in one line

This service holds an OAuth token that can **publish publicly under a real
person's name**. The main thing worth protecting is the ability to use that
token.

---

## 1. API authentication

Every route under `/api/*` requires a bearer token.

```http
GET /api/status
Authorization: Bearer <API_ACCESS_KEY>
```

`X-API-Key: <key>` is accepted as an alternative.

### Design decisions

**Enforced globally, not per route.** The check runs in a Flask
`before_request` hook (`backend/app.py`), not as a decorator on each endpoint.
A new endpoint is therefore protected *by default*. Forgetting a decorator is
silent and dangerous; forgetting to add an exemption is loud and safe.

**Fails closed.** If `API_ACCESS_KEY` is unset, the app returns `503` for all
API requests rather than serving them openly. There is no "auth disabled"
mode — that is how a temporarily open deployment becomes a permanently open
one.

**Constant-time comparison.** Keys are compared with `hmac.compare_digest` so
response timing cannot be used to recover the key byte by byte.

**Never accepted in a query string.** Only headers are read. URLs end up in
server logs, browser history, and `Referer` headers sent to third parties.

### Public paths

Only two, each with a reason:

| Path | Why | What protects it instead |
|---|---|---|
| `/health` | Render's health probe cannot send custom headers | Exposes no data — status and DB reachability only |
| `/api/auth/linkedin/callback` | LinkedIn redirects the member's browser here; it cannot carry our token | The signed `state` parameter (below) |

---

## 2. OAuth CSRF protection — signed state

The `state` parameter is an HMAC-SHA256 signed, expiring token that carries the
`user_id`:

```
base64url(payload) . base64url(HMAC-SHA256(payload, SECRET_KEY))
payload = {"user_id": 1, "exp": <unix ts>, "nonce": <random>}
```

The callback verifies the signature **before parsing the payload** — it never
acts on unauthenticated data — then checks expiry, then extracts the `user_id`.

### Why signed rather than session-stored

The obvious implementation keeps a random `state` in the Flask session and
compares on return. That has real problems:

- It requires the same browser to both start and finish the flow. Minting an
  authorize URL server-side breaks it, as do blocked cross-site cookies.
- It is lost when the service restarts — on Render's free tier, that is often.
- It proves only "this browser started a flow." It does **not** bind the
  `user_id`, so a returned state could be replayed to attach an attacker's
  LinkedIn account to another user's record.

Signing solves all three. The `user_id` is inside the signature, so retargeting
the state at a different account invalidates it.

**Lifetime:** 10 minutes — long enough to log in and consent, short enough that
a leaked authorize URL is near-useless.

Tests: `tests/test_security.py` covers tampered `user_id`, forged signature,
expired state, and malformed input.

---

## 3. CORS

Restricted to origins listed in `CORS_ORIGINS` (comma-separated), defaulting to
`http://localhost:5173`.

Previously `*`. That let **any** website a user visited issue requests against
this API from their browser. Combined with no authentication, any page could
have driven the whole API.

---

## 4. Credential handling

### No passwords, ever

Publishing uses **OAuth 2.0** exclusively. The application never sees, stores,
or transmits a social account password.

`LINKEDIN_PASSWORD` was removed from the configuration entirely — not left
blank, removed — so nobody can helpfully fill it in later. LinkedIn's User
Agreement prohibits password-based automation, and holding a client's password
means holding access to their DMs, connections, and account settings, which is
a liability far beyond publishing.

`instagrapi` was removed for the same reason. It is a reverse-engineered client
that logs in with a username and password, violating Instagram's Terms of
Service and risking suspension of the account being posted to. See
`backend/core/publishers/instagram.py`.

### What is stored

| Item | Where | Notes |
|---|---|---|
| LinkedIn access token | `users.linkedin_access_token` | Expires ~60 days |
| LinkedIn refresh token | `users.linkedin_refresh_token` | Expires ~365 days |
| Person URN | `users.linkedin_person_urn` | Public identifier, not sensitive |

Tokens are scoped to `w_member_social` — publish only. They cannot read DMs or
change account settings.

`POST /api/auth/linkedin/disconnect` clears them locally. It does **not** revoke
the grant at LinkedIn; only the member can do that, from their own LinkedIn
settings. The API response says so explicitly rather than implying a full
revocation.

### Secrets in configuration

`.env` is gitignored and must never be committed. `data/instagram_sessions/` is
also gitignored — those files contain session identifiers, which are bearer
credentials granting full account access without a password or 2FA.

---

## 5. Upload safety

- `MAX_CONTENT_LENGTH` rejects oversized uploads at the transport layer, before
  the body is streamed to disk — a 413 in ~40ms instead of a full transfer.
- Filenames pass through `werkzeug.secure_filename`.
- Thumbnail serving resolves the path and confirms it stays inside the user's
  own directory, blocking `../` traversal.
- Extension and duration are validated per platform before anything is queued.

---

## 6. Known gaps — not yet addressed

Stated plainly, because an undocumented gap is worse than a known one.

| Gap | Impact | Notes |
|---|---|---|
| **Single shared API key** | No per-operator identity, no audit trail of who published what | Needs real user accounts. Recommended: LinkedIn OpenID Connect as the identity provider, reusing the OAuth integration already built |
| **Tokens stored in plaintext** | DB read = token compromise | Needs application-level encryption or a secrets manager |
| **No rate limiting** | Brute-force against the API key is unthrottled | 40-char random key makes this impractical, but throttling is still correct |
| **`user_id` is a client-supplied parameter** | Any authenticated caller can act as any user | Resolved once identity comes from a session rather than a query parameter |
| **Ephemeral storage on free tier** | Tokens and uploads lost on restart | Availability, not confidentiality. Needs a managed database |
| **No HTTPS enforcement locally** | Dev-only exposure | Render terminates TLS in production |

---

## 7. Deployment checklist

Before pointing this at any account you do not personally own:

- [ ] `API_ACCESS_KEY` set to a long random value (40+ chars)
- [ ] `SECRET_KEY` set to a distinct long random value — it signs OAuth state
- [ ] `DEBUG=false` — the Werkzeug debugger is remote code execution if exposed
- [ ] `CORS_ORIGINS` set to your real frontend origin, never `*`
- [ ] `LINKEDIN_REDIRECT_URI` matches the LinkedIn app entry exactly
- [ ] `.env` not committed (`git check-ignore .env` should print `.env`)
- [ ] Secrets rotated if they were ever pasted into a chat, ticket, or log
- [ ] Bind to `127.0.0.1` when running locally; `0.0.0.0` exposes the dev server
      to the whole network

---

## 8. Rotating credentials

**LinkedIn client secret:** LinkedIn app → Auth tab → *Generate a new Client
Secret* → update `LINKEDIN_CLIENT_SECRET` in `.env` and on the host.

**API access key:** generate with
`python -c "import secrets; print(secrets.token_urlsafe(40))"`, update
everywhere. All clients must be updated together — there is no key-rollover
window.

**Render API key:** Render dashboard → Account Settings → API Keys → revoke.
Note this key can modify and delete services; treat it as the most powerful
credential in the project and revoke it when not actively needed.
