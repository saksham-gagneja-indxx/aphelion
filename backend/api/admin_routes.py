"""Administrator endpoints: user management and the audit log.

Every route here is guarded by `require_admin`. The guard runs as a
blueprint-level `before_request` rather than a decorator per route, for the
same reason the API key gate is global: a route added later is protected by
default instead of protected only if someone remembers.

The frontend also hides admin UI from non-admins, but that is convenience.
This is the actual enforcement.
"""

import requests
from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_

from backend.models.audit import AuditLog
from backend.models.audit import record as audit
from backend.models.post import Post
from backend.models.user import User
from backend.utils.database import get_session
from backend.utils.logger import get_logger
from backend.utils.security import current_user, require_admin

USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

logger = get_logger("social_media_automation.admin")

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.before_request
def guard():
    return require_admin()


@admin_bp.route("/users", methods=["GET"])
def list_users():
    """All accounts, with post counts."""
    db = get_session()
    try:
        counts = dict(
            db.query(Post.user_id, func.count(Post.id)).group_by(Post.user_id).all()
        )
        users = db.query(User).order_by(User.created_at.desc()).all()
        return jsonify({
            "users": [u.to_admin_dict(counts.get(u.id, 0)) for u in users],
            "total": len(users),
        }), 200
    finally:
        db.close()


@admin_bp.route("/users/<int:user_id>/role", methods=["POST"])
def set_role(user_id: int):
    """Promote or demote an account."""
    data = request.get_json(silent=True) or {}
    role = (data.get("role") or "").strip().lower()

    if role not in User.VALID_ROLES:
        return jsonify({
            "error": f"role must be one of: {', '.join(User.VALID_ROLES)}"
        }), 400

    actor = current_user()
    db = get_session()
    try:
        target = db.query(User).filter(User.id == user_id).first()
        if target is None:
            return jsonify({"error": "User not found"}), 404

        previous = target.role

        # Refuse to remove the last administrator. Without this the system can
        # be locked into a state where nobody can administer it and the only
        # way back in is direct database access.
        if previous == User.ROLE_ADMIN and role != User.ROLE_ADMIN:
            remaining = (
                db.query(User)
                .filter(User.role == User.ROLE_ADMIN, User.is_active.is_(True))
                .count()
            )
            if remaining <= 1:
                return jsonify({
                    "error": "Cannot demote the last administrator. "
                             "Promote another account first."
                }), 409

        target.role = role
        audit(
            db,
            action="user.role_changed",
            actor=actor,
            target=f"user:{target.id}",
            detail=f"{previous} -> {role}",
            ip_address=request.remote_addr,
        )
        db.commit()
        db.refresh(target)

        logger.info(f"Role changed for user {target.id}: {previous} -> {role}")
        return jsonify(target.to_admin_dict()), 200
    finally:
        db.close()


@admin_bp.route("/users/<int:user_id>/active", methods=["POST"])
def set_active(user_id: int):
    """Approve or suspend an account.

    This is the approval step for new sign-ups, which are created inactive.
    Deactivation takes effect immediately: `is_active` is checked on every
    request, so an already-issued session token stops working at once.
    """
    data = request.get_json(silent=True) or {}
    if "is_active" not in data:
        return jsonify({"error": "is_active is required"}), 400

    is_active = bool(data["is_active"])
    actor = current_user()

    db = get_session()
    try:
        target = db.query(User).filter(User.id == user_id).first()
        if target is None:
            return jsonify({"error": "User not found"}), 404

        # Locking yourself out is never the intent.
        if actor is not None and target.id == actor.id and not is_active:
            return jsonify({
                "error": "You cannot deactivate your own account."
            }), 409

        if not is_active and target.role == User.ROLE_ADMIN:
            remaining = (
                db.query(User)
                .filter(User.role == User.ROLE_ADMIN, User.is_active.is_(True))
                .count()
            )
            if remaining <= 1:
                return jsonify({
                    "error": "Cannot deactivate the last active administrator."
                }), 409

        target.is_active = is_active
        audit(
            db,
            action="user.activated" if is_active else "user.deactivated",
            actor=actor,
            target=f"user:{target.id}",
            detail=target.email,
            ip_address=request.remote_addr,
        )
        db.commit()
        db.refresh(target)

        logger.info(f"User {target.id} active={is_active}")
        return jsonify(target.to_admin_dict()), 200
    finally:
        db.close()


@admin_bp.route("/users/<int:user_id>/github", methods=["POST"])
def set_github(user_id: int):
    """HTTP twin of `admin_cli set-github` / `admin_cli unset-github`.

    Deliberately admin-only, same reasoning as the CLI version
    (backend/admin_cli.py's cmd_set_github): letting a user set their own
    github_username would let anyone claim an account by GitHub login alone,
    with no proof they actually control it. Pass `{"github_username": null}`
    (or omit it / send an empty string) to clear an existing mapping - e.g.
    to re-test the self-serve MCP link flow (see auth_routes.py's
    mcp_link_start) against an account that's already mapped.
    """
    data = request.get_json(silent=True) or {}
    github_username = (data.get("github_username") or "").strip() or None

    db = get_session()
    try:
        target = db.query(User).filter(User.id == user_id).first()
        if target is None:
            return jsonify({"error": "User not found"}), 404

        if github_username is not None:
            clash = (
                db.query(User)
                .filter(User.github_username == github_username, User.id != target.id)
                .first()
            )
            if clash is not None:
                return jsonify({
                    "error": f"GitHub login {github_username!r} is already mapped to "
                             f"account {clash.id}."
                }), 409

        target.github_username = github_username
        audit(
            db,
            action="user.github_mapped" if github_username else "user.github_unmapped",
            actor=current_user(),
            target=f"user:{target.id}",
            detail=github_username or "",
            ip_address=request.remote_addr,
        )
        db.commit()
        db.refresh(target)

        return jsonify({"id": target.id, "github_username": target.github_username}), 200
    finally:
        db.close()


