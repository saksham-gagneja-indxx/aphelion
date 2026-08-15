"""Guest accounts: try the tool without a LinkedIn account.

Not a bypass of authentication - a guest gets an ordinary account and an
ordinary session, and every guard in the app applies to it exactly as it does
to anyone else. What makes it safe to offer publicly is what a guest cannot
reach:

  * it can never publish. Publishing acts on a real LinkedIn profile, and a
    guest has not proved they own one.
  * it can never be an administrator. Enforced on the row (User.is_admin
    returns False for a guest regardless of role), not by remembering to check
    it at each call site.
  * it sees only its own data, through the same ownership guard as everyone.

Each request creates a NEW account rather than sharing one. Two people trying
the tool at the same time would otherwise see each other's uploads, which is
both confusing and a small privacy leak - and "guest" is exactly the population
you cannot ask to be careful.
"""

import secrets

from flask import Blueprint, jsonify, request

from backend.models.audit import record as audit
from backend.models.user import User
from backend.utils.config import get_settings, guest_access_enabled
from backend.utils.database import get_session
from backend.utils.logger import get_logger
from backend.utils.security import make_session_token

logger = get_logger("social_media_automation.guest")

guest_bp = Blueprint("guest", __name__, url_prefix="/api/auth/guest")


@guest_bp.route("/status", methods=["GET"])
def guest_status():
    """Whether the sign-in page should offer a guest option."""
    return jsonify({"enabled": guest_access_enabled()}), 200


@guest_bp.route("", methods=["POST"])
def create_guest():
    """Create a fresh sandboxed guest account and sign it in."""
    if not guest_access_enabled():
        return jsonify({
            "error": "Guest access is disabled on this server. Sign in with LinkedIn."
        }), 403

    # Unguessable and unique, so a guest can never collide with - or be
    # mistaken for - a LinkedIn identity, which uses the real `sub`.
    suffix = secrets.token_urlsafe(9)

    db = get_session()
    try:
        user = User(
            linkedin_sub=f"guest:{suffix}",
            full_name="Guest",
            email=None,
            role=User.ROLE_OPERATOR,
            # Active immediately: an approval queue makes sense for people
            # asking for real access, but a guest that has to wait for an
            # administrator is just a broken button.
            is_active=True,
            is_guest=True,
            timezone=get_settings().timezone,
        )
        db.add(user)
        db.flush()

        audit(
            db,
            action="user.guest_created",
            actor=user,
            target=f"user:{user.id}",
            detail="guest account",
            ip_address=request.remote_addr,
        )
        db.commit()

        token = make_session_token(user.id, days=1)
        user_id = user.id
        logger.info(f"Created guest account {user_id}")
    finally:
        db.close()

    return jsonify({
        "token": token,
        "user": {"id": user_id, "name": "Guest", "role": User.ROLE_OPERATOR},
        "limits": [
            "Publishing is disabled for guest accounts.",
            "Guest data is not shared with other accounts.",
            "This session lasts a day.",
        ],
    }), 201
