"""
LinkedIn OAuth and credential management routes.

Routes:
  POST /api/linkedin/connect        - Initiate LinkedIn OAuth flow
  GET  /api/linkedin/callback       - LinkedIn OAuth redirect (from LinkedIn)
  POST /api/linkedin/callback       - LinkedIn OAuth callback (handles auth code from frontend)
  GET  /api/linkedin/status         - Check LinkedIn connection status
  POST /api/linkedin/disconnect     - Revoke LinkedIn connection
  POST /api/linkedin/refresh-token  - Manually refresh LinkedIn token
"""

from flask import Blueprint, request, jsonify, g, url_for, redirect
from backend.utils.database import get_session
from backend.models.user import User
from backend.models.linkedin_credential import LinkedInCredential
from backend.utils.logger import get_logger
from backend.utils.security import current_user
from backend.utils.encryption import encrypt_token, decrypt_token
from backend.utils.config import get_settings
from datetime import datetime, timedelta
from urllib.parse import quote
import requests
import secrets
import logging

logger = get_logger("linkedin")
linkedin_bp = Blueprint("linkedin", __name__, url_prefix="/api/linkedin")
settings = get_settings()


class LinkedInError(Exception):
    """LinkedIn API error."""
    pass


def get_linkedin_oauth_url(state: str) -> str:
    """
    Generate LinkedIn OAuth authorization URL.

    Args:
        state: CSRF protection state token

    Returns:
        LinkedIn OAuth authorization URL
    """
    params = {
        "response_type": "code",
        "client_id": settings.linkedin_client_id,
        "redirect_uri": settings.linkedin_redirect_uri,
        "state": state,
        "scope": "openid profile email w_member_social",  # Scopes for sign-in and publishing
    }

    base_url = "https://www.linkedin.com/oauth/v2/authorization"
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{base_url}?{query_string}"


def exchange_code_for_token(code: str, state: str) -> dict:
    """
    Exchange authorization code for access token.

    Args:
        code: Authorization code from LinkedIn
        state: CSRF protection state token (for validation)

    Returns:
        Token response with access_token, refresh_token, expires_in, etc.

    Raises:
        LinkedInError: If token exchange fails
    """
    if not settings.linkedin_client_id or not settings.linkedin_client_secret:
        raise LinkedInError("LinkedIn credentials not configured")

    token_url = "https://www.linkedin.com/oauth/v2/accessToken"

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.linkedin_redirect_uri,
        "client_id": settings.linkedin_client_id,
        "client_secret": settings.linkedin_client_secret,
    }

    try:
        response = requests.post(token_url, data=data, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"LinkedIn token exchange failed: {str(e)}")
        raise LinkedInError(f"Failed to exchange code for token: {str(e)}")


def get_linkedin_profile(access_token: str) -> dict:
    """
    Fetch LinkedIn user profile information.

    Args:
        access_token: LinkedIn access token

    Returns:
        User profile data with id, name, email, picture, etc.

    Raises:
        LinkedInError: If profile fetch fails
    """
    profile_url = "https://api.linkedin.com/v2/me?projection=(id,firstName,lastName,profilePicture(displayImage))"
    email_url = "https://api.linkedin.com/v2/emailAddress?q=primary&projection=(elements*)"

    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        # Get profile
        profile_response = requests.get(profile_url, headers=headers, timeout=10)
        profile_response.raise_for_status()
        profile = profile_response.json()

        # Get email
        email_response = requests.get(email_url, headers=headers, timeout=10)
        email_response.raise_for_status()
        email_data = email_response.json()

        email = None
        if email_data.get("elements"):
            email = email_data["elements"][0].get("handle~", {}).get("emailAddress")

        # Extract person URN (e.g., "urn:li:person:ABC123")
        person_urn = profile.get("id")

        # Extract name
        first_name = profile.get("firstName", {}).get("localized", {}).get("en_US", "")
        last_name = profile.get("lastName", {}).get("localized", {}).get("en_US", "")
        full_name = f"{first_name} {last_name}".strip()

        return {
            "person_urn": person_urn,
            "full_name": full_name,
            "email": email,
            "profile_picture_url": profile.get("profilePicture", {}).get("displayImage"),
        }
    except requests.RequestException as e:
        logger.error(f"LinkedIn profile fetch failed: {str(e)}")
        raise LinkedInError(f"Failed to fetch profile: {str(e)}")


