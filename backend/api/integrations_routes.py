"""Per-user LinkedIn app credentials.

Lets an account bring its own LinkedIn developer app instead of sharing the
server's. Always self-scoped: there is no user_id in these routes at all,
deliberately - the caller can only ever act on their own row, which is a
stronger guarantee than checking it after the fact.
"""

from flask import Blueprint, jsonify, request

from backend.models.audit import record as audit
from backend.utils.database import get_session
from backend.utils.logger import get_logger
from backend.utils.security import current_user

logger = get_logger("social_media_automation.integrations")

integrations_bp = Blueprint("integrations", __name__, url_prefix="/api/integrations")


def _require_person():
    """A signed-in human, never a machine caller or a guest.

    A guest account exists specifically to be sandboxed and to never publish -
    letting it register a LinkedIn app would hand it exactly the capability
    the whole guest design withholds.
    """
    user = current_user()
    if user is None:
        return None, (jsonify({"error": "Sign in required."}), 401)
    if user.is_guest_account():
        return None, (jsonify({"error": "Guest accounts cannot connect LinkedIn."}), 403)
    return user, None


@integrations_bp.route("/linkedin/credentials/status", methods=["GET"])
def linkedin_credentials_status():
    user, error = _require_person()
    if error:
        return error

    return jsonify({
        "configured": user.has_own_linkedin_app(),
        "client_id": user.linkedin_own_client_id,
    }), 200


@integrations_bp.route("/linkedin/credentials", methods=["POST"])
def save_linkedin_credentials():
    """Save this account's own LinkedIn app credentials.

    The secret is encrypted before it touches the database (User.set_own_
    linkedin_app -> backend/utils/crypto.py) and is never echoed back by any
    endpoint - /status reports only the client id.
    """
    user, error = _require_person()
    if error:
        return error

    body = request.get_json(silent=True) or {}
    client_id = (body.get("client_id") or "").strip()
    client_secret = (body.get("client_secret") or "").strip()

    if not client_id or not client_secret:
        return jsonify({"error": "client_id and client_secret are both required."}), 400
    if len(client_id) > 255 or len(client_secret) > 500:
        return jsonify({"error": "That doesn't look like a valid LinkedIn client_id/secret."}), 400

    db = get_session()
    try:
        target = db.merge(user)
        target.set_own_linkedin_app(client_id, client_secret)
        audit(
            db,
            action="linkedin.own_app_configured",
            actor=target,
            target=f"user:{target.id}",
            ip_address=request.remote_addr,
        )
        db.commit()
        return jsonify({"configured": True, "client_id": client_id}), 200
    finally:
        db.close()


@integrations_bp.route("/linkedin/credentials", methods=["DELETE"])
def clear_linkedin_credentials():
    """Fall back to the server's shared LinkedIn app, if any."""
    user, error = _require_person()
    if error:
        return error

    db = get_session()
    try:
        target = db.merge(user)
        target.clear_own_linkedin_app()
        audit(
            db,
            action="linkedin.own_app_removed",
            actor=target,
            target=f"user:{target.id}",
            ip_address=request.remote_addr,
        )
        db.commit()
        return jsonify({"configured": False}), 200
    finally:
        db.close()
