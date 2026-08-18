"""
Post scheduling and optimal timing routes.

Routes:
  GET    /api/scheduler/optimal-times  - Get optimal posting times
  POST   /api/scheduler/reschedule     - Reschedule a post
  GET    /api/scheduler/jobs           - List scheduled jobs
  DELETE /api/scheduler/jobs/{id}      - Cancel a scheduled job
  POST   /api/scheduler/execute-now    - Execute a scheduled post immediately
"""

from flask import Blueprint, request, jsonify
from backend.utils.database import get_session
from backend.models.post import Post, PostStatus
from backend.utils.logger import get_logger
from backend.utils.security import current_user
from backend.core.optimal_timing import OptimalTimingCalculator
from backend.core.scheduler import get_scheduler
from datetime import datetime, timedelta
import json

logger = get_logger("scheduler")
scheduler_bp = Blueprint("scheduler", __name__, url_prefix="/api/scheduler")


# ============================================================================
# Routes
# ============================================================================


@scheduler_bp.route("/optimal-times", methods=["GET"])
def get_optimal_times():
    """
    Get optimal posting times for the user.

    Request:
        GET /api/scheduler/optimal-times?days_ahead=7&top_n=5
        Authorization: Bearer {session_token}

    Response (200):
        {
          "slots": [
            {
              "datetime": "2026-08-20T10:00:00Z",
              "score": 0.765,
              "day_of_week": "Tue",
              "hour": 10
            },
            {
              "datetime": "2026-08-21T09:00:00Z",
              "score": 0.747,
              "day_of_week": "Wed",
              "hour": 9
            },
            ...
          ],
          "recommendation": "Tuesday 10 AM has the highest engagement score (0.765)"
        }

    Response (401):
        {
          "error": "Unauthorized"
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    days_ahead = int(request.args.get("days_ahead", 7))
    top_n = int(request.args.get("top_n", 5))

    # Validate ranges
    days_ahead = max(1, min(days_ahead, 90))  # 1-90 days
    top_n = max(1, min(top_n, 20))  # 1-20 results

    try:
        # Get user's historical analytics (optional)
        db = get_session()
        try:
            # For now, use default analytics
            # In production, would fetch from user's actual post history
            user_analytics = None

            slots = OptimalTimingCalculator.get_all_optimal_slots(
                user_analytics=user_analytics,
                days_ahead=days_ahead,
                top_n=top_n,
            )

            # Format response
            formatted_slots = [
                {
                    "datetime": slot["datetime"].isoformat(),
                    "score": round(slot["score"], 3),
                    "day_of_week": slot["day_of_week"],
                    "hour": slot["hour"],
                }
                for slot in slots
            ]

            best_slot = slots[0] if slots else None
            recommendation = (
                f"{best_slot['day_of_week']} {best_slot['hour']:02d}:00 "
                f"has the highest engagement score ({best_slot['score']:.3f})"
                if best_slot
                else "Unable to calculate optimal time"
            )

            logger.info(f"Optimal times calculated for user {user.id}")

            return jsonify({
                "slots": formatted_slots,
                "recommendation": recommendation,
            }), 200

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Failed to calculate optimal times: {str(e)}")
        return jsonify({"error": "Unable to calculate optimal times"}), 503


@scheduler_bp.route("/reschedule", methods=["POST"])
def reschedule_post():
    """
    Reschedule a scheduled post to a new time.

    Request:
        POST /api/scheduler/reschedule
        Authorization: Bearer {session_token}
        {
          "post_id": 123,
          "new_time": "2026-08-22T10:00:00Z"
        }

    Response (200):
        {
          "id": 123,
          "status": "scheduled",
          "scheduled_time": "2026-08-22T10:00:00Z"
        }

    Response (400):
        {
          "error": "Invalid scheduled time"
        }

    Response (404):
        {
          "error": "Post not found"
        }

    Response (409):
        {
          "error": "Post not in scheduled status"
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    post_id = data.get("post_id")
    new_time_str = data.get("new_time")

    if not post_id or not new_time_str:
        return jsonify({"error": "post_id and new_time required"}), 400

    try:
        new_time = datetime.fromisoformat(new_time_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return jsonify({"error": "Invalid new_time format (use ISO 8601)"}), 400

    from backend.utils.timeutil import utcnow

    if new_time <= utcnow():
        return jsonify({"error": "new_time must be in the future"}), 400

    db = get_session()
    try:
        post = db.query(Post).filter(
            Post.id == post_id,
            Post.user_id == user.id,
        ).first()

        if not post:
            return jsonify({"error": "Post not found"}), 404

        if post.status != PostStatus.SCHEDULED:
            return jsonify({
                "error": f"Post not in scheduled status (current: {post.status})"
            }), 409

        # Update scheduled time
        post.scheduled_time = new_time
        db.commit()
        db.refresh(post)

        logger.info(f"Post {post_id} rescheduled to {new_time} by user {user.id}")

        return jsonify({
            "id": post.id,
            "status": post.status,
            "scheduled_time": post.scheduled_time.isoformat() if post.scheduled_time else None,
        }), 200

    finally:
        db.close()


@scheduler_bp.route("/jobs", methods=["GET"])
def list_scheduled_jobs():
    """
    List all scheduled jobs for the user.

    Request:
        GET /api/scheduler/jobs
        Authorization: Bearer {session_token}

    Response (200):
        {
          "total": 5,
          "jobs": [
            {
              "job_id": "post-123",
              "post_id": 123,
              "scheduled_time": "2026-08-20T10:00:00Z",
              "status": "scheduled",
              "next_run_time": "2026-08-20T10:00:00Z"
            },
            ...
          ]
        }

    Response (401):
        {
          "error": "Unauthorized"
        }

    Response (503):
        {
          "error": "Scheduler unavailable"
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    db = get_session()
    try:
        # Get all scheduled posts for user
        posts = db.query(Post).filter(
            Post.user_id == user.id,
            Post.status == PostStatus.SCHEDULED,
        ).all()

        jobs = [
            {
                "job_id": post.job_id or f"post-{post.id}",
                "post_id": post.id,
                "scheduled_time": post.scheduled_time.isoformat() if post.scheduled_time else None,
                "status": post.status,
                "caption_preview": post.caption[:50] + "..." if post.caption and len(post.caption) > 50 else post.caption,
            }
            for post in posts
        ]

        logger.info(f"Listed {len(jobs)} scheduled jobs for user {user.id}")

        return jsonify({
            "total": len(jobs),
            "jobs": jobs,
        }), 200

    finally:
        db.close()


@scheduler_bp.route("/jobs/<job_id>", methods=["DELETE"])
def cancel_scheduled_job(job_id: str):
    """
    Cancel a scheduled job.

    Request:
        DELETE /api/scheduler/jobs/post-123
        Authorization: Bearer {session_token}

    Response (200):
        {
          "message": "Job cancelled",
          "post_id": 123
        }

    Response (404):
        {
          "error": "Job not found"
        }

    Response (409):
        {
          "error": "Job already executed"
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    db = get_session()
    try:
        # Extract post_id from job_id (format: "post-123")
        try:
            post_id = int(job_id.split("-")[-1])
        except (ValueError, IndexError):
            return jsonify({"error": "Invalid job_id format"}), 400

        post = db.query(Post).filter(
            Post.id == post_id,
            Post.user_id == user.id,
        ).first()

        if not post:
            return jsonify({"error": "Job not found"}), 404

        if post.status != PostStatus.SCHEDULED:
            return jsonify({
                "error": f"Cannot cancel {post.status} job"
            }), 409

        # Mark as cancelled
        post.status = PostStatus.CANCELLED
        db.commit()

        logger.info(f"Job {job_id} cancelled by user {user.id}")

        return jsonify({
            "message": "Job cancelled",
            "post_id": post.id,
        }), 200

    finally:
        db.close()


@scheduler_bp.route("/jobs/<job_id>/execute-now", methods=["POST"])
def execute_job_now(job_id: str):
    """
    Execute a scheduled job immediately.

    Request:
        POST /api/scheduler/jobs/post-123/execute-now
        Authorization: Bearer {session_token}

    Response (200):
        {
          "message": "Post published",
          "post_id": 123,
          "linkedin_post_id": "urn:li:share:1234567890"
        }

    Response (404):
        {
          "error": "Job not found"
        }

    Response (409):
        {
          "error": "Post not in scheduled status"
        }

    Response (503):
        {
          "error": "Publishing service unavailable"
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    db = get_session()
    try:
        # Extract post_id from job_id
        try:
            post_id = int(job_id.split("-")[-1])
        except (ValueError, IndexError):
            return jsonify({"error": "Invalid job_id format"}), 400

        post = db.query(Post).filter(
            Post.id == post_id,
            Post.user_id == user.id,
        ).first()

        if not post:
            return jsonify({"error": "Job not found"}), 404

        if post.status != PostStatus.SCHEDULED:
            return jsonify({
                "error": f"Post not in scheduled status (current: {post.status})"
            }), 409

        try:
            # Import here to avoid circular imports
            from backend.core.linkedin_publisher import publish_to_linkedin
            from backend.models.linkedin_credential import LinkedInCredential
            from backend.models.media_file import MediaFile

            # Get credentials and media
            linkedin_cred = db.query(LinkedInCredential).filter(
                LinkedInCredential.user_id == user.id,
                LinkedInCredential.is_connected == True,
            ).first()

            if not linkedin_cred:
                return jsonify({"error": "LinkedIn credentials not configured"}), 409

            media = db.query(MediaFile).filter(
                MediaFile.id == post.media_file_id
            ).first() if post.media_file_id else None

            # Publish
            result = publish_to_linkedin(
                access_token=linkedin_cred.get_access_token(),
                caption=post.caption,
                media_file=media,
                metadata=post.post_metadata or {},
            )

            # Update post
            post.mark_as_posted(result["post_id"], "linkedin")
            db.commit()

            logger.info(f"Job {job_id} executed immediately by user {user.id}")

            return jsonify({
                "message": "Post published",
                "post_id": post.id,
                "linkedin_post_id": post.linkedin_post_id,
            }), 200

        except Exception as e:
            logger.error(f"Job execution failed: {str(e)}")
            post.mark_as_failed(str(e))
            db.commit()
            return jsonify({"error": "Publishing service unavailable"}), 503

    finally:
        db.close()
