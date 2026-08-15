"""
Flask API Routes - All REST endpoints for the application
Handles user management, scheduling, uploads, and analytics
"""

from flask import Blueprint, request, jsonify, current_app, send_file, g
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException
from pathlib import Path
from datetime import datetime
import pytz

from backend.utils.logger import get_logger
from backend.utils.database import get_session
from backend.utils.config import get_settings
from backend.utils.security import current_user, require_user_access
from backend.core.agent import get_agent, clear_agent
from backend.core.reel_manager import get_reel_manager
from backend.core.scheduler import get_scheduler
from backend.core.analytics_engine import get_analytics_engine
from backend.models.user import User
from backend.models.post import Post, PostStatus, PostPlatform
from backend.models.analytics import Analytics
from sqlalchemy.exc import IntegrityError

logger = get_logger("social_media_automation.api")
settings = get_settings()

# Create blueprint
api_bp = Blueprint("api", __name__, url_prefix="/api")


def _scope_to_caller(user_id):
    """Resolve the user_id filter for the scheduler listing endpoints.

    Both take user_id as an OPTIONAL query parameter, where None means "every
    user's jobs". That default is fine for an administrator or the scheduler
    itself, but for an ordinary operator it would list other people's posts, so
    an absent filter is narrowed to their own id rather than left wide open.

    Returns the id to filter by, or a Flask error tuple the caller must return.
    """
    if getattr(g, "is_machine", False):
        return user_id

    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized. Sign in or provide an API key."}), 401

    if user.is_admin():
        return user_id

    if user_id is None:
        return user.id

    denied = require_user_access(user_id)
    if denied:
        return denied

    return user_id


# ============ USER ENDPOINTS ============

