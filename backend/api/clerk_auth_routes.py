"""
Authentication routes using Clerk as the identity provider.

Routes:
  POST /auth/login      - Verify Clerk token and create session
  POST /auth/logout     - Invalidate session
  GET  /auth/me         - Get current user profile
"""

from flask import Blueprint, request, jsonify, g
from backend.utils.database import get_session
from backend.models.user import User
from backend.utils.logger import get_logger
from backend.utils.security import current_user, api_key_configured
from functools import wraps
import jwt
from datetime import datetime, timedelta
from backend.utils.config import get_settings

logger = get_logger("clerk_auth")
clerk_auth_bp = Blueprint("clerk_auth", __name__, url_prefix="/auth")
settings = get_settings()


def verify_clerk_token(token: str) -> dict:
    """
    Verify Clerk JWT token.

    Args:
        token: Clerk JWT token from Authorization header

    Returns:
        Decoded token data (user_id, email, etc.)

    Raises:
        ValueError: If token is invalid
    """
    if not settings.clerk_secret_key:
        raise ValueError("CLERK_SECRET_KEY not configured")

    try:
        # Verify and decode Clerk JWT
        # Note: In production, verify signature using Clerk's public key
        decoded = jwt.decode(
            token,
            settings.clerk_secret_key,
            algorithms=["HS256"],
        )
        return decoded
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid Clerk token: {str(e)}")


def create_session_token(user_id: int) -> str:
    """
    Create a session token for the user.

    Args:
        user_id: User ID

    Returns:
        JWT session token
    """
    payload = {
        "user_id": user_id,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    return token


# ============================================================================
# Routes
# ============================================================================


@clerk_auth_bp.route("/login", methods=["POST"])
def login():
    """
    Login via Clerk token.

    Request:
        POST /auth/login
        {
          "clerk_token": "eyJhbGc..."
        }

    Response (200):
        {
          "session_token": "sess_xyz...",
          "user": {
            "id": 1,
            "email": "user@example.com",
            "full_name": "John Doe"
          }
        }

    Response (401):
        {
          "error": "Invalid Clerk token"
        }
    """
    data = request.get_json()
    clerk_token = data.get("clerk_token")

    if not clerk_token:
        return jsonify({"error": "Missing clerk_token"}), 400

    try:
        # Verify Clerk token
        clerk_data = verify_clerk_token(clerk_token)
        clerk_id = clerk_data.get("sub")  # Clerk user ID
        email = clerk_data.get("email")

        if not clerk_id or not email:
            return jsonify({"error": "Invalid Clerk token data"}), 401

        # Find or create user in database
        db = get_session()
        try:
            user = db.query(User).filter(User.clerk_id == clerk_id).first()

            if not user:
                # Create new user
                user = User(
                    clerk_id=clerk_id,
                    email=email,
                    full_name=clerk_data.get("name", ""),
                    is_active=True,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info(f"Created new user: {user.id} ({email})")

            # Create session token
            session_token = create_session_token(user.id)

            return jsonify({
                "session_token": session_token,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                }
            }), 200

        finally:
            db.close()

    except ValueError as e:
        logger.warning(f"Login failed: {str(e)}")
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@clerk_auth_bp.route("/logout", methods=["POST"])
def logout():
    """
    Logout and invalidate session.

    Request:
        POST /auth/logout
        Authorization: Bearer {session_token}

    Response (200):
        {
          "message": "Logged out successfully"
        }

    Response (401):
        {
          "error": "Unauthorized"
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    # Note: In a production system with stateful sessions,
    # add the token to a blacklist here. For now, token expiration
    # handles logout (24-hour expiry).

    return jsonify({"message": "Logged out successfully"}), 200


@clerk_auth_bp.route("/me", methods=["GET"])
def get_me():
    """
    Get current user profile.

    Request:
        GET /auth/me
        Authorization: Bearer {session_token}

    Response (200):
        {
          "user": {
            "id": 1,
            "email": "user@example.com",
            "full_name": "John Doe",
            "avatar_url": "https://...",
            "timezone": "America/New_York",
            "created_at": "2026-08-18T10:00:00Z"
          }
        }

    Response (401):
        {
          "error": "Unauthorized"
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    return jsonify({
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "avatar_url": user.avatar_url,
            "timezone": user.timezone,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
    }), 200
