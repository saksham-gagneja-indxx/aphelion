"""
Media file upload and management routes.

Routes:
  POST /api/media/upload  - Upload video or image
  GET  /api/media         - List user's media files
  GET  /api/media/{id}    - Get media file details
  DELETE /api/media/{id}  - Delete media file
"""

from flask import Blueprint, request, jsonify
from backend.utils.database import get_session
from backend.models.media_file import MediaFile
from backend.models.user import User
from backend.utils.logger import get_logger
from backend.utils.security import current_user
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid

logger = get_logger("media")
media_bp = Blueprint("media", __name__, url_prefix="/api/media")

# Configuration
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "webm"}
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024   # 10 MB
UPLOAD_FOLDER = "data/uploads"


def get_media_storage_path(user_id: int, extension: str) -> str:
    """Generate secure storage path for media file."""
    unique_id = str(uuid.uuid4())
    return f"{UPLOAD_FOLDER}/user_{user_id}/{unique_id}.{extension}"


def validate_file_extension(filename: str) -> tuple[bool, str, str]:
    """
    Validate file extension and determine media type.

    Returns:
        (is_valid, media_type, extension)
    """
    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""

    if ext in ALLOWED_VIDEO_EXTENSIONS:
        return True, "video", ext
    elif ext in ALLOWED_IMAGE_EXTENSIONS:
        return True, "image", ext
    else:
        return False, "", ""


def get_max_file_size(media_type: str) -> int:
    """Get max file size for media type."""
    return MAX_VIDEO_SIZE if media_type == "video" else MAX_IMAGE_SIZE


# ============================================================================
# Routes
# ============================================================================


@media_bp.route("/upload", methods=["POST"])
def upload_media():
    """
    Upload a media file (video or image).

    Request:
        POST /api/media/upload
        Authorization: Bearer {session_token}
        Content-Type: multipart/form-data
        file: (binary file)
        metadata: {"title": "...", "description": "..."}  # optional

    Response (201):
        {
          "id": 42,
          "filename": "my_video.mp4",
          "file_size_bytes": 45000000,
          "media_type": "video",
          "duration_seconds": 30.5,
          "width": 1920,
          "height": 1080,
          "thumbnail_url": "https://storage/thumb_42.jpg",
          "storage_url": "https://storage/media_42.mp4",
          "created_at": "2026-08-18T10:00:00Z",
          "expires_at": "2026-09-18T10:00:00Z"
        }

    Response (400):
        {
          "error": "File too large (max 100MB for videos)"
        }

    Response (401):
        {
          "error": "Unauthorized"
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    # Check file provided
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    # Validate extension
    is_valid, media_type, extension = validate_file_extension(file.filename)
    if not is_valid:
        return jsonify({
            "error": f"Invalid file type. Allowed: {', '.join(ALLOWED_VIDEO_EXTENSIONS | ALLOWED_IMAGE_EXTENSIONS)}"
        }), 400

    # Check file size
    max_size = get_max_file_size(media_type)
    if file.content_length and file.content_length > max_size:
        return jsonify({
            "error": f"File too large (max {max_size / 1024 / 1024:.0f}MB for {media_type}s)"
        }), 413

    try:
        # Secure filename
        secure_name = secure_filename(file.filename)
        storage_path = get_media_storage_path(user.id, extension)

        # Create directory if needed
        storage_dir = os.path.dirname(storage_path)
        os.makedirs(storage_dir, exist_ok=True)

        # Save file
        file.save(storage_path)

        # Get file size
        file_size = os.path.getsize(storage_path)
        if file_size > max_size:
            os.remove(storage_path)
            return jsonify({
                "error": f"File too large (max {max_size / 1024 / 1024:.0f}MB for {media_type}s)"
            }), 413

        # Create media file record
        db = get_session()
        try:
            media = MediaFile(
                user_id=user.id,
                filename=secure_name,
                file_size_bytes=file_size,
                media_type=media_type,
                mime_type=file.content_type or f"{media_type}/{extension}",
                file_extension=extension,
                storage_path=storage_path,
                storage_url=f"/api/media/{storage_path}",  # Local storage URL
                storage_service="local",
                upload_completed_at=datetime.utcnow(),
            )
            db.add(media)
            db.commit()
            db.refresh(media)

            logger.info(f"Media uploaded: {media.id} ({secure_name}) by user {user.id}")

            return jsonify({
                "id": media.id,
                "filename": media.filename,
                "file_size_bytes": media.file_size_bytes,
                "media_type": media.media_type,
                "thumbnail_url": media.thumbnail_url,
                "storage_url": media.storage_url,
                "created_at": media.created_at.isoformat() if media.created_at else None,
                "expires_at": media.expires_at.isoformat() if media.expires_at else None,
            }), 201

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        return jsonify({"error": "Upload failed"}), 500


@media_bp.route("", methods=["GET"])
def list_media():
    """
    List user's media files.

    Request:
        GET /api/media?limit=20&offset=0&sort=created_at_desc
        Authorization: Bearer {session_token}

    Response (200):
        {
          "total": 25,
          "items": [
            {
              "id": 42,
              "filename": "video.mp4",
              "media_type": "video",
              "file_size_bytes": 45000000,
              "created_at": "2026-08-18T10:00:00Z"
            },
            ...
          ]
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    limit = min(int(request.args.get("limit", 20)), 100)
    offset = int(request.args.get("offset", 0))

    db = get_session()
    try:
        # Get total count
        total = db.query(MediaFile).filter(
            MediaFile.user_id == user.id,
            MediaFile.is_deleted == False,
        ).count()

        # Get paginated items
        items = db.query(MediaFile).filter(
            MediaFile.user_id == user.id,
            MediaFile.is_deleted == False,
        ).order_by(MediaFile.created_at.desc()).limit(limit).offset(offset).all()

        return jsonify({
            "total": total,
            "items": [
                {
                    "id": m.id,
                    "filename": m.filename,
                    "media_type": m.media_type,
                    "file_size_bytes": m.file_size_bytes,
                    "duration_seconds": float(m.duration_seconds) if m.duration_seconds else None,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in items
            ]
        }), 200

    finally:
        db.close()


@media_bp.route("/<int:media_id>", methods=["DELETE"])
def delete_media(media_id: int):
    """
    Delete a media file.

    Request:
        DELETE /api/media/42
        Authorization: Bearer {session_token}

    Response (200):
        {
          "message": "Media deleted"
        }

    Response (404):
        {
          "error": "Media not found"
        }

    Response (409):
        {
          "error": "Cannot delete media with published posts"
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    db = get_session()
    try:
        media = db.query(MediaFile).filter(
            MediaFile.id == media_id,
            MediaFile.user_id == user.id,
        ).first()

        if not media:
            return jsonify({"error": "Media not found"}), 404

        # Check if media is used by published posts
        published_posts = db.query(db.func.count()).filter(
            db.models.Post.media_file_id == media_id,
            db.models.Post.status.in_(["published", "scheduled"]),
        ).scalar()

        if published_posts > 0:
            return jsonify({
                "error": "Cannot delete media with published posts"
            }), 409

        # Soft delete
        media.mark_deleted()
        db.commit()

        logger.info(f"Media deleted: {media_id} by user {user.id}")

        return jsonify({"message": "Media deleted"}), 200

    finally:
        db.close()