@admin_bp.route("/users/<int:user_id>/backfill-linkedin-sub", methods=["POST"])
def backfill_linkedin_sub(user_id: int):
    """Repair tool for accounts stuck without a linkedin_sub.

    auth_routes.py's reconnect flow used to store a fresh LinkedIn token
    without ever recording the member's `sub` claim on the account - fixed
    now (see _resolve_user), but any account that reconnected before that
    fix is stuck: `sub` is what the plain LinkedIn sign-in path matches on,
    so without it the account can never sign in that way again, only
    however it was originally created (e.g. Clerk). Since the account
    already has a valid, connected access token, this just asks LinkedIn
    who that token belongs to and records it - no new OAuth round trip
    needed.
    """
    db = get_session()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            return jsonify({"error": "User not found"}), 404
        if user.linkedin_sub:
            return jsonify({"id": user.id, "linkedin_sub": user.linkedin_sub, "changed": False}), 200
        if not user.linkedin_access_token:
            return jsonify({"error": "No LinkedIn access token on file for this account."}), 409

        try:
            resp = requests.get(
                USERINFO_URL,
                headers={"Authorization": f"Bearer {user.linkedin_access_token}"},
                timeout=30,
            )
        except requests.RequestException as e:
            return jsonify({"error": f"Could not reach LinkedIn: {e}"}), 502

        if resp.status_code >= 400:
            return jsonify({
                "error": f"LinkedIn rejected the stored token (HTTP {resp.status_code}). "
                         "It may need to be reconnected fresh instead."
            }), 502

        subject = (resp.json() or {}).get("sub")
        if not subject:
            return jsonify({"error": "LinkedIn's response carried no subject claim."}), 502

        clash = db.query(User).filter(User.linkedin_sub == subject, User.id != user.id).first()
        if clash is not None:
            return jsonify({
                "error": f"That LinkedIn identity is already mapped to account {clash.id}."
            }), 409

        user.linkedin_sub = subject
        db.commit()
        return jsonify({"id": user.id, "linkedin_sub": subject, "changed": True}), 200
    finally:
        db.close()


@admin_bp.route("/encrypt-linkedin-tokens", methods=["POST"])
def encrypt_linkedin_tokens_route():
    """One-off migration trigger: force any plaintext LinkedIn access/refresh
    tokens onto encrypted storage immediately.

    Equivalent to `python -m backend.admin_cli encrypt-linkedin-tokens`
    (backend/admin_cli.py's encrypt_pending_linkedin_tokens does the actual
    work, shared by both). Exists as an HTTP route because the production
    database is not reachable directly from every environment that needs to
    run this once after deploying the encryption fix, but the deployed API
    always is. Idempotent - safe to call more than once.
    """
    from backend.admin_cli import encrypt_pending_linkedin_tokens

    db = get_session()
    try:
        count = encrypt_pending_linkedin_tokens(db)
        return jsonify({"migrated": count}), 200
    finally:
        db.close()


@admin_bp.route("/audit", methods=["GET"])
def audit_log():
    """Recent audit entries, newest first."""
    limit = min(request.args.get("limit", default=100, type=int), 500)
    action = request.args.get("action")

    db = get_session()
    try:
        query = db.query(AuditLog)
        if action:
            query = query.filter(AuditLog.action == action)

        events = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
        return jsonify({
            "events": [e.to_dict() for e in events],
            "count": len(events),
        }), 200
    finally:
        db.close()


@admin_bp.route("/stats", methods=["GET"])
def admin_stats():
    """Fleet-wide counts for the admin dashboard."""
    db = get_session()
    try:
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active.is_(True)).count()
        pending = db.query(User).filter(User.is_active.is_(False)).count()
        # linkedin_access_token is a Python property (encrypted at rest, see
        # backend/models/user.py) rather than a Column, so it can't be
        # filtered on directly at the class level - check both the encrypted
        # column and the legacy plaintext one a not-yet-migrated row might
        # still carry.
        connected = (
            db.query(User)
            .filter(
                or_(
                    User.linkedin_access_token_encrypted.isnot(None),
                    User._linkedin_access_token_legacy.isnot(None),
                )
            )
            .count()
        )

        by_status = dict(
            db.query(Post.status, func.count(Post.id)).group_by(Post.status).all()
        )

        return jsonify({
            "users": {
                "total": total_users,
                "active": active_users,
                "pending_approval": pending,
                "linkedin_connected": connected,
            },
            # Counted by actual status rather than derived by subtraction, so
            # cancelled and failed posts are not silently reported as pending.
            "posts": {
                "total": sum(by_status.values()),
                "by_status": by_status,
            },
        }), 200
    finally:
        db.close()