# ============================================================================
# Routes
# ============================================================================


@linkedin_bp.route("/connect", methods=["POST"])
def initiate_linkedin_connection():
    """
    Initiate LinkedIn OAuth flow.

    Request:
        POST /api/linkedin/connect
        Authorization: Bearer {session_token}

    Response (200):
        {
          "oauth_url": "https://www.linkedin.com/oauth/v2/authorization?...",
          "state": "state_xyz..."
        }

    Response (401):
        {
          "error": "Unauthorized"
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    if not settings.linkedin_client_id:
        return jsonify({"error": "LinkedIn is not configured"}), 503

    # Generate state token for CSRF protection
    state = secrets.token_urlsafe(32)

    # In production, store state in Redis or database with TTL
    # For now, we'll validate it in the callback
    # TODO: Store state in cache with expiration (5 minutes)

    oauth_url = get_linkedin_oauth_url(state)

    return jsonify({
        "oauth_url": oauth_url,
        "state": state,
    }), 200


@linkedin_bp.route("/callback", methods=["GET"])
def linkedin_oauth_callback_get():
    """
    Handle LinkedIn OAuth redirect (GET from LinkedIn).
    LinkedIn redirects to this endpoint with code and state as query params.
    """
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")

    if error:
        logger.warning(f"LinkedIn OAuth error: {error}")
        return redirect(f"{get_settings().frontend_url}/?linkedin=denied")

    if not code or not state:
        logger.warning("Missing code or state in LinkedIn callback")
        return redirect(f"{get_settings().frontend_url}/?linkedin=missing_code")

    # Redirect to frontend with code and state so it can POST to /callback
    return redirect(
        f"{get_settings().frontend_url}/?linkedin=authorize"
        f"&code={quote(code)}&state={quote(state)}"
    )


@linkedin_bp.route("/callback", methods=["POST"])
def linkedin_oauth_callback():
    """
    Handle LinkedIn OAuth callback.

    Request:
        POST /api/linkedin/callback
        {
          "code": "auth_code_from_linkedin",
          "state": "state_xyz..."
        }

    Response (200):
        {
          "success": true,
          "credential_id": 5,
          "linkedin_account": "John Doe",
          "person_urn": "urn:li:person:ABC123"
        }

    Response (400/401):
        {
          "error": "Invalid OAuth code"
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    code = data.get("code")
    state = data.get("state")

    if not code or not state:
        return jsonify({"error": "Missing code or state"}), 400

    try:
        # Exchange code for access token
        token_response = exchange_code_for_token(code, state)

        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token")
        expires_in = token_response.get("expires_in", 3600)

        if not access_token:
            return jsonify({"error": "No access token in response"}), 401

        # Fetch user profile
        profile = get_linkedin_profile(access_token)

        # Calculate token expiration
        token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        # Save credentials to database
        db = get_session()
        try:
            # Check if user already has LinkedIn credentials
            cred = db.query(LinkedInCredential).filter(
                LinkedInCredential.user_id == user.id
            ).first()

            if cred:
                # Update existing credentials
                cred.access_token_encrypted = encrypt_token(access_token)
                cred.refresh_token_encrypted = encrypt_token(refresh_token) if refresh_token else cred.refresh_token_encrypted
                cred.linkedin_person_urn = profile["person_urn"]
                cred.linkedin_account_name = profile["full_name"]
                cred.token_expires_at = token_expires_at
                cred.mark_verified()
            else:
                # Create new credentials
                cred = LinkedInCredential(
                    user_id=user.id,
                    access_token_encrypted=encrypt_token(access_token),
                    refresh_token_encrypted=encrypt_token(refresh_token) if refresh_token else None,
                    linkedin_person_urn=profile["person_urn"],
                    linkedin_account_name=profile["full_name"],
                    token_expires_at=token_expires_at,
                    is_connected=True,
                )
                db.add(cred)

            db.commit()
            logger.info(f"LinkedIn connected for user {user.id}: {profile['full_name']}")

            return jsonify({
                "success": True,
                "credential_id": cred.id,
                "linkedin_account": profile["full_name"],
                "person_urn": profile["person_urn"],
            }), 200

        finally:
            db.close()

    except LinkedInError as e:
        logger.error(f"LinkedIn connection failed: {str(e)}")
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        logger.error(f"LinkedIn callback error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@linkedin_bp.route("/status", methods=["GET"])
def get_linkedin_status():
    """
    Check LinkedIn connection status.

    Request:
        GET /api/linkedin/status
        Authorization: Bearer {session_token}

    Response (200, connected):
        {
          "is_connected": true,
          "account_name": "John Doe",
          "person_urn": "urn:li:person:ABC123",
          "connected_at": "2026-08-18T10:00:00Z",
          "token_expires_at": "2026-09-18T10:00:00Z"
        }

    Response (200, not connected):
        {
          "is_connected": false
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    db = get_session()
    try:
        cred = db.query(LinkedInCredential).filter(
            LinkedInCredential.user_id == user.id
        ).first()

        if not cred or not cred.is_connected:
            return jsonify({"is_connected": False}), 200

        return jsonify({
            "is_connected": True,
            "account_name": cred.linkedin_account_name,
            "person_urn": cred.linkedin_person_urn,
            "connected_at": cred.created_at.isoformat() if cred.created_at else None,
            "token_expires_at": cred.token_expires_at.isoformat() if cred.token_expires_at else None,
            "token_needs_refresh": cred.should_refresh(),
        }), 200

    finally:
        db.close()


@linkedin_bp.route("/disconnect", methods=["POST"])
def disconnect_linkedin():
    """
    Revoke LinkedIn connection.

    Request:
        POST /api/linkedin/disconnect
        Authorization: Bearer {session_token}

    Response (200):
        {
          "message": "LinkedIn disconnected"
        }

    Response (409):
        {
          "error": "Not connected"
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    db = get_session()
    try:
        cred = db.query(LinkedInCredential).filter(
            LinkedInCredential.user_id == user.id
        ).first()

        if not cred or not cred.is_connected:
            return jsonify({"error": "Not connected"}), 409

        cred.disconnect()
        db.commit()

        logger.info(f"LinkedIn disconnected for user {user.id}")

        return jsonify({"message": "LinkedIn disconnected"}), 200

    finally:
        db.close()


@linkedin_bp.route("/refresh-token", methods=["POST"])
def refresh_linkedin_token():
    """
    Manually refresh LinkedIn access token.

    Request:
        POST /api/linkedin/refresh-token
        Authorization: Bearer {session_token}

    Response (200):
        {
          "expires_at": "2026-09-18T10:00:00Z",
          "message": "Token refreshed"
        }

    Response (401):
        {
          "error": "LinkedIn connection required"
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    db = get_session()
    try:
        cred = db.query(LinkedInCredential).filter(
            LinkedInCredential.user_id == user.id
        ).first()

        if not cred or not cred.is_connected or not cred.refresh_token_encrypted:
            return jsonify({"error": "LinkedIn connection required"}), 401

        # Decrypt refresh token
        refresh_token = decrypt_token(cred.refresh_token_encrypted)

        # Exchange refresh token for new access token
        token_url = "https://www.linkedin.com/oauth/v2/accessToken"

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.linkedin_client_id,
            "client_secret": settings.linkedin_client_secret,
        }

        try:
            response = requests.post(token_url, data=data, timeout=10)
            response.raise_for_status()
            token_response = response.json()

            new_access_token = token_response.get("access_token")
            expires_in = token_response.get("expires_in", 3600)

            if new_access_token:
                # Update credentials
                cred.access_token_encrypted = encrypt_token(new_access_token)
                cred.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                cred.mark_refreshed(cred.token_expires_at)
                db.commit()

                logger.info(f"LinkedIn token refreshed for user {user.id}")

                return jsonify({
                    "expires_at": cred.token_expires_at.isoformat(),
                    "message": "Token refreshed",
                }), 200
            else:
                return jsonify({"error": "Failed to get new token"}), 401

        except requests.RequestException as e:
            logger.error(f"Token refresh failed: {str(e)}")
            return jsonify({"error": "Failed to refresh token"}), 500

    finally:
        db.close()
