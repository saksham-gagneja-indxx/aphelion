"""
LinkedIn publishing integration.

Handles uploading media and posting to LinkedIn using the LinkedIn API.
"""

import requests
import json
from backend.utils.logger import get_logger
from backend.models.media_file import MediaFile
from backend.utils.config import get_settings

logger = get_logger("linkedin_publisher")
settings = get_settings()

LINKEDIN_API_BASE = "https://api.linkedin.com/v2"


def publish_to_linkedin(
    access_token: str,
    caption: str,
    media_file: MediaFile = None,
    metadata: dict = None,
) -> dict:
    """
    Publish content to LinkedIn.

    Args:
        access_token: LinkedIn OAuth access token
        caption: Post caption text
        media_file: MediaFile object (if posting with media)
        metadata: Additional metadata (hashtags, mentions, etc.)

    Returns:
        {
            "post_id": "urn:li:share:1234567890",
            "url": "https://linkedin.com/feed/update/urn:li:share:1234567890/"
        }

    Raises:
        Exception: If publishing fails
    """
    if not metadata:
        metadata = {}

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Linkedin-Version": "202208",
    }

    try:
        if media_file and media_file.is_video():
            # Upload video and publish
            result = _publish_video(headers, caption, media_file, metadata)
        elif media_file and media_file.is_image():
            # Upload image and publish
            result = _publish_image(headers, caption, media_file, metadata)
        else:
            # Text-only post
            result = _publish_text(headers, caption, metadata)

        logger.info(f"LinkedIn publish succeeded: {result['post_id']}")
        return result

    except Exception as e:
        logger.error(f"LinkedIn publishing failed: {str(e)}")
        raise


def _publish_text(headers: dict, caption: str, metadata: dict) -> dict:
    """Publish text-only post to LinkedIn."""
    payload = {
        "author": metadata.get("person_urn", ""),
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": caption,
                },
                "shareMediaCategory": "NONE",
            }
        },
    }

    response = requests.post(
        f"{LINKEDIN_API_BASE}/ugcPosts",
        json=payload,
        headers=headers,
    )

    if response.status_code not in [200, 201]:
        error_detail = response.text
        try:
            error_detail = response.json().get("message", response.text)
        except:
            pass
        raise Exception(f"LinkedIn API error {response.status_code}: {error_detail}")

    result = response.json()
    return {
        "post_id": result.get("id"),
        "url": f"https://www.linkedin.com/feed/update/{result.get('id')}/",
    }


def _publish_image(headers: dict, caption: str, media_file: MediaFile, metadata: dict) -> dict:
    """Publish image post to LinkedIn."""
    # Step 1: Register image upload
    register_payload = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": metadata.get("person_urn", ""),
            "serviceRelationships": [
                {
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }
            ],
        }
    }

    register_response = requests.post(
        f"{LINKEDIN_API_BASE}/assets?action=registerUpload",
        json=register_payload,
        headers=headers,
    )

    if register_response.status_code != 200:
        raise Exception(
            f"Failed to register image upload: {register_response.status_code}"
        )

    register_result = register_response.json()
    upload_url = register_result["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
    asset_id = register_result["value"]["asset"]

    # Step 2: Upload image
    with open(media_file.storage_path, "rb") as f:
        upload_response = requests.put(
            upload_url,
            data=f.read(),
            headers={
                "Content-Type": media_file.mime_type,
            },
        )

    if upload_response.status_code not in [200, 201]:
        raise Exception(
            f"Failed to upload image: {upload_response.status_code}"
        )

    # Step 3: Create post with image
    publish_payload = {
        "author": metadata.get("person_urn", ""),
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": caption,
                },
                "shareMediaCategory": "IMAGE",
                "media": [
                    {
                        "status": "READY",
                        "media": asset_id,
                    }
                ],
            }
        },
    }

    publish_response = requests.post(
        f"{LINKEDIN_API_BASE}/ugcPosts",
        json=publish_payload,
        headers=headers,
    )

    if publish_response.status_code not in [200, 201]:
        raise Exception(
            f"Failed to publish image post: {publish_response.status_code}"
        )

    result = publish_response.json()
    return {
        "post_id": result.get("id"),
        "url": f"https://www.linkedin.com/feed/update/{result.get('id')}/",
    }


def _publish_video(headers: dict, caption: str, media_file: MediaFile, metadata: dict) -> dict:
    """Publish video post to LinkedIn."""
    # Step 1: Register video upload
    register_payload = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-video"],
            "owner": metadata.get("person_urn", ""),
            "serviceRelationships": [
                {
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }
            ],
        }
    }

    register_response = requests.post(
        f"{LINKEDIN_API_BASE}/assets?action=registerUpload",
        json=register_payload,
        headers=headers,
    )

    if register_response.status_code != 200:
        raise Exception(
            f"Failed to register video upload: {register_response.status_code}"
        )

    register_result = register_response.json()
    upload_url = register_result["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
    asset_id = register_result["value"]["asset"]

    # Step 2: Upload video
    with open(media_file.storage_path, "rb") as f:
        upload_response = requests.put(
            upload_url,
            data=f.read(),
            headers={
                "Content-Type": media_file.mime_type,
            },
        )

    if upload_response.status_code not in [200, 201]:
        raise Exception(
            f"Failed to upload video: {upload_response.status_code}"
        )

    # Step 3: Create post with video
    publish_payload = {
        "author": metadata.get("person_urn", ""),
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": caption,
                },
                "shareMediaCategory": "VIDEO",
                "media": [
                    {
                        "status": "READY",
                        "media": asset_id,
                    }
                ],
            }
        },
    }

    publish_response = requests.post(
        f"{LINKEDIN_API_BASE}/ugcPosts",
        json=publish_payload,
        headers=headers,
    )

    if publish_response.status_code not in [200, 201]:
        raise Exception(
            f"Failed to publish video post: {publish_response.status_code}"
        )

    result = publish_response.json()
    return {
        "post_id": result.get("id"),
        "url": f"https://www.linkedin.com/feed/update/{result.get('id')}/",
    }
