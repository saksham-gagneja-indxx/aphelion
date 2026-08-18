"""
Post creation, publishing, and scheduling routes.

Routes:
  POST   /api/posts                - Create draft post
  POST   /api/posts/{id}/schedule  - Schedule post for later
  GET    /api/posts                - List user's posts
  GET    /api/posts/{id}           - Get post details
  DELETE /api/posts/{id}           - Delete draft post

The publish route that used to live here was a legacy, MediaFile/
LinkedInCredential-based implementation that only ever ran by accident: it
registers on the same "/<int:post_id>/publish" path as the current,
reel/User-based implementation in publish_routes.py, and blueprint
registration order in app.py happened to let this one shadow that one.
Because it required a human session via current_user() and rejected the
machine API-key callers the MCP server and other automation use, every
publish attempt through those paths failed with a bare "Unauthorized"
before ever reaching the real LinkedIn integration. Removed rather than
reordered, to match create/schedule above, which already resolve to the
current implementation for the same reason.
"""

from flask import Blueprint, request, jsonify
from backend.utils.database import get_session
from backend.models.post import Post, PostStatus
from backend.models.media_file import MediaFile
from backend.models.linkedin_credential import LinkedInCredential
from backend.utils.logger import get_logger
from backend.utils.security import current_user
from datetime import datetime, timedelta
import json

logger = get_logger("posts")
post_bp = Blueprint("posts", __name__, url_prefix="/api/posts")


# ============================================================================
# Routes
# ============================================================================


