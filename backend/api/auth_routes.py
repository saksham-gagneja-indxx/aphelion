"""LinkedIn OAuth 2.0 (three-legged) authorization.

The member authorizes this app in their browser and LinkedIn hands back a code
that we exchange for a bearer token. We never see or store their password.

Flow:
    GET  /api/auth/linkedin/start?user_id=1  -> 302 to LinkedIn's consent screen
    GET  /api/auth/linkedin/callback         -> exchange code, store token, 302 to UI
    GET  /api/auth/linkedin/status?user_id=1 -> connection state for the UI
    POST /api/auth/linkedin/disconnect       -> forget the token locally

Scopes requested:
    openid, profile   - identifies the member so we can build their person URN
    w_member_social   - publish on their behalf; self-serve via the
                        "Share on LinkedIn" product, no partner review

The `state` parameter is required, not decorative: without it this endpoint
would accept a callback forged by any site the member visits, letting an
attacker bind their own LinkedIn account to our user record. It is generated
per attempt, kept in the signed Flask session, and compared on return.
"""

import secrets
from datetime import timedelta
from urllib.parse import urlencode

import requests
from flask import Blueprint, jsonify, redirect, request, session

from backend.models.user import User
from backend.utils.config import get_settings, linkedin_configured
from backend.utils.database import get_session
from backend.utils.logger import get_logger
from backend.utils.timeutil import utcnow

logger = get_logger("social_media_automation.auth")

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

SCOPES = "openid profile w_member_social"

_STATE_KEY = "linkedin_oauth_state"
_USER_KEY = "linkedin_oauth_user_id"

def _settings_url(status: str) -> str:
    """Where to send the browser once the dance finishes.

    Built per-request from config rather than a module constant: the frontend
    origin differs between local dev and the deployed environment, and baking
    in localhost would strand every deployed user on a dead redirect.
    """
    base = get_settings().frontend_url.rstrip("/")
    return f"{base}/settings?linkedin={status}"


@auth_bp.route("/linkedin/start", methods=["GET"])
def linkedin_start():
    """Kick off authorization by redirecting to LinkedIn's consent screen."""
    if not linkedin_configured():
        return jsonify({
            "error": "LinkedIn app is not configured. Set LINKEDIN_CLIENT_ID and "
                     "LINKEDIN_CLIENT_SECRET in .env."
        }), 503

    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    settings = get_settings()
    state = secrets.token_urlsafe(32)
    session[_STATE_KEY] = state
    session[_USER_KEY] = user_id

    params = {
        "response_type": "code",
        "client_id": settings.linkedin_client_id,
        "redirect_uri": settings.linkedin_redirect_uri,
        "state": state,
        "scope": SCOPES,
    }
    logger.info(f"Starting LinkedIn OAuth for user {user_id}")
    return redirect(f"{AUTHORIZE_URL}?{urlencode(params)}")


@auth_bp.route("/linkedin/callback", methods=["GET"])
def linkedin_callback():
    """Handle LinkedIn's redirect back: verify state, exchange code, store token."""
    # LinkedIn reports user-declined consent here rather than as an HTTP error.
    error = request.args.get("error")
    if error:
        description = request.args.get("error_description", "")
        logger.warning(f"LinkedIn authorization denied: {error} {description}")
        return redirect(_settings_url("denied"))

    state = request.args.get("state")
    expected_state = session.pop(_STATE_KEY, None)
    user_id = session.pop(_USER_KEY, None)

    # Constant-time compare; a mismatch means a forged or replayed callback.
    if not expected_state or not state or not secrets.compare_digest(state, expected_state):
        logger.warning("LinkedIn callback rejected: state mismatch")
        return redirect(_settings_url("state_mismatch"))

    code = request.args.get("code")
    if not code or not user_id:
        return redirect(_settings_url("missing_code"))

    settings = get_settings()

    try:
        token_response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.linkedin_client_id,
                "client_secret": settings.linkedin_client_secret,
                "redirect_uri": settings.linkedin_redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        if token_response.status_code >= 400:
            logger.error(
                f"LinkedIn token exchange failed "
                f"({token_response.status_code}): {token_response.text[:300]}"
            )
            return redirect(_settings_url("token_failed"))

        token = token_response.json()
        access_token = token.get("access_token")
        if not access_token:
            return redirect(_settings_url("token_failed"))

        # OpenID Connect userinfo gives us `sub`, the member id behind the
        # person URN that every publish call needs as its author.
        userinfo_response = requests.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        if userinfo_response.status_code >= 400:
            logger.error(
                f"LinkedIn userinfo failed "
                f"({userinfo_response.status_code}): {userinfo_response.text[:300]}"
            )
            return redirect(_settings_url("userinfo_failed"))

        userinfo = userinfo_response.json()
        member_id = userinfo.get("sub")
        if not member_id:
            return redirect(_settings_url("userinfo_failed"))

        expires_at = None
        if token.get("expires_in"):
            expires_at = utcnow() + timedelta(seconds=int(token["expires_in"]))

        db = get_session()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return redirect(_settings_url("no_user"))

            user.store_linkedin_token(
                access_token=access_token,
                person_urn=f"urn:li:person:{member_id}",
                expires_at=expires_at,
                refresh_token=token.get("refresh_token"),
            )
            if userinfo.get("email"):
                user.linkedin_email = userinfo["email"]
            db.commit()
        finally:
            db.close()

        logger.info(f"✅ LinkedIn connected for user {user_id} ({userinfo.get('name')})")
        return redirect(_settings_url("connected"))

    except requests.RequestException as e:
        logger.error(f"LinkedIn OAuth network failure: {e}")
        return redirect(_settings_url("network_error"))


@auth_bp.route("/linkedin/status", methods=["GET"])
def linkedin_status():
    """Report connection state so the Settings page can render honestly."""
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    db = get_session()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        expires_at = user.linkedin_token_expires_at
        return jsonify({
            "app_configured": linkedin_configured(),
            "connected": user.linkedin_token_valid(),
            "person_urn": user.linkedin_person_urn,
            "email": user.linkedin_email,
            "token_expires_at": expires_at.isoformat() if expires_at else None,
            # A token that exists but has lapsed is a distinct state from never
            # having connected, and needs a different message in the UI.
            "token_expired": bool(
                user.linkedin_access_token and not user.linkedin_token_valid()
            ),
        }), 200
    finally:
        db.close()


@auth_bp.route("/linkedin/disconnect", methods=["POST"])
def linkedin_disconnect():
    """Forget the stored token.

    Local only - it does not revoke the grant on LinkedIn's side. The member
    revokes that from their own LinkedIn settings, which is the only place that
    can actually do it.
    """
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    db = get_session()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        user.clear_linkedin_token()
        db.commit()
        logger.info(f"LinkedIn disconnected for user {user_id}")
        return jsonify({
            "message": "LinkedIn disconnected locally. To fully revoke access, "
                       "remove the app from your LinkedIn account settings.",
            "connected": False,
        }), 200
    finally:
        db.close()
