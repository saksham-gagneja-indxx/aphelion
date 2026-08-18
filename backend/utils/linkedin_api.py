"""
LinkedIn API helper utilities.

Provides higher-level functions for LinkedIn API interactions:
- Token validation and refresh
- Profile verification
- Publishing helpers
"""

import logging
from datetime import datetime, timedelta
from backend.utils.encryption import decrypt_token
import requests

logger = logging.getLogger(__name__)


class LinkedInAPIError(Exception):
    """LinkedIn API error."""
    pass


def validate_access_token(access_token: str) -> bool:
    """
    Validate LinkedIn access token by making a simple API call.

    Args:
        access_token: LinkedIn access token

    Returns:
        True if token is valid, False otherwise
    """
    try:
        url = "https://api.linkedin.com/v2/me"
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.head(url, headers=headers, timeout=5)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Token validation failed: {str(e)}")
        return False


def get_person_urn(access_token: str) -> str:
    """
    Get the authenticated user's LinkedIn person URN.

    Args:
        access_token: LinkedIn access token

    Returns:
        Person URN (e.g., "urn:li:person:ABC123")

    Raises:
        LinkedInAPIError: If API call fails
    """
    try:
        url = "https://api.linkedin.com/v2/me"
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json().get("id")
    except requests.RequestException as e:
        raise LinkedInAPIError(f"Failed to get person URN: {str(e)}")


def check_publish_permissions(access_token: str) -> bool:
    """
    Check if the user has permission to publish content.

    LinkedIn permissions are granted during OAuth. This makes a test
    call to verify the w_member_social scope is present.

    Args:
        access_token: LinkedIn access token

    Returns:
        True if user can publish, False otherwise
    """
    try:
        # Try to fetch the UGC post schema - requires w_member_social scope
        url = "https://api.linkedin.com/v2/ugcPosts"
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(url, headers=headers, timeout=5)
        # 403 = no permission, 200 = has permission
        return response.status_code != 403
    except Exception as e:
        logger.warning(f"Permission check failed: {str(e)}")
        return False


def calculate_token_refresh_time(expires_in: int) -> datetime:
    """
    Calculate when a token should be refreshed.

    Refresh 1 hour before actual expiration to handle timing issues.

    Args:
        expires_in: Seconds until token expires

    Returns:
        Datetime when token should be refreshed
    """
    # Refresh 1 hour before expiration
    return datetime.utcnow() + timedelta(seconds=expires_in - 3600)


def format_api_error(response) -> str:
    """
    Format LinkedIn API error for logging.

    Args:
        response: requests.Response object

    Returns:
        Formatted error message
    """
    try:
        error_data = response.json()
        if isinstance(error_data, dict):
            message = error_data.get("message", "Unknown error")
            code = error_data.get("status", response.status_code)
            return f"LinkedIn API error ({code}): {message}"
    except:
        pass

    return f"LinkedIn API error ({response.status_code}): {response.text[:200]}"