@post_bp.route("", methods=["POST"])
def create_post():
    """
    Create a draft post.

    Request:
        POST /api/posts
        Authorization: Bearer {session_token}
        {
          "media_id": 42,
          "caption": "Just shipped something amazing...",
          "platforms": ["linkedin"],
          "metadata": {"hashtags": "#AI #Tech", "mention_urls": [...]}
        }

    Response (201):
        {
          "id": 123,
          "status": "draft",
          "media_id": 42,
          "caption": "Just shipped something amazing...",
          "platforms": ["linkedin"],
          "created_at": "2026-08-18T10:00:00Z",
          "scheduled_time": null
        }

    Response (400):
        {
          "error": "media_id required"
        }

    Response (401):
        {
          "error": "Unauthorized"
        }

    Response (404):
        {
          "error": "Media file not found"
        }

    Response (409):
        {
          "error": "LinkedIn credentials not configured"
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    media_id = data.get("media_id")
    caption = data.get("caption", "")
    platforms = data.get("platforms", ["linkedin"])
    metadata = data.get("metadata", {})

    if not media_id:
        return jsonify({"error": "media_id required"}), 400

    if not caption:
        return jsonify({"error": "caption required"}), 400

    if not platforms:
        return jsonify({"error": "platforms required"}), 400

    db = get_session()
    try:
        # Verify media file exists and belongs to user
        media = db.query(MediaFile).filter(
            MediaFile.id == media_id,
            MediaFile.user_id == user.id,
            MediaFile.is_deleted == False,
        ).first()

        if not media:
            return jsonify({"error": "Media file not found"}), 404

        # Check LinkedIn credentials for linkedin platform
        if "linkedin" in platforms:
            linkedin_cred = db.query(LinkedInCredential).filter(
                LinkedInCredential.user_id == user.id,
                LinkedInCredential.is_connected == True,
            ).first()

            if not linkedin_cred:
                return jsonify({"error": "LinkedIn credentials not configured"}), 409

            # Verify token hasn't expired
            if linkedin_cred.is_token_expired():
                return jsonify({
                    "error": "LinkedIn token expired - please reconnect"
                }), 409

        # Create post
        post = Post(
            user_id=user.id,
            media_file_id=media_id,
            caption=caption,
            platform=",".join(platforms),  # Store as comma-separated
            status=PostStatus.DRAFT,
            post_metadata=metadata or {},
        )

        db.add(post)
        db.commit()
        db.refresh(post)

        logger.info(f"Post created: {post.id} (draft) by user {user.id}")

        return jsonify({
            "id": post.id,
            "status": post.status,
            "media_id": post.media_file_id,
            "caption": post.caption,
            "platforms": platforms,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "scheduled_time": None,
        }), 201

    finally:
        db.close()


@post_bp.route("/<int:post_id>/schedule", methods=["POST"])
def schedule_post(post_id: int):
    """
    Schedule a draft post for publishing at a specific time.

    Request:
        POST /api/posts/123/schedule
        Authorization: Bearer {session_token}
        {
          "scheduled_time": "2026-08-20T14:30:00Z"
        }

    Response (200):
        {
          "id": 123,
          "status": "scheduled",
          "scheduled_time": "2026-08-20T14:30:00Z"
        }

    Response (400):
        {
          "error": "scheduled_time in the past"
        }

    Response (401):
        {
          "error": "Unauthorized"
        }

    Response (404):
        {
          "error": "Post not found"
        }

    Response (409):
        {
          "error": "Post not in draft status"
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    scheduled_time_str = data.get("scheduled_time")

    if not scheduled_time_str:
        return jsonify({"error": "scheduled_time required"}), 400

    try:
        scheduled_time = datetime.fromisoformat(scheduled_time_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return jsonify({"error": "Invalid scheduled_time format (use ISO 8601)"}), 400

    # Check if scheduled time is in the future
    from backend.utils.timeutil import utcnow
    if scheduled_time <= utcnow():
        return jsonify({"error": "scheduled_time must be in the future"}), 400

    db = get_session()
    try:
        post = db.query(Post).filter(
            Post.id == post_id,
            Post.user_id == user.id,
        ).first()

        if not post:
            return jsonify({"error": "Post not found"}), 404

        if post.status != PostStatus.DRAFT:
            return jsonify({
                "error": f"Post not in draft status (current: {post.status})"
            }), 409

        # Get LinkedIn credentials
        linkedin_cred = db.query(LinkedInCredential).filter(
            LinkedInCredential.user_id == user.id,
            LinkedInCredential.is_connected == True,
        ).first()

        if not linkedin_cred:
            return jsonify({"error": "LinkedIn credentials not configured"}), 409

        # Update post
        post.status = PostStatus.SCHEDULED
        post.scheduled_time = scheduled_time
        db.commit()
        db.refresh(post)

        # Schedule the job (handled by scheduler)
        logger.info(f"Post scheduled: {post.id} for {scheduled_time} by user {user.id}")

        return jsonify({
            "id": post.id,
            "status": post.status,
            "scheduled_time": post.scheduled_time.isoformat() if post.scheduled_time else None,
        }), 200

    finally:
        db.close()


@post_bp.route("", methods=["GET"])
def list_posts():
    """
    List user's posts with filters.

    Request:
        GET /api/posts?status=draft&platform=linkedin&limit=20&offset=0
        Authorization: Bearer {session_token}

    Response (200):
        {
          "total": 42,
          "items": [
            {
              "id": 123,
              "status": "draft",
              "media_id": 42,
              "caption": "Just shipped something amazing...",
              "platforms": ["linkedin"],
              "views": 150,
              "likes": 23,
              "created_at": "2026-08-18T10:00:00Z",
              "scheduled_time": null
            },
            ...
          ]
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    status = request.args.get("status")
    platform = request.args.get("platform")
    limit = min(int(request.args.get("limit", 20)), 100)
    offset = int(request.args.get("offset", 0))

    db = get_session()
    try:
        query = db.query(Post).filter(Post.user_id == user.id)

        # Filter by status
        if status:
            query = query.filter(Post.status == status)

        # Filter by platform
        if platform:
            query = query.filter(Post.platform.contains(platform))

        # Get total count
        total = query.count()

        # Get paginated items
        items = query.order_by(Post.created_at.desc()).limit(limit).offset(offset).all()

        return jsonify({
            "total": total,
            "items": [
                {
                    "id": p.id,
                    "status": p.status,
                    "media_id": p.media_file_id,
                    "caption": p.caption,
                    "platforms": p.platform.split(",") if p.platform else [],
                    "views": p.views,
                    "likes": p.likes,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "scheduled_time": p.scheduled_time.isoformat() if p.scheduled_time else None,
                }
                for p in items
            ]
        }), 200

    finally:
        db.close()


@post_bp.route("/<int:post_id>", methods=["GET"])
def get_post(post_id: int):
    """
    Get post details.

    Request:
        GET /api/posts/123
        Authorization: Bearer {session_token}

    Response (200):
        {
          "id": 123,
          "status": "draft",
          "media_id": 42,
          "caption": "Just shipped something amazing...",
          "platforms": ["linkedin"],
          "views": 150,
          "likes": 23,
          "comments": 5,
          "shares": 2,
          "engagement_rate": 18.7,
          "created_at": "2026-08-18T10:00:00Z",
          "scheduled_time": null,
          "posted_at": null,
          "linkedin_post_id": null
        }

    Response (404):
        {
          "error": "Post not found"
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    db = get_session()
    try:
        post = db.query(Post).filter(
            Post.id == post_id,
            Post.user_id == user.id,
        ).first()

        if not post:
            return jsonify({"error": "Post not found"}), 404

        return jsonify({
            "id": post.id,
            "status": post.status,
            "media_id": post.media_file_id,
            "caption": post.caption,
            "platforms": post.platform.split(",") if post.platform else [],
            "views": post.views,
            "likes": post.likes,
            "comments": post.comments,
            "shares": post.shares,
            "engagement_rate": post.engagement_rate,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "scheduled_time": post.scheduled_time.isoformat() if post.scheduled_time else None,
            "posted_at": post.posted_at.isoformat() if post.posted_at else None,
            "linkedin_post_id": post.linkedin_post_id,
        }), 200

    finally:
        db.close()


@post_bp.route("/<int:post_id>", methods=["DELETE"])
def delete_post(post_id: int):
    """
    Delete a draft post.

    Request:
        DELETE /api/posts/123
        Authorization: Bearer {session_token}

    Response (200):
        {
          "message": "Post deleted"
        }

    Response (401):
        {
          "error": "Unauthorized"
        }

    Response (404):
        {
          "error": "Post not found"
        }

    Response (409):
        {
          "error": "Cannot delete published post"
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    db = get_session()
    try:
        post = db.query(Post).filter(
            Post.id == post_id,
            Post.user_id == user.id,
        ).first()

        if not post:
            return jsonify({"error": "Post not found"}), 404

        if post.status not in [PostStatus.DRAFT, PostStatus.FAILED]:
            return jsonify({
                "error": f"Cannot delete {post.status} post"
            }), 409

        db.delete(post)
        db.commit()

        logger.info(f"Post deleted: {post_id} by user {user.id}")

        return jsonify({"message": "Post deleted"}), 200

    finally:
        db.close()
