"""Conversational composer endpoints.

Ownership follows the same rule as everywhere else: `user_id` comes from the
authenticated session, never the request body, so one operator cannot compose
against another's reels.

Note what is *not* here. There is no publish route on this blueprint and no
tool that reaches one. The composer returns a draft; turning that draft into a
post still goes through the existing create / schedule / publish endpoints,
which require a deliberate authenticated request from a human. See
backend/core/composer.py for why that boundary is drawn where it is.
"""

from flask import Blueprint, jsonify, request

from backend.core.captions import is_configured, unavailable_reason
from backend.core.composer import ComposerError, empty_draft, run_turn
from backend.core.reel_manager import get_reel_manager
from backend.models.user import User
from backend.utils.config import get_settings
from backend.utils.database import get_session
from backend.utils.logger import get_logger
from backend.utils.security import current_user

logger = get_logger("social_media_automation.composer")

composer_bp = Blueprint("composer", __name__, url_prefix="/api/composer")


@composer_bp.route("/status", methods=["GET"])
def composer_status():
    """Whether the composer can run, so the UI can explain itself or hide."""
    return jsonify({"available": is_configured(), "reason": unavailable_reason()}), 200


@composer_bp.route("/turn", methods=["POST"])
def turn():
    """One exchange with the composer.

    In:  {messages: [{role, content}], draft?: {...}}
    Out: {reply, draft, ready, actions}
    """
    data = request.get_json(silent=True) or {}
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        return jsonify({"error": "messages is required"}), 400

    actor = current_user()
    db = None
    try:
        if actor is not None:
            user_id = actor.id
            tz_name = actor.timezone or get_settings().timezone
        else:
            # Machine caller holding the API key. Full privilege already, but
            # it still has to name a real user so reels resolve to a folder.
            user_id = data.get("user_id")
            if not user_id:
                return jsonify({"error": "user_id is required"}), 400
            db = get_session()
            owner = db.query(User).filter(User.id == user_id).first()
            if owner is None:
                return jsonify({"error": "User not found"}), 404
            tz_name = owner.timezone or get_settings().timezone

        reels = get_reel_manager().list_user_reels(user_id)

        result = run_turn(
            messages=messages,
            draft=data.get("draft") or empty_draft(),
            reels=reels,
            tz_name=tz_name,
        )
        return jsonify(result), 200

    except ComposerError as e:
        return jsonify({"error": e.message}), e.status
    except Exception as e:
        logger.exception("Composer turn failed")
        return jsonify({"error": "Composer failed"}), 500
    finally:
        if db is not None:
            db.close()
