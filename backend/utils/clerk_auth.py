"""Verify Clerk session tokens and fetch the profile behind them.

Deliberately not the Clerk Python SDK - the surface used here is two calls
("verify a JWT against a JWKS", "GET one user by id"), both a handful of lines
with PyJWT + requests. Pulling in a 0.1.0 SDK for that is a bigger, less
predictable dependency than writing it.

The Frontend API domain (and with it the JWKS URL) is derived from the
publishable key rather than configured separately: a Clerk publishable key is
`pk_<env>_<base64>`, and the base64 segment decodes to `<domain>$`. Deriving it
removes one more place the two keys could drift out of sync.
"""

import base64
import time
from functools import lru_cache
from typing import Optional

import jwt
import requests
from jwt import PyJWKClient

from backend.utils.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger("social_media_automation.clerk")

CLERK_API_BASE = "https://api.clerk.com/v1"

# How long a verified-but-stale JWKS is trusted before a refetch. Clerk
# rotates signing keys rarely; this just bounds how long a rotation takes to
# propagate here, not a security boundary (PyJWKClient still matches by kid).
_JWKS_CACHE_SECONDS = 3600


class ClerkVerificationError(Exception):
    """A token failed verification, or Clerk could not be reached."""


def _frontend_api_domain(publishable_key: str) -> str:
    try:
        _, _, encoded = publishable_key.split("_", 2)
        padding = "=" * (-len(encoded) % 4)
        decoded = base64.b64decode(encoded + padding).decode("utf-8")
        return decoded.rstrip("$")
    except (ValueError, UnicodeDecodeError) as e:
        raise ClerkVerificationError(
            f"VITE_CLERK_PUBLISHABLE_KEY is malformed: {e}"
        ) from e


@lru_cache(maxsize=4)
def _jwks_client_for(publishable_key: str, _epoch: int) -> PyJWKClient:
    """Cached per publishable key AND a time bucket, so it expires without a
    process restart. `_epoch` is just cache-busting input, not read otherwise.
    """
    domain = _frontend_api_domain(publishable_key)
    return PyJWKClient(
        f"https://{domain}/.well-known/jwks.json",
        cache_keys=True,
        lifespan=_JWKS_CACHE_SECONDS,
    )


def _jwks_client() -> PyJWKClient:
    key = get_settings().clerk_publishable_key
    if not key:
        raise ClerkVerificationError("VITE_CLERK_PUBLISHABLE_KEY is not configured")
    epoch = int(time.time()) // _JWKS_CACHE_SECONDS
    return _jwks_client_for(key, epoch)


def verify_session_token(token: str) -> str:
    """Verify a Clerk session JWT. Returns the `sub` (Clerk user id).

    Raises ClerkVerificationError on anything that does not verify: wrong
    signature, wrong issuer, expired, not-yet-valid, or malformed. Callers
    must not treat a caught exception as "guest" - it means "reject the
    request", the same way an unverified LinkedIn token would.
    """
    if not token:
        raise ClerkVerificationError("empty token")

    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            # Clerk session tokens carry `azp`/`sub` but not always a fixed
            # `aud` matching the publishable key, and issuer is what actually
            # ties the token to this Clerk instance - checked explicitly below
            # instead of via the `audience` option.
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as e:
        raise ClerkVerificationError(f"token did not verify: {e}") from e

    domain = _frontend_api_domain(get_settings().clerk_publishable_key)
    expected_issuer = f"https://{domain}"
    if claims.get("iss") != expected_issuer:
        raise ClerkVerificationError(
            f"unexpected issuer {claims.get('iss')!r}, expected {expected_issuer!r}"
        )

    subject = claims.get("sub")
    if not subject:
        raise ClerkVerificationError("token has no subject claim")

    return subject


def fetch_user_profile(clerk_user_id: str) -> dict:
    """The account's email/name/avatar/public_metadata, from Clerk itself.

    Fetched via the Backend API with the secret key rather than trusted from
    the session token's own claims: a default Clerk session token carries only
    `sub` unless a custom JWT template is configured in the dashboard, and
    `public_metadata` - which decides admin status - must never be read from
    anything the client could have influenced.
    """
    settings = get_settings()
    if not settings.clerk_secret_key:
        raise ClerkVerificationError("CLERK_SECRET_KEY is not configured")

    try:
        response = requests.get(
            f"{CLERK_API_BASE}/users/{clerk_user_id}",
            headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
            timeout=15,
        )
    except requests.RequestException as e:
        raise ClerkVerificationError(f"could not reach Clerk: {e}") from e

    if response.status_code >= 400:
        raise ClerkVerificationError(
            f"Clerk user lookup failed ({response.status_code}): {response.text[:200]}"
        )

    data = response.json()
    primary_email = None
    primary_id = data.get("primary_email_address_id")
    for entry in data.get("email_addresses") or []:
        if entry.get("id") == primary_id:
            primary_email = entry.get("email_address")
            break
    if primary_email is None and data.get("email_addresses"):
        primary_email = data["email_addresses"][0].get("email_address")

    name = " ".join(
        part for part in [data.get("first_name"), data.get("last_name")] if part
    ) or None

    return {
        "email": primary_email,
        "name": name,
        "avatar_url": data.get("image_url"),
        "public_metadata": data.get("public_metadata") or {},
    }


def verify_and_fetch(token: str) -> tuple[str, dict]:
    """Verify a session token and return (clerk_user_id, profile)."""
    subject = verify_session_token(token)
    profile = fetch_user_profile(subject)
    return subject, profile
