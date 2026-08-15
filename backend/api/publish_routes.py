"""Immediate publish and retraction.

Separate from the scheduler: these act now, on request, rather than when a
trigger fires. Both paths go through the same Publisher, so there is one
implementation of "how do we post to LinkedIn" rather than two that can drift.

Ownership is enforced on every route. `user_id` is never taken from the
request - it comes from the authenticated session - so one operator cannot
publish or delete another's posts by guessing an id.
"""

from pathlib import Path

from flask import Blueprint, jsonify, request

from backend.models.audit import record as audit
from backend.models.post import Post, PostStatus
from backend.models.user import User
from backend.core.publishers import UnknownPlatformError, get_publisher
from backend.utils.database import get_session
from backend.utils.logger import get_logger
from backend.utils.security import current_user

logger = get_logger("social_media_automation.publish")

publish_bp = Blueprint("publish", __name__, url_prefix="/api/posts")


@publish_bp.before_request
def block_guests():
    """A guest may not publish or retract.

    Publishing acts on a real LinkedIn profile, and a guest has not proved they
    own one. Enforced blueprint-wide rather than per route, for the same reason
    the admin guard is: a route added later is covered by default instead of
    covered only if someone remembers.
    """
    user = current_user()
    if user is not None and user.is_guest_account():
        return jsonify({
            "error": "Guest accounts cannot publish to LinkedIn. "
                     "Sign in with LinkedIn to post."
        }), 403
    return None


def _load_owned_post(db, post_id: int):
    """Fetch a post the caller is allowed to act on.

    Returns (post, user, error_response). Machine callers holding the API key
    may act on any post - the key is already full-privilege - but a human
    session is restricted to its own.
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None:
        return None, None, (jsonify({"error": "Post not found"}), 404)

    actor = current_user()

    if actor is None:
        # Machine caller: act as the post's owner.
        owner = db.query(User).filter(User.id == post.user_id).first()
        if owner is None:
            return None, None, (jsonify({"error": "Post has no owner"}), 409)
        return post, owner, None

    if post.user_id != actor.id:
        # 404 rather than 403: confirming the post exists would let a caller
        # enumerate other users' post ids.
        logger.warning(
            f"User {actor.id} attempted to access post {post_id} owned by {post.user_id}"
        )
        return None, None, (jsonify({"error": "Post not found"}), 404)

    return post, actor, None


@publish_bp.route("/<int:post_id>/publish", methods=["POST"])
def publish_now(post_id: int):
    """Publish a post immediately, bypassing its schedule."""
    db = get_session()
    try:
        post, owner, error = _load_owned_post(db, post_id)
        if error:
            return error

        if post.status == PostStatus.POSTED:
            return jsonify({
                "error": "This post has already been published.",
                "url": post.video_url,
            }), 409

        video_path = Path(post.video_path)
        if not video_path.exists():
            post.mark_as_failed(f"Video file is missing: {post.video_path}")
            db.commit()
            return jsonify({"error": f"Video file not found: {post.video_path}"}), 404

        platform = post.platform or "linkedin"
        try:
            publisher = get_publisher(owner, platform)
        except UnknownPlatformError as e:
            return jsonify({"error": str(e)}), 400

        if not publisher.is_connected():
            status = publisher.connection_status()
            return jsonify({
                "error": status.get("reason")
                or f"{platform} is not connected. Authorize it from Settings."
            }), 409

        logger.info(f"📤 Publishing post {post_id} to {platform} on request")
        result = publisher.publish(
            video_path=video_path,
            caption=post.caption or "",
            thumbnail_path=Path(post.thumbnail_path) if post.thumbnail_path else None,
        )

        if result.success:
            post.mark_as_posted(result.platform_post_id, platform=platform)
            post.video_url = result.url
            audit(
                db,
                action="post.published",
                actor=owner,
                target=f"post:{post.id}",
                detail=f"{platform} {result.platform_post_id}",
                ip_address=request.remote_addr,
            )
            db.commit()
            db.refresh(post)
            return jsonify({
                "message": "Published successfully",
                "post": post.to_dict(),
                "url": result.url,
                "platform_post_id": result.platform_post_id,
            }), 200

        post.mark_as_failed(result.error or "Publishing failed")
        audit(
            db,
            action="post.publish_failed",
            actor=owner,
            target=f"post:{post.id}",
            detail=(result.error or "")[:400],
            ip_address=request.remote_addr,
        )
        db.commit()
        # 502: the failure came from the upstream platform, not from this
        # request being malformed.
        return jsonify({
            "error": result.error,
            "retryable": result.retryable,
        }), 502
    finally:
        db.close()


@publish_bp.route("/<int:post_id>/published", methods=["DELETE"])
def delete_published(post_id: int):
    """Retract a published post from the platform.

    The local Post row is kept and marked cancelled rather than deleted, so
    the audit trail still shows that it was published and then withdrawn.
    """
    db = get_session()
    try:
        post, owner, error = _load_owned_post(db, post_id)
        if error:
            return error

        platform_post_id = post.linkedin_post_id or post.instagram_post_id
        if not platform_post_id:
            return jsonify({
                "error": "This post has not been published, so there is "
                         "nothing to delete."
            }), 409

        platform = post.platform or "linkedin"
        try:
            publisher = get_publisher(owner, platform)
        except UnknownPlatformError as e:
            return jsonify({"error": str(e)}), 400

        ok, err = publisher.delete(platform_post_id)
        if not ok:
            return jsonify({"error": err}), 502

        post.mark_as_cancelled()
        post.video_url = None
        audit(
            db,
            action="post.deleted",
            actor=owner,
            target=f"post:{post.id}",
            detail=f"{platform} {platform_post_id}",
            ip_address=request.remote_addr,
        )
        db.commit()
        db.refresh(post)

        return jsonify({
            "message": f"Deleted from {platform}",
            "post": post.to_dict(),
        }), 200
    finally:
        db.close()
