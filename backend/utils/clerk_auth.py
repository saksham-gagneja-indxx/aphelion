"""
Clerk authentication integration.
Handles JWT verification and user session management.
"""

import os
import jwt
import json
import requests
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from backend.utils.logger import get_logger

logger = get_logger("clerk_auth")

CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")
CLERK_API_ENDPOINT = "https://api.clerk.com/v1"


def verify_clerk_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify Clerk JWT token.

    Args:
        token: Bearer token from Clerk

    Returns:
        Decoded token claims or None if invalid
    """
    if not CLERK_SECRET_KEY:
        logger.error("CLERK_SECRET_KEY not configured")
        return None

    if not token:
        return None

    try:
        # Remove "Bearer " prefix if present
        if token.startswith("Bearer "):
            token = token[7:]

        # Verify and decode JWT
        decoded = jwt.decode(
            token,
            CLERK_SECRET_KEY,
            algorithms=["HS256"],
            options={"verify_signature": True}
        )

        logger.info(f"Clerk token verified for user: {decoded.get('sub')}")
        return decoded

    except jwt.ExpiredSignatureError:
        logger.warning("Clerk token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid Clerk token: {e}")
        return None
    except Exception as e:
        logger.error(f"Clerk token verification failed: {e}")
        return None


def get_clerk_user(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get user details from Clerk API.

    Args:
        user_id: Clerk user ID (from token 'sub' claim)

    Returns:
        User details or None if not found
    """
    if not CLERK_SECRET_KEY:
        logger.error("CLERK_SECRET_KEY not configured")
        return None

    try:
        headers = {
            "Authorization": f"Bearer {CLERK_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        response = requests.get(
            f"{CLERK_API_ENDPOINT}/users/{user_id}",
            headers=headers,
            timeout=5
        )

        if response.status_code == 200:
            user = response.json()
            logger.info(f"Retrieved Clerk user: {user_id}")
            return user
        else:
            logger.warning(f"Failed to get Clerk user {user_id}: {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"Clerk API error: {e}")
        return None


def extract_user_info(clerk_user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract relevant user info from Clerk user object.

    Args:
        clerk_user: User object from Clerk API

    Returns:
        Extracted user info
    """
    primary_email = next(
        (email["email_address"] for email in clerk_user.get("email_addresses", [])
         if email.get("primary")),
        None
    )

    primary_phone = next(
        (phone["phone_number"] for phone in clerk_user.get("phone_numbers", [])
         if phone.get("primary")),
        None
    )

    return {
        "clerk_id": clerk_user.get("id"),
        "email": primary_email,
        "phone": primary_phone,
        "first_name": clerk_user.get("first_name"),
        "last_name": clerk_user.get("last_name"),
        "full_name": f"{clerk_user.get('first_name') or ''} {clerk_user.get('last_name') or ''}".strip(),
        "avatar_url": clerk_user.get("profile_image_url"),
        "username": clerk_user.get("username"),
        "created_at": clerk_user.get("created_at"),
    }


def create_session_token(user_id: int, clerk_id: str) -> str:
    """
    Create a session token for authenticated user.

    Args:
        user_id: Database user ID
        clerk_id: Clerk user ID

    Returns:
        JWT session token
    """
    if not os.getenv("SECRET_KEY"):
        raise ValueError("SECRET_KEY not configured")

    payload = {
        "user_id": user_id,
        "clerk_id": clerk_id,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=24),
    }

    token = jwt.encode(
        payload,
        os.getenv("SECRET_KEY"),
        algorithm="HS256"
    )

    logger.info(f"Session token created for user {user_id}")
    return token


def verify_session_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify application session token.

    Args:
        token: Session token

    Returns:
        Decoded token claims or None if invalid
    """
    if not os.getenv("SECRET_KEY"):
        logger.error("SECRET_KEY not configured")
        return None

    try:
        decoded = jwt.decode(
            token,
            os.getenv("SECRET_KEY"),
            algorithms=["HS256"]
        )
        return decoded

    except jwt.ExpiredSignatureError:
        logger.warning("Session token expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid session token")
        return None
    except Exception as e:
        logger.error(f"Session token verification failed: {e}")
        return None
