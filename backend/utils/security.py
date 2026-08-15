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

from flask import jsonify, request

from backend.utils.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger("social_media_automation.security")

# Paths reachable without an API key. Keep this list short and justified.
PUBLIC_PATHS = {
    # Render's health probe cannot send custom headers.
    "/health",
    # LinkedIn redirects the member's browser here after consent. It cannot
    # carry our bearer token. It is protected instead by the signed `state`
    # parameter, which must verify before anything is written.
    "/api/auth/linkedin/callback",
}

# How long a minted authorize URL stays valid. Long enough to click through a
# login and consent screen, short enough that a leaked URL is near-useless.
STATE_TTL_SECONDS = 600


def api_key_configured() -> bool:
    """True when an API access key is set."""
    key = get_settings().api_access_key
    return bool(key and not key.startswith("your_"))


def check_api_key() -> Optional[tuple]:
    """Enforce bearer-token auth. Returns an error response, or None to allow.

    Wired into a before_request hook. Returning None lets the request proceed.
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
    expected = get_settings().api_access_key

    # Constant-time compare so response timing cannot be used to guess the key.
    if not provided or not hmac.compare_digest(provided, expected):
        logger.warning(
            f"Rejected unauthenticated request: {request.method} {request.path}"
        )
        return jsonify({"error": "Unauthorized. Provide a valid API key."}), 401

    return None


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
