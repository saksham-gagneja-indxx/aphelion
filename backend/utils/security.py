"""API authentication and OAuth state signing.

Two separate concerns live here because they solve the same problem from
different directions: proving a request is allowed to act.

1. `require_api_key` - a global gate. Every /api/* route needs a bearer token
   except a small, explicit allowlist. It is enforced in a before_request hook
   rather than as a per-route decorator so that a newly added endpoint is
   protected by DEFAULT. Forgetting a decorator is silent; forgetting to add
   an exemption is loud.

2. Signed OAuth state - replaces server-side session storage for the CSRF
   `state` value. The state is an HMAC-signed, expiring token that carries the
   user_id, so the callback can verify it without a cookie.

   Why not the Flask session? The session is a browser cookie, which means the
   OAuth flow only works if the same browser both starts and finishes it. That
   breaks when the authorize URL is minted server-side, and it silently breaks
   again whenever cookies are blocked cross-site. Signing the state is
   stateless, survives restarts, and is strictly stronger: it binds the user_id
   into the signature, so a returned state cannot be replayed against a
   different account.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from functools import wraps
from typing import Optional, Tuple

from flask import g, jsonify, request

from backend.utils.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger("social_media_automation.security")

# Paths reachable without credentials. Keep this list short and justified -
# every entry is an endpoint the whole internet can reach.
PUBLIC_PATHS = {
    # Render's health probe cannot send custom headers.
    "/health",
    # LinkedIn redirects the member's browser here after consent. It cannot
    # carry a bearer token. It is protected instead by the signed `state`
    # parameter, which must verify before anything is written.
    "/api/auth/linkedin/callback",
    # Sign-in entry point. Necessarily public - it is what an anonymous
    # visitor clicks to authenticate. Reaching it grants nothing on its own:
    # new accounts are created INACTIVE and cannot use the API until an
    # administrator approves them.
    "/api/auth/linkedin/login",
    # Guest sign-in. Public for the same reason as the LinkedIn entry point:
    # it is what an unauthenticated visitor calls to get a session. What it
    # hands back is an ordinary, sandboxed account - it cannot publish and can
    # never be an administrator. See backend/api/guest_routes.py.
    "/api/auth/guest",
    "/api/auth/guest/status",
    # Clerk sign-in bridge. Necessarily public for the same reason as the
    # LinkedIn login entry point - the caller has no app session token yet.
    # It is protected instead by verifying the Clerk-issued JWT in the body
    # against Clerk's own JWKS before anything is looked up or created.
    "/api/auth/clerk/verify",
}

# How long a minted authorize URL stays valid. Long enough to click through a
# login and consent screen, short enough that a leaked URL is near-useless.
STATE_TTL_SECONDS = 600


def api_key_configured() -> bool:
    """True when an API access key is set."""
    key = get_settings().api_access_key
    return bool(key and not key.startswith("your_"))


def current_user():
    """The User for this request, or None for machine (API-key) callers.

    Resolved once per request and cached on `g`.
    """
    return getattr(g, "current_user", None)


def authenticate_request() -> Optional[tuple]:
    """Authenticate the request. Returns an error response, or None to allow.

    Two accepted credentials, both presented as a bearer token:

      * the API access key  - machine callers (scripts, the scheduler)
      * a signed session token - a human who signed in with LinkedIn

    Wired into a before_request hook, so anything under /api/ that is not on
    the explicit allowlist is protected without the endpoint doing anything.
    """
    path = request.path.rstrip("/") or "/"

    if path in PUBLIC_PATHS or not path.startswith("/api/"):
        return None

    # CORS preflight never carries an Authorization header.
    if request.method == "OPTIONS":
        return None

    if not api_key_configured():
        # Fail CLOSED. An unset key must not silently disable authentication -
        # that is how a "temporarily open for testing" deployment becomes a
        # permanently open one.
        logger.error("API_ACCESS_KEY is not configured; refusing all API requests")
        return jsonify({
            "error": "Server is misconfigured: API_ACCESS_KEY is not set. "
                     "No API requests can be served."
        }), 503

    provided = _extract_key(request)
    if not provided:
        return jsonify({"error": "Unauthorized. Sign in or provide an API key."}), 401

    # 1. Machine caller. Constant-time compare so response timing cannot be
    #    used to recover the key.
    if hmac.compare_digest(provided, get_settings().api_access_key):
        g.current_user = None
        g.is_machine = True
        return None

    # 2. Human caller with a session token.
    user_id = verify_session_token(provided)
    if user_id is None:
        logger.warning(f"Rejected request: {request.method} {request.path}")
        return jsonify({"error": "Unauthorized. Sign in or provide an API key."}), 401

    from backend.models.user import User
    from backend.utils.database import get_session

    db = get_session()
    try:
        user = db.query(User).filter(User.id == user_id).first()

        if user is None:
            return jsonify({"error": "Account no longer exists."}), 401

        # Checked on EVERY request, not just at login. A signed token cannot be
        # revoked before it expires, so this is what makes deactivating a user
        # take effect immediately.
        if not user.is_active:
            return jsonify({
                "error": "Your account is not active. An administrator must "
                         "approve it before you can use this tool."
            }), 403

        user.touch_last_seen()
        db.commit()

        # Detached copy: the session closes when this function returns, and a
        # bound instance would raise DetachedInstanceError on attribute access
        # inside the view.
        db.refresh(user)
        db.expunge(user)
        g.current_user = user
        g.is_machine = False
    finally:
        db.close()

    return None


def require_admin() -> Optional[tuple]:
    """Guard for admin-only endpoints. Returns an error response, or None.

    Machine callers holding the API key are treated as administrators: the key
    is already full-privilege, so refusing it here would protect nothing.

    A CORS preflight carries no Authorization header (same reason
    authenticate_request() skips it - see there), so current_user() is always
    None for one and this would otherwise 403 every OPTIONS request to an
    admin blueprint. Browsers treat a non-2xx preflight response as a failed
    CORS check regardless of what headers came with it, so that 403 doesn't
    read as "not an admin" - it reads as "CORS is broken here", on every
    admin/console request, from every origin, including ones that ARE
    correctly allowlisted. Found live: the admin and console pages on
    postpilot-sandy.vercel.app looked exactly like a missing-origin CORS bug
    from the browser console, and the actual allowlist was never the problem.
    """
    if request.method == "OPTIONS":
        return None

    if getattr(g, "is_machine", False):
        return None

    user = current_user()
    if user is None or not user.is_admin():
        return jsonify({"error": "Administrator access required."}), 403
    return None


def require_user_access(user_id) -> Optional[tuple]:
    """Guard for routes that act on one user's data. Returns an error, or None.

    Authentication only proves *who* is calling; it says nothing about whose
    records they asked for. Every user-scoped route takes the target user id
    from the client (path, body, form or query string), so without this check a
    signed-in operator can read and modify any other account's reels, posts and
    analytics by editing the number - the requests are perfectly authenticated.

    Machine callers and administrators are allowed through, matching
    require_admin(): the API key is already full-privilege, and the Admin page
    exists to inspect other accounts.
    """
    if getattr(g, "is_machine", False):
        return None

    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized. Sign in or provide an API key."}), 401

    if user.is_admin():
        return None

    # A non-numeric id cannot match anyone; treat it as a refusal rather than
    # letting int() raise a 500 and leak a stack trace.
    try:
        target = int(user_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid user id."}), 400

    if user.id != target:
        logger.warning(
            f"Refused cross-account access: user {user.id} -> user {target} "
            f"({request.method} {request.path})"
        )
        return jsonify({"error": "You can only access your own data."}), 403

    return None


# Backwards-compatible alias for the original hook name.
check_api_key = authenticate_request


def _extract_key(req) -> Optional[str]:
    """Read the key from Authorization: Bearer, or the X-API-Key header.

    Deliberately NOT read from the query string: URLs end up in server logs,
    browser history, and Referer headers.
    """
    auth = req.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return req.headers.get("X-API-Key")


def require_api_key(f):
    """Per-route decorator. The before_request hook is the real enforcement;
    this exists for routes registered outside the /api prefix."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        error = check_api_key()
        if error is not None:
            return error
        return f(*args, **kwargs)

    return wrapper


