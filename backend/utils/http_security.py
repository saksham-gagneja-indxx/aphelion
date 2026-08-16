"""Transport-level hardening: CORS validation, response headers, rate limits.

Three findings from the security review live here, kept together because they
are all "things every response or request passes through" rather than anything
a single endpoint owns.

Rate limiting is in-process on purpose. This app already pins itself to
**exactly one gunicorn worker** — APScheduler runs in-process and a second
worker would double-publish every scheduled post (see the Dockerfile). Given
one process, a dict is an accurate limiter and Redis would be a dependency,
a network hop and an operational surface bought for nothing. If the worker
count ever changes, this becomes per-worker and must move to shared storage;
that is written on the limiter itself so it is not discovered the hard way.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Iterable, List, Tuple

from flask import jsonify, request

from backend.utils.logger import get_logger

logger = get_logger("social_media_automation.http_security")


# --------------------------------------------------------------------- CORS

# Origins that must never be trusted by a production deployment. A developer
# origin in a production allowlist means any process bound to that port on a
# user's machine can make credentialed calls against live data.
_DEV_ORIGIN_MARKERS = ("localhost", "127.0.0.1", "0.0.0.0", "[::1]")


def validate_cors_origins(raw: str, is_production: bool) -> Tuple[List[str], List[str]]:
    """Parse CORS_ORIGINS into (allowed, problems).

    A wildcard is dropped rather than passed through. Combined with
    `supports_credentials=True` it would let any site a signed-in user visits
    drive this API with their token attached, which is the single worst CORS
    configuration available.
    """
    problems: List[str] = []
    allowed: List[str] = []

    for origin in (o.strip() for o in (raw or "").split(",")):
        if not origin:
            continue
        if origin == "*":
            problems.append(
                "CORS_ORIGINS contains '*'. Refused: with credentials enabled "
                "that lets any website drive this API as a signed-in user."
            )
            continue
        if is_production and any(m in origin for m in _DEV_ORIGIN_MARKERS):
            problems.append(
                f"CORS_ORIGINS contains the development origin '{origin}' in a "
                "production deployment. Refused: any process bound to that port "
                "on a user's machine could call this API with their credentials."
            )
            continue
        allowed.append(origin)

    return allowed, problems


# ----------------------------------------------------------------- headers

# The one remote origin the frontend genuinely needs. Kept as a named constant
# so that if the fonts move, the CSP and the test that guards it change
# together instead of drifting apart.
FONT_STYLESHEET_ORIGIN = "https://api.fontshare.com"

# Clerk serves its own client script from the instance's accounts.dev
# subdomain, which is per-instance and could change if the app moves - a
# wildcard here (rather than hardcoding noble-glowworm-144) survives that.
CLERK_SCRIPT_ORIGIN = "https://*.clerk.accounts.dev"


def security_headers(is_production: bool) -> Dict[str, str]:
    """Headers attached to every response.

    The API serves JSON and, in the single-image deployment, the SPA. The CSP
    below is written for that SPA:

    * `script-src 'self'` plus Clerk's own script host - Clerk's React SDK
      loads its actual client (`clerk-js`) from a `<script src>` pointed at
      the Clerk instance's own accounts.dev subdomain, not bundled by Vite.
      Without this the script is silently blocked and sign-in never loads at
      all (`failed_to_load_clerk_js_timeout`) - found live, in production,
      because local dev never sends this header at all (only this Flask path
      and vercel.json do), so it passed every check that ran against the dev
      server. No inline script, no general CDN allowance otherwise.
    * `style-src` allows inline: the app sets a handful of computed styles
      (gradients, grid backdrops) as style attributes, and 'unsafe-inline' for
      styles alone does not enable script execution. It also names Fontshare
      explicitly - index.css does `@import url(https://api.fontshare.com/...)`
      and that survives the Vite build, so a CSP without it serves the whole
      app in fallback system fonts. Silent, and it only shows up in the deploy
      that serves the SPA from Flask.
    * `connect-src` has to include https: because the API origin is
      configurable per deployment (VITE_API_URL) and is not known at build
      time.
    * `frame-ancestors 'none'` is the header that actually stops clickjacking;
      X-Frame-Options is kept for older browsers that ignore CSP.

    This matters more here than in a typical app: the session token lives in
    localStorage, so an XSS is a full account takeover. CSP is the control
    that makes injected script unable to run in the first place.
    """
    csp = "; ".join([
        "default-src 'self'",
        f"script-src 'self' {CLERK_SCRIPT_ORIGIN}",
        f"style-src 'self' 'unsafe-inline' {FONT_STYLESHEET_ORIGIN}",
        "img-src 'self' data: https:",
        # Fonts are inert content, so an https: wildcard here buys convenience
        # at close to no risk - unlike script-src, where it would be fatal.
        "font-src 'self' https: data:",
        "connect-src 'self' https:",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "object-src 'none'",
    ])

    headers = {
        "Content-Security-Policy": csp,
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        # Nothing here uses a camera, microphone or location. Denying them
        # outright means an injected iframe or script cannot ask either.
        # Every feature needs the `=()` form; a bare `payment()` is a syntax
        # error and browsers drop the whole header when they hit one.
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    }

    if is_production:
        # Only in production: sending HSTS from a local http:// dev server can
        # pin localhost to https in the browser and break every other project
        # served from the same host.
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return headers


# ------------------------------------------------------------- rate limiting

class SlidingWindowLimiter:
    """Fixed-cost in-process rate limiter.

    Correct only while the app runs as ONE process — which this one pins
    itself to for scheduler reasons. With multiple workers each would keep its
    own counters and the effective limit would multiply by the worker count.
    """

    def __init__(self) -> None:
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
        """Record a hit. Returns (allowed, seconds_until_retry)."""
        now = time.monotonic()
        cutoff = now - window_seconds

        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()

            if len(hits) >= limit:
                # Oldest hit in the window decides when a slot frees up.
                return False, max(1, int(hits[0] + window_seconds - now) + 1)

            hits.append(now)

            # Opportunistic cleanup: without it the dict grows one entry per
            # distinct client forever, which is its own slow memory leak.
            if len(self._hits) > 4096:
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]

            return True, 0


_limiter = SlidingWindowLimiter()


def client_key() -> str:
    """Who to count against.

    An authenticated caller is counted by user id, which cannot be spoofed and
    survives a changing IP. Everyone else falls back to the remote address.

    `remote_addr` behind a proxy is the proxy unless ProxyFix is configured.
    That makes anonymous limits coarser than intended rather than bypassable,
    which is the safe direction to be wrong in; the note is here so the
    trade-off is visible when a proxy is introduced.
    """
    from backend.utils.security import current_user

    user = current_user()
    if user is not None:
        return f"user:{user.id}"
    return f"ip:{request.remote_addr or 'unknown'}"


def enforce(rules: Iterable[Tuple[str, str, int, int]]):
    """before_request hook enforcing (method, path_prefix, limit, window).

    Returns a 429 with `Retry-After` — a number the client can act on beats a
    bare refusal.
    """
    def _hook():
        path = request.path.rstrip("/") or "/"
        for method, prefix, limit, window in rules:
            if request.method != method or not path.startswith(prefix):
                continue
            allowed, retry_after = _limiter.check(
                f"{method}:{prefix}:{client_key()}", limit, window
            )
            if not allowed:
                logger.warning(
                    f"Rate limit hit: {method} {path} by {client_key()} "
                    f"({limit} per {window}s)"
                )
                response = jsonify({
                    "error": "Too many requests. Slow down and try again.",
                    "retry_after_seconds": retry_after,
                })
                response.status_code = 429
                response.headers["Retry-After"] = str(retry_after)
                return response
            return None
        return None

    return _hook


def reset_limits() -> None:
    """Clear all counters. For tests."""
    with _limiter._lock:
        _limiter._hits.clear()
