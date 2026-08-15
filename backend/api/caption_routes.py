"""Caption assist endpoints.

Ownership follows the same rule as publishing: `user_id` is never taken from
the request body. A human session may only ask for captions against its own
reels, so one operator cannot use another's thumbnails as model input.
"""

from pathlib import Path

from flask import Blueprint, jsonify, request

from backend.core.captions import (
    CaptionError,
    is_configured,
    suggest_captions,
    unavailable_reason,
)
from backend.core.storage import get_media_store
from backend.models.user import User
from backend.utils.database import get_session
from backend.utils.logger import get_logger
from backend.utils.security import current_user

logger = get_logger("social_media_automation.captions")

caption_bp = Blueprint("captions", __name__, url_prefix="/api/captions")

MAX_BRIEF_CHARS = 2000


def _resolve_thumbnail(user_id: int, reel_filename: str):
    """The thumbnail for one of this user's reels, or None.

    Mirrors the containment check the thumbnail route uses: resolve inside the
    user's own folder and refuse anything that walks out of it, so a crafted
    filename cannot feed an arbitrary file on disk to the model.
    """
    if not reel_filename:
        return None

    candidate = get_media_store().resolve(user_id, reel_filename)
    if candidate is None:
        return None

    thumbnail = candidate.with_suffix(".jpg")
    return thumbnail if thumbnail.is_file() else None


@caption_bp.route("/status", methods=["GET"])
def caption_status():
    """Whether caption assist can run, so the UI can hide or explain itself."""
    return jsonify({
        "available": is_configured(),
        "reason": unavailable_reason(),
    }), 200


@caption_bp.route("/suggest", methods=["POST"])
def suggest():
    """Three caption options for a reel, written from the caller's brief."""
    data = request.get_json(silent=True) or {}

    brief = (data.get("brief") or "").strip()
    if len(brief) > MAX_BRIEF_CHARS:
        return jsonify({
            "error": f"Brief is too long (max {MAX_BRIEF_CHARS} characters)."
        }), 400

    actor = current_user()
    db = None
    try:
        if actor is not None:
            user_id = actor.id
        else:
            # Machine caller holding the API key. It is already full-privilege,
            # but it still has to name a user that exists so the thumbnail
            # lookup is scoped to a real folder.
            user_id = data.get("user_id")
            if not user_id:
                return jsonify({"error": "user_id is required"}), 400
            db = get_session()
            if db.query(User).filter(User.id == user_id).first() is None:
                return jsonify({"error": "User not found"}), 404

        thumbnail = _resolve_thumbnail(user_id, data.get("reel_filename") or "")

        captions = suggest_captions(
            brief=brief,
            thumbnail=thumbnail,
            duration_seconds=data.get("duration_seconds"),
        )

        return jsonify({
            "captions": captions,
            "used_thumbnail": thumbnail is not None,
        }), 200

    except CaptionError as e:
        return jsonify({"error": e.message}), e.status
    except Exception as e:
        logger.exception("Caption generation failed")
        return jsonify({"error": f"Caption generation failed: {e}"}), 500
    finally:
        if db is not None:
            db.close()