# --------------------------------------------------------------- OAuth state


def _sign(payload: bytes) -> str:
    secret = get_settings().secret_key.encode("utf-8")
    digest = hmac.new(secret, payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def make_session_token(user_id: int, days: int = 7) -> str:
    """Mint a signed session token for a logged-in user.

    Tokens rather than cookies because the SPA and the API are on different
    origins. A cross-site session cookie needs SameSite=None; Secure, which
    browsers are actively restricting as third-party cookies are phased out -
    a login that works today and silently breaks on a browser update is not
    worth shipping. A bearer token is unaffected by any of that.

    Stateless and signed, so there is no session store to keep or migrate. The
    trade-off is that a token cannot be revoked before it expires; `is_active`
    is checked on every request so a deactivated user is locked out
    immediately regardless.
    """
    payload = json.dumps(
        {
            "uid": user_id,
            "exp": int(time.time()) + days * 86400,
            "typ": "session",
            "nonce": secrets.token_urlsafe(8),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    return f"{_b64encode(payload)}.{_sign(payload)}"


def verify_session_token(token: Optional[str]) -> Optional[int]:
    """Return the user_id carried by a valid session token, else None."""
    if not token or "." not in token:
        return None

    encoded, signature = token.rsplit(".", 1)

    try:
        payload = _b64decode(encoded)
    except Exception:
        return None

    # Verify before parsing - never act on unauthenticated data.
    if not hmac.compare_digest(_sign(payload), signature):
        return None

    try:
        data = json.loads(payload)
    except ValueError:
        return None

    # Reject an OAuth state replayed as a session token: both are signed with
    # the same key, so the type claim is what keeps them from being confused.
    if data.get("typ") != "session":
        return None

    if int(data.get("exp", 0)) < int(time.time()):
        return None

    uid = data.get("uid")
    return uid if isinstance(uid, int) else None


def make_oauth_state(user_id: int) -> str:
    """Mint a signed, expiring state value bound to `user_id`."""
    payload = json.dumps(
        {
            "user_id": user_id,
            "exp": int(time.time()) + STATE_TTL_SECONDS,
            # Makes each state unique even for the same user in the same second,
            # so two concurrent attempts cannot collide.
            "nonce": secrets.token_urlsafe(16),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    return f"{_b64encode(payload)}.{_sign(payload)}"


def verify_oauth_state(state: Optional[str]) -> Tuple[Optional[int], str]:
    """Validate a state value. Returns (user_id, error_message).

    user_id is None when validation fails. The error message is for logs, not
    for the user - it can describe why a token was rejected.
    """
    if not state or "." not in state:
        return None, "missing or malformed state"

    encoded, signature = state.rsplit(".", 1)

    try:
        payload = _b64decode(encoded)
    except Exception:
        return None, "state is not decodable"

    # Verify BEFORE parsing: never act on unauthenticated data.
    if not hmac.compare_digest(_sign(payload), signature):
        return None, "state signature does not verify"

    try:
        data = json.loads(payload)
    except ValueError:
        return None, "state payload is not valid JSON"

    if int(data.get("exp", 0)) < int(time.time()):
        return None, "state has expired"

    user_id = data.get("user_id")
    if not isinstance(user_id, int):
        return None, "state carries no valid user_id"

    return user_id, ""
