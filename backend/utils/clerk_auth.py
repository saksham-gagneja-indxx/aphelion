"""
Clerk authentication integration.

Verifies Clerk session JWTs against Clerk's own JWKS - not by trusting
whatever the caller claims a token's decoded claims are. Signature
verification is not optional here: skipping it (as an earlier version of
this module did, decoding with verify_signature=False on the theory that
"the frontend Clerk SDK already verified it") means anyone can POST a
structurally valid JWT with an arbitrary `sub` claim and be handed a
session for that Clerk account, including someone else's. The frontend SDK
verifying a token tells the frontend it's real; it tells this server
nothing, because nothing stops a caller from skipping the frontend
entirely and hitting this endpoint directly.

Note: verify_session_token here verifies an incoming CLERK token and
returns the clerk_id it names - a different job from
backend.utils.security.verify_session_token, which verifies THIS APP'S
OWN previously-issued session token and returns a user_id. The two are
unrelated functions that happen to share a name because each verifies
"the token in this request," for a different meaning of "this".
"""

import base64
from typing import Optional, Dict, Any, Tuple

import jwt
import requests
from jwt import PyJWKClient

from backend.utils.logger import get_logger

logger = get_logger("clerk_auth")

CLERK_API_ENDPOINT = "https://api.clerk.com/v1"

# Keyed by Frontend API domain. PyJWKClient itself caches the fetched keys,
# so this just avoids re-creating a client (and re-fetching the JWKS) on
# every single request.
_jwks_clients: Dict[str, PyJWKClient] = {}


def _frontend_api_domain() -> Optional[str]:
    """Recover the Clerk Frontend API domain from the publishable key.

    A Clerk publishable key is `pk_{env}_{base64(domain + "$")}` - decoding
    the base64 segment and dropping the trailing "$" gives the exact host
    that serves this instance's JWKS, with no separate config value that
    could drift out of sync with the real key.
    """
    from backend.utils.config import get_settings

    key = get_settings().clerk_publishable_key
    if not key or "_" not in key:
        return None
    try:
        encoded = key.rsplit("_", 1)[-1]
        padded = encoded + "=" * (-len(encoded) % 4)
        return base64.b64decode(padded).decode().rstrip("$")
    except Exception:
        return None


def _jwks_client() -> Optional[PyJWKClient]:
    domain = _frontend_api_domain()
    if not domain:
        return None
    if domain not in _jwks_clients:
        _jwks_clients[domain] = PyJWKClient(f"https://{domain}/.well-known/jwks.json")
    return _jwks_clients[domain]


def verify_session_token(token: str) -> Optional[str]:
    """Verify a Clerk-issued JWT's signature against Clerk's real JWKS.

    Returns the verified `sub` claim (the Clerk user id) only if the
    signature genuinely checks out against a public key Clerk itself
    published for this token's `kid`. Anything else - wrong key, expired
    token, malformed JWT, no publishable key configured to even locate the
    JWKS - returns None.
    """
    if not token:
        return None

    if token.startswith("Bearer "):
        token = token[7:]

    jwks_client = _jwks_client()
    if jwks_client is None:
        logger.error("Cannot verify Clerk token: VITE_CLERK_PUBLISHABLE_KEY is not configured")
        return None

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        logger.warning("Clerk token expired")
        return None
    except Exception as e:
        # Covers PyJWKClientError (unknown kid), InvalidSignatureError (the
        # forged-token case), and anything else - all of these mean "this
        # token did not verify," not "something crashed."
        logger.warning(f"Clerk token verification failed: {e}")
        return None

    clerk_id = decoded.get("sub")
    if not clerk_id:
        logger.warning("No 'sub' claim in Clerk token")
        return None

    logger.info(f"Clerk token verified for user: {clerk_id}")
    return clerk_id


def fetch_user_profile(clerk_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a user's profile from Clerk's Backend API.

    Returns the flat shape the rest of the sign-in path expects: email,
    name, avatar_url, public_metadata. None on any failure - a verified
    token whose profile can't be fetched is treated as a failed sign-in,
    not as a session with holes in it.
    """
    from backend.utils.config import get_settings

    secret_key = get_settings().clerk_secret_key
    if not secret_key:
        logger.error("CLERK_SECRET_KEY not configured")
        return None

    try:
        response = requests.get(
            f"{CLERK_API_ENDPOINT}/users/{clerk_id}",
            headers={
                "Authorization": f"Bearer {secret_key}",
                "Content-Type": "application/json",
            },
            timeout=5,
        )
    except requests.RequestException as e:
        logger.error(f"Clerk API error fetching user {clerk_id}: {e}")
        return None

    if response.status_code != 200:
        logger.warning(f"Failed to fetch Clerk user {clerk_id}: {response.status_code}")
        return None

    clerk_user = response.json()

    primary_email = next(
        (
            e["email_address"]
            for e in clerk_user.get("email_addresses", [])
            if e.get("id") == clerk_user.get("primary_email_address_id")
        ),
        None,
    )
    full_name = (
        f"{clerk_user.get('first_name') or ''} {clerk_user.get('last_name') or ''}".strip()
        or clerk_user.get("username")
        or None
    )

    return {
        "email": primary_email,
        "name": full_name,
        "avatar_url": clerk_user.get("image_url") or clerk_user.get("profile_image_url"),
        "public_metadata": clerk_user.get("public_metadata") or {},
    }


class ClerkVerificationError(Exception):
    """Raised when Clerk token verification fails."""

    pass


def verify_and_fetch(token: str) -> Tuple[str, Dict[str, Any]]:
    """Verify a Clerk JWT and fetch the profile behind it.

    Returns (clerk_id, profile). Raises ClerkVerificationError for any
    failure - invalid signature, missing claim, or a profile fetch that
    didn't succeed - so callers have one exception to catch rather than
    several None-checks to get right.
    """
    clerk_id = verify_session_token(token)
    if not clerk_id:
        raise ClerkVerificationError("Token verification failed")

    profile = fetch_user_profile(clerk_id)
    if not profile:
        raise ClerkVerificationError("Could not fetch user profile from Clerk")

    return clerk_id, profile