@api_bp.route("/users", methods=["POST"])
def create_user():
    """Create a new user account"""
    try:
        data = request.get_json()
        db = get_session()

        # Only the username is required. The password used to be mandatory
        # here but was never persisted or used - the User model has no password
        # column, and auth happens later via /users/<id>/authenticate. Requiring
        # it blocked creating the single local user before credentials exist.
        if not data.get("instagram_username"):
            return jsonify({"error": "instagram_username is required"}), 400

        # Check if user exists
        existing = db.query(User).filter(
            User.instagram_username == data["instagram_username"]
        ).first()

        if existing:
            db.close()
            return jsonify({"error": "User already exists"}), 409

        # Create user
        user = User(
            instagram_username=data["instagram_username"],
            timezone=data.get("timezone", settings.timezone),
            account_name=data.get("account_name"),
        )

        db.add(user)
        db.commit()

        logger.info(f"✅ Created user: {user.instagram_username}")

        response = user.to_dict()
        db.close()
        return jsonify(response), 201

    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    """Get user information"""
    denied = require_user_access(user_id)
    if denied:
        return denied

    try:
        db = get_session()
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            db.close()
            return jsonify({"error": "User not found"}), 404

        response = user.to_dict()
        db.close()
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error getting user: {str(e)}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/users/<int:user_id>/authenticate", methods=["POST"])
def authenticate_user(user_id):
    """Authenticate user with Instagram"""
    denied = require_user_access(user_id)
    if denied:
        return denied

    try:
        data = request.get_json()
        db = get_session()

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            db.close()
            return jsonify({"error": "User not found"}), 404

        # Get agent
        agent = get_agent(user, db)

        # Authenticate
        password = data.get("password") or settings.instagram_password
        success = agent.authenticate(user.instagram_username, password)

        if success:
            user.update_last_login()
            db.commit()
            logger.info(f"✅ Authenticated user: {user.instagram_username}")

            response = {
                "success": True,
                "message": "Authentication successful",
                "user": user.to_dict()
            }
        else:
            response = {
                "success": False,
                "message": "Authentication failed"
            }

        db.close()
        return jsonify(response), 200 if success else 401

    except Exception as e:
        logger.error(f"Error authenticating user: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ============ POST/REEL ENDPOINTS ============

@api_bp.route("/posts", methods=["POST"])
def create_post():
    """Create a new post"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")

        denied = require_user_access(user_id)
        if denied:
            return denied

        db = get_session()

        # Validate user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            db.close()
            return jsonify({"error": "User not found"}), 404

        video_path = data.get("video_path", "")
        if not video_path:
            db.close()
            return jsonify({"error": "video_path is required"}), 400

        # Carry the reel's on-disk metadata onto the post. The posting job
        # reads post.thumbnail_path, and the UI wants duration/size without
        # re-statting the file.
        reel_manager = get_reel_manager()
        reel_info = reel_manager.get_reel_info(Path(video_path))
        if reel_info is None:
            db.close()
            return jsonify({"error": f"No reel found at '{video_path}'"}), 400

        # Create post
        post = Post(
            user_id=user_id,
            video_path=video_path,
            thumbnail_path=reel_info.get("thumbnail_path"),
            video_duration=reel_info.get("duration_seconds"),
            video_size=reel_info.get("size_bytes"),
            caption=data.get("caption"),
            hashtags=data.get("hashtags"),
            # Records that the caption came from caption assist rather than
            # being typed. The column has existed since the first schema and
            # was never written to; the Queue and the audit trail are more
            # honest with it populated.
            ai_generated_caption=bool(data.get("ai_generated_caption", False)),
            status=PostStatus.DRAFT,
            # Defaults to LinkedIn: it is the only platform that can currently
            # publish. Defaulting to Instagram created posts that were
            # guaranteed to fail at publish time, since InstagramPublisher is
            # disabled pending Meta App Review.
            platform=data.get("platform", PostPlatform.LINKEDIN),
        )

        db.add(post)
        db.commit()

        logger.info(f"✅ Created post: {post.id}")

        response = post.to_dict()
        db.close()
        return jsonify(response), 201

    except Exception as e:
        logger.error(f"Error creating post: {str(e)}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/posts/<int:post_id>", methods=["GET"])
def get_post(post_id):
    """Get post information"""
    try:
        db = get_session()
        post = db.query(Post).filter(Post.id == post_id).first()

        if not post:
            db.close()
            return jsonify({"error": "Post not found"}), 404

        denied = require_user_access(post.user_id)
        if denied:
            db.close()
            return denied

        response = post.to_dict()
        db.close()
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error getting post: {str(e)}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/posts/<int:post_id>/schedule", methods=["POST"])
def schedule_post(post_id):
    """Schedule a post for posting"""
    try:
        data = request.get_json()
        db = get_session()

        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            db.close()
            return jsonify({"error": "Post not found"}), 404

        denied = require_user_access(post.user_id)
        if denied:
            db.close()
            return denied

        user = db.query(User).filter(User.id == post.user_id).first()
        if not user:
            db.close()
            return jsonify({"error": "User not found"}), 404

        # Parse scheduled time. Previously a missing/invalid value fell through
        # as None and blew up inside the scheduler as an opaque 500.
        scheduled_time_str = data.get("scheduled_time")
        if not scheduled_time_str:
            db.close()
            return jsonify({"error": "scheduled_time is required (ISO 8601)"}), 400

        tz = pytz.timezone(user.timezone)
        try:
            scheduled_time = datetime.fromisoformat(scheduled_time_str)
        except ValueError:
            db.close()
            return jsonify({
                "error": f"Invalid scheduled_time '{scheduled_time_str}' - expected ISO 8601"
            }), 400

        # Naive datetimes are interpreted in the user's configured timezone.
        if scheduled_time.tzinfo is None:
            scheduled_time = tz.localize(scheduled_time)

        # A past time would either fire instantly or be silently dropped by
        # APScheduler's misfire grace window - reject it explicitly instead.
        if scheduled_time <= datetime.now(tz):
            db.close()
            return jsonify({
                "error": "scheduled_time must be in the future",
                "scheduled_time": scheduled_time.isoformat(),
                "now": datetime.now(tz).isoformat(),
            }), 400

        # Schedule post
        scheduler = get_scheduler()
        job_id = scheduler.schedule_post(user, post_id, scheduled_time)

        if job_id:
            # The scheduler commits status/scheduled_time/job_id from its own
            # session, so this session's copy is stale. Refresh before
            # serialising or the client sees status="draft", job_id=null.
            db.refresh(post)

            response = {
                "success": True,
                "job_id": job_id,
                "post": post.to_dict()
            }
            db.close()
            return jsonify(response), 200
        else:
            db.close()
            return jsonify({"error": "Failed to schedule post"}), 500

    except Exception as e:
        logger.error(f"Error scheduling post: {str(e)}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/posts/<int:post_id>/schedule-optimal", methods=["POST"])
def schedule_post_optimal(post_id):
    """Schedule post at optimal engagement time"""
    try:
        db = get_session()

        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            db.close()
            return jsonify({"error": "Post not found"}), 404

        denied = require_user_access(post.user_id)
        if denied:
            db.close()
            return denied

        user = db.query(User).filter(User.id == post.user_id).first()
        if not user:
            db.close()
            return jsonify({"error": "User not found"}), 404

        # Get analytics engine
        analytics_engine = get_analytics_engine(user, db)

        # Schedule at optimal time
        scheduler = get_scheduler()
        job_id = scheduler.schedule_at_optimal_time(user, post_id, analytics_engine)

        if job_id:
            response = {
                "success": True,
                "job_id": job_id,
                "message": "Post scheduled at optimal time",
                "post": post.to_dict()
            }
        else:
            response = {
                "success": False,
                "message": "Could not determine optimal time"
            }

        db.close()
        return jsonify(response), 200 if job_id else 400

    except Exception as e:
        logger.error(f"Error scheduling optimal post: {str(e)}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/posts/<int:post_id>", methods=["DELETE"])
def cancel_post(post_id):
    """Cancel a scheduled post"""
    try:
        # Ownership is checked against the stored post before the scheduler is
        # touched: cancel_post() only takes an id, so without this lookup any
        # signed-in user could cancel anyone's scheduled post.
        db = get_session()
        try:
            post = db.query(Post).filter(Post.id == post_id).first()
            if not post:
                return jsonify({"error": "Post not found"}), 404

            denied = require_user_access(post.user_id)
            if denied:
                return denied
        finally:
            db.close()

        scheduler = get_scheduler()
        success = scheduler.cancel_post(post_id)

        if success:
            return jsonify({"success": True, "message": "Post cancelled"}), 200
        else:
            return jsonify({"success": False, "message": "Could not cancel post"}), 500

    except Exception as e:
        logger.error(f"Error cancelling post: {str(e)}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/posts/<int:post_id>/delete", methods=["DELETE"])
def delete_post(post_id):
    """Remove a post entirely, cancelling its scheduled job first.

    Distinct from cancel: cancelling leaves the record visible with a
    'cancelled' status, which is the right default because it preserves what
    was attempted. This is for clearing it out of the list afterwards.

    The scheduler job is cancelled BEFORE the row is deleted. The other order
    leaves a job pointing at a post id that no longer exists, which fires and
    fails at publish time.
    """
    db = get_session()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return jsonify({"error": "Post not found"}), 404

        denied = require_user_access(post.user_id)
        if denied:
            return denied

        was_scheduled = post.status in (PostStatus.QUEUED, PostStatus.SCHEDULED)
    finally:
        db.close()

    if was_scheduled:
        try:
            get_scheduler().cancel_post(post_id)
        except Exception as e:
            # A missing job is fine - it may already have run or been cancelled.
            logger.warning(f"Could not cancel job for post {post_id}: {e}")

    db = get_session()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if post is None:
            return jsonify({"success": True, "message": "Post already removed"}), 200
        db.delete(post)
        db.commit()
    finally:
        db.close()

    logger.info(f"Deleted post {post_id}")
    return jsonify({"success": True, "deleted": post_id}), 200


@api_bp.route("/users/<int:user_id>/posts", methods=["GET"])
def get_user_posts(user_id):
    """Get all posts for a user"""
    denied = require_user_access(user_id)
    if denied:
        return denied

    try:
        db = get_session()

        # Get status filter
        status = request.args.get("status")

        query = db.query(Post).filter(Post.user_id == user_id)
        if status:
            query = query.filter(Post.status == status)

        posts = query.order_by(Post.created_at.desc()).all()

        response = {
            "count": len(posts),
            "posts": [p.to_dict() for p in posts]
        }

        db.close()
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error getting user posts: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ============ UPLOAD ENDPOINTS ============

@api_bp.route("/upload", methods=["POST"])
def upload_reel():
    """Upload a new reel"""
    try:
        user_id = request.form.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id required"}), 400

        denied = require_user_access(user_id)
        if denied:
            return denied

        # Check file
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        # Get the reel manager FIRST: its constructor creates the upload and
        # reels directories. Saving before this point fails with ENOENT on any
        # fresh environment - it only appeared to work locally because earlier
        # runs had already created the folders.
        reel_manager = get_reel_manager()

        # Save uploaded file
        filename = secure_filename(file.filename)
        temp_path = Path(settings.upload_folder) / filename
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        file.save(str(temp_path))

        # Validate and move to reels folder
        success, reel_path, error_msg = reel_manager.upload_reel(
            temp_path,
            int(user_id),
            keep_original=False
        )

        if not success:
            temp_path.unlink(missing_ok=True)
            return jsonify({"error": error_msg}), 400

        # Get reel info
        reel_info = reel_manager.get_reel_info(reel_path)

        response = {
            "success": True,
            "message": "Reel uploaded successfully",
            "reel": reel_info
        }

        return jsonify(response), 201

    except HTTPException:
        # Let Flask's own handlers deal with HTTP errors - notably the 413
        # raised by MAX_CONTENT_LENGTH when the body is read. Without this the
        # generic handler below rewrote it into a 500.
        raise
    except Exception as e:
        logger.error(f"Error uploading reel: {str(e)}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/users/<int:user_id>/reels", methods=["GET"])
def get_user_reels(user_id):
    """Get all reels for a user"""
    denied = require_user_access(user_id)
    if denied:
        return denied

    try:
        reel_manager = get_reel_manager()
        reels = reel_manager.list_user_reels(user_id)

        response = {
            "count": len(reels),
            "reels": reels
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error getting user reels: {str(e)}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/users/<int:user_id>/reels/<path:filename>", methods=["DELETE"])
def delete_reel(user_id, filename):
    """Delete one of a user's uploaded reels, and its thumbnail.

    Refuses while a post still references the file: deleting it would leave a
    scheduled post pointing at nothing, which fails at publish time - long
    after the mistake, and with no obvious cause.
    """
    denied = require_user_access(user_id)
    if denied:
        return denied

    try:
        reel_manager = get_reel_manager()
        user_folder = (reel_manager.reels_folder / str(user_id)).resolve()

        # Same guard as the thumbnail route: resolve, then confirm the result
        # is still inside this user's folder so a crafted name cannot walk out.
        candidate = (user_folder / filename).resolve()
        if not candidate.is_relative_to(user_folder):
            return jsonify({"error": "Invalid filename"}), 400

        if not candidate.exists():
            return jsonify({"error": "Reel not found"}), 404

        db = get_session()
        try:
            blocking = (
                db.query(Post)
                .filter(
                    Post.user_id == user_id,
                    Post.video_path.like(f"%{candidate.name}"),
                    # Anything not yet published still needs the file.
                    Post.status.in_([
                        PostStatus.DRAFT,
                        PostStatus.QUEUED,
                        PostStatus.SCHEDULED,
                    ]),
                )
                .count()
            )
            if blocking:
                return jsonify({
                    "error": f"This reel is used by {blocking} scheduled post(s). "
                             f"Cancel them first."
                }), 409
        finally:
            db.close()

        candidate.unlink()
        thumbnail = candidate.with_suffix(".jpg")
        if thumbnail.exists():
            thumbnail.unlink()

        logger.info(f"Deleted reel {candidate.name} for user {user_id}")
        return jsonify({"success": True, "deleted": candidate.name}), 200

    except Exception as e:
        logger.error(f"Error deleting reel: {str(e)}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/users/<int:user_id>/reels/<path:filename>/thumbnail", methods=["GET"])
def get_reel_thumbnail(user_id, filename):
    """Serve the generated thumbnail for one of a user's reels."""
    denied = require_user_access(user_id)
    if denied:
        return denied

    try:
        reel_manager = get_reel_manager()
        user_folder = (reel_manager.reels_folder / str(user_id)).resolve()

        # Resolve and confirm the result stays inside the user's own folder,
        # so a crafted filename can't walk out of it.
        candidate = (user_folder / filename).resolve()
        if not candidate.is_relative_to(user_folder):
            return jsonify({"error": "Invalid filename"}), 400

        thumbnail = candidate.with_suffix(".jpg")
        if not thumbnail.exists():
            return jsonify({"error": "Thumbnail not found"}), 404

        return send_file(thumbnail, mimetype="image/jpeg")

    except Exception as e:
        logger.error(f"Error serving thumbnail: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ============ ANALYTICS ENDPOINTS ============

@api_bp.route("/users/<int:user_id>/analytics", methods=["GET"])
def get_user_analytics(user_id):
    """Get analytics for a user"""
    denied = require_user_access(user_id)
    if denied:
        return denied

    try:
        db = get_session()

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            db.close()
            return jsonify({"error": "User not found"}), 404

        # Get analytics
        analytics_engine = get_analytics_engine(user, db)
        summary = analytics_engine.get_analytics_summary()

        db.close()

        if summary:
            return jsonify(summary), 200
        else:
            return jsonify({"message": "No analytics data available"}), 200

    except Exception as e:
        logger.error(f"Error getting analytics: {str(e)}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/users/<int:user_id>/analyze", methods=["POST"])
def analyze_engagement(user_id):
    """Analyze engagement and calculate optimal times"""
    denied = require_user_access(user_id)
    if denied:
        return denied

    try:
        db = get_session()

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            db.close()
            return jsonify({"error": "User not found"}), 404

        # Check if authenticated
        if not user.instagram_connected:
            db.close()
            return jsonify({"error": "Instagram not connected"}), 401

        # Get agent
        agent = get_agent(user, db)

        # Get engagement data
        engagement_data = agent.get_engagement_data()

        if not engagement_data:
            db.close()
            return jsonify({"error": "Could not fetch engagement data"}), 500

        # Analyze
        analytics_engine = get_analytics_engine(user, db)
        analytics = analytics_engine.analyze_engagement(engagement_data)

        if analytics:
            response = {
                "success": True,
                "analytics": analytics.to_dict()
            }
        else:
            response = {
                "success": False,
                "error": "Analysis failed"
            }

        db.close()
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error analyzing engagement: {str(e)}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/users/<int:user_id>/optimal-time", methods=["GET"])
def get_optimal_time(user_id):
    """Get next optimal posting time"""
    denied = require_user_access(user_id)
    if denied:
        return denied

    try:
        db = get_session()

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            db.close()
            return jsonify({"error": "User not found"}), 404

        # Get analytics engine
        analytics_engine = get_analytics_engine(user, db)
        optimal_time = analytics_engine.get_next_optimal_posting_time()

        db.close()

        if optimal_time:
            return jsonify(optimal_time), 200
        else:
            return jsonify({"message": "No optimal time available"}), 200

    except Exception as e:
        logger.error(f"Error getting optimal time: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ============ SCHEDULER ENDPOINTS ============

@api_bp.route("/scheduler/status", methods=["GET"])
def scheduler_status():
    """Get scheduler status"""
    try:
        scheduler = get_scheduler()
        status = scheduler.get_jobs_count()

        return jsonify(status), 200

    except Exception as e:
        logger.error(f"Error getting scheduler status: {str(e)}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/scheduler/jobs", methods=["GET"])
def get_scheduled_jobs():
    """Get all scheduled jobs"""
    try:
        user_id = _scope_to_caller(request.args.get("user_id", type=int))
        if isinstance(user_id, tuple):
            return user_id

        scheduler = get_scheduler()
        jobs = scheduler.get_scheduled_posts(user_id)

        return jsonify({
            "count": len(jobs),
            "jobs": jobs
        }), 200

    except Exception as e:
        logger.error(f"Error getting scheduled jobs: {str(e)}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/scheduler/pending", methods=["GET"])
def get_pending_posts():
    """Get all pending posts"""
    try:
        user_id = _scope_to_caller(request.args.get("user_id", type=int))
        if isinstance(user_id, tuple):
            return user_id

        scheduler = get_scheduler()
        posts = scheduler.get_pending_posts(user_id)

        return jsonify({
            "count": len(posts),
            "posts": posts
        }), 200

    except Exception as e:
        logger.error(f"Error getting pending posts: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ============ QUEUE ENDPOINTS ============

@api_bp.route("/queue/add", methods=["POST"])
def add_to_queue():
    """Add a post to the queue"""
    try:
        data = request.get_json()
        db = get_session()

        post_id = data.get("post_id")
        post = db.query(Post).filter(Post.id == post_id).first()

        if not post:
            db.close()
            return jsonify({"error": "Post not found"}), 404

        denied = require_user_access(post.user_id)
        if denied:
            db.close()
            return denied

        # Update status to queued
        post.status = PostStatus.QUEUED
        db.commit()

        response = {
            "success": True,
            "message": "Post added to queue",
            "post": post.to_dict()
        }

        db.close()
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error adding to queue: {str(e)}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/queue/<int:post_id>", methods=["DELETE"])
def remove_from_queue(post_id):
    """Remove a post from the queue"""
    try:
        db = get_session()

        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            db.close()
            return jsonify({"error": "Post not found"}), 404

        denied = require_user_access(post.user_id)
        if denied:
            db.close()
            return denied

        # Update status back to draft
        post.status = PostStatus.DRAFT
        db.commit()

        response = {
            "success": True,
            "message": "Post removed from queue"
        }

        db.close()
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error removing from queue: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ============ STATS ENDPOINTS ============

@api_bp.route("/stats", methods=["GET"])
def get_stats():
    """Get application statistics"""
    try:
        db = get_session()

        # Count users
        user_count = db.query(User).count()

        # Count posts
        total_posts = db.query(Post).count()
        posted_count = db.query(Post).filter(Post.status == PostStatus.POSTED).count()
        scheduled_count = db.query(Post).filter(Post.status == PostStatus.SCHEDULED).count()

        response = {
            "users": user_count,
            "posts": {
                "total": total_posts,
                "posted": posted_count,
                "scheduled": scheduled_count,
                "pending": total_posts - posted_count - scheduled_count
            },
            "scheduler": get_scheduler().get_jobs_count()
        }

        db.close()
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        return jsonify({"error": str(e)}), 500
