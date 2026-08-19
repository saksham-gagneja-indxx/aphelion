"""Operations console: the state of the running system, and a few levers.

Distinct from /api/admin, which is about *people* - who exists, what role they
hold, whether they are approved. This is about the *deployment*: is the
scheduler actually running, where is the disk going, which features are on,
what is the database.

Separate because the questions are different and so are the answers you act on.
Nothing here is per-user; everything here is per-instance.

Guarded by `require_admin` as a blueprint-level before_request, same as the
admin routes: a route added later is protected by default rather than protected
if someone remembers.
"""

import os
import platform
import shutil
import sys
from pathlib import Path

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from backend.models.audit import AuditLog
from backend.models.audit import record as audit
from backend.models.post import Post
from backend.models.user import User
from backend.utils.config import (
    get_settings,
    guest_access_enabled,
    instagram_configured,
    linkedin_configured,
)
from backend.utils.database import get_session
from backend.utils.logger import get_logger
from backend.utils.security import current_user, require_admin

logger = get_logger("social_media_automation.console")

console_bp = Blueprint("console", __name__, url_prefix="/api/console")


@console_bp.before_request
def guard():
    return require_admin()


def _directory_size(path: Path) -> tuple:
    """(bytes, file count) for a directory tree, tolerating a missing one."""
    total, count = 0, 0
    if not path.exists():
        return 0, 0
    for entry in path.rglob("*"):
        if entry.is_file():
            try:
                total += entry.stat().st_size
                count += 1
            except OSError:
                # A file can vanish between the walk and the stat; it simply
                # does not count rather than taking the whole endpoint down.
                continue
    return total, count


@console_bp.route("/overview", methods=["GET"])
def overview():
    """Everything worth knowing about this instance in one call."""
    settings = get_settings()

    # ---- scheduler -------------------------------------------------------
    # Reported rather than assumed: on a free instance that sleeps, the
    # scheduler can be "enabled" in config and not running in fact, which is
    # the single most misleading state this system has.
    scheduler_state = {"enabled": settings.scheduler_enabled}
    try:
        from backend.core.scheduler import get_scheduler

        scheduler_state.update(get_scheduler().get_jobs_count())
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Scheduler status check failed: {e}")
        scheduler_state["error"] = "Scheduler status unavailable"

    # ---- storage ---------------------------------------------------------
    reels_path = Path(settings.reels_folder)
    uploads_path = Path(settings.upload_folder)
    reels_bytes, reels_files = _directory_size(reels_path)
    uploads_bytes, uploads_files = _directory_size(uploads_path)

    try:
        usage = shutil.disk_usage(reels_path if reels_path.exists() else Path("."))
        disk = {"total": usage.total, "used": usage.used, "free": usage.free}
    except OSError:
        disk = None

    # ---- database --------------------------------------------------------
    db = get_session()
    try:
        users_total = db.query(User).count()
        users_pending = db.query(User).filter(User.is_active.is_(False)).count()
        users_guest = db.query(User).filter(User.is_guest.is_(True)).count()
        posts_by_status = dict(
            db.query(Post.status, func.count(Post.id)).group_by(Post.status).all()
        )
        audit_total = db.query(AuditLog).count()
    finally:
        db.close()

    url = settings.database_url
    backend_name = url.split("://", 1)[0] if "://" in url else "unknown"

    return jsonify({
        "runtime": {
            "environment": settings.flask_env,
            "debug": settings.debug,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "pid": os.getpid(),
            "timezone": settings.timezone,
        },
        "database": {
            # Never the URL itself - it carries the password.
            "backend": backend_name,
            "users": {
                "total": users_total,
                "pending_approval": users_pending,
                "guests": users_guest,
            },
            "posts": {"total": sum(posts_by_status.values()), "by_status": posts_by_status},
            "audit_events": audit_total,
        },
        "scheduler": scheduler_state,
        "storage": {
            "reels": {"bytes": reels_bytes, "files": reels_files, "path": str(reels_path)},
            "uploads": {
                "bytes": uploads_bytes,
                "files": uploads_files,
                "path": str(uploads_path),
            },
            "disk": disk,
        },
        "features": {
            "linkedin_configured": linkedin_configured(),
            "instagram_configured": instagram_configured(),
            "guest_access": guest_access_enabled(),
            "new_signups": settings.allow_new_signups,
            "caption_assist": settings.enable_caption_generation,
            "admin_allowlist_pinned": bool(settings.admin_linkedin_subs.strip()),
        },
    }), 200


@console_bp.route("/guests", methods=["DELETE"])
def purge_guests():
    """Delete guest accounts and everything they own.

    Guests accumulate one row per visitor, so this is the housekeeping that
    keeps the user list readable. Their posts go too - a post whose owner no
    longer exists is unreachable by every route in the app, since all of them
    scope by user.
    """
    actor = current_user()
    db = get_session()
    try:
        guests = db.query(User).filter(User.is_guest.is_(True)).all()
        guest_ids = [g.id for g in guests]

        posts_removed = 0
        if guest_ids:
            posts_removed = (
                db.query(Post)
                .filter(Post.user_id.in_(guest_ids))
                .delete(synchronize_session=False)
            )
            for guest in guests:
                db.delete(guest)

        audit(
            db,
            action="console.guests_purged",
            actor=actor,
            target="guests",
            detail=f"{len(guest_ids)} account(s), {posts_removed} post(s)",
            ip_address=request.remote_addr,
        )
        db.commit()

        logger.info(f"Purged {len(guest_ids)} guest account(s)")
        return jsonify({
            "deleted_accounts": len(guest_ids),
            "deleted_posts": posts_removed,
        }), 200
    finally:
        db.close()


@console_bp.route("/storage/orphans", methods=["GET"])
def list_orphans():
    """Reel files on disk that no post refers to.

    Read-only on purpose. Deleting is a separate, explicit call, because "the
    database does not mention it" is a claim about the database, and a bug
    there would otherwise turn straight into data loss.
    """
    orphans, total_bytes = _find_orphans()
    return jsonify({
        "orphans": [{"path": p, "bytes": b} for p, b in orphans],
        "count": len(orphans),
        "bytes": total_bytes,
    }), 200


def _find_orphans():
    settings = get_settings()
    reels_root = Path(settings.reels_folder)
    if not reels_root.exists():
        return [], 0

    db = get_session()
    try:
        referenced = {
            Path(p).name for (p,) in db.query(Post.video_path).all() if p
        }
    finally:
        db.close()

    orphans, total = [], 0
    for entry in reels_root.rglob("*"):
        # Thumbnails belong to their video, so they are judged by it rather
        # than being reported as orphans in their own right.
        if not entry.is_file() or entry.suffix.lower() == ".jpg":
            continue
        if entry.name in referenced:
            continue
        try:
            size = entry.stat().st_size
        except OSError:
            continue
        orphans.append((str(entry), size))
        total += size

    return orphans, total


@console_bp.route("/storage/orphans", methods=["DELETE"])
def delete_orphans():
    """Remove orphaned reel files, and their thumbnails."""
    actor = current_user()
    orphans, total_bytes = _find_orphans()

    removed = 0
    for path_str, _ in orphans:
        path = Path(path_str)
        try:
            path.unlink()
            removed += 1
            thumbnail = path.with_suffix(".jpg")
            if thumbnail.exists():
                thumbnail.unlink()
        except OSError as e:
            logger.warning(f"Could not delete orphan {path}: {e}")

    db = get_session()
    try:
        audit(
            db,
            action="console.orphans_deleted",
            actor=actor,
            target="storage",
            detail=f"{removed} file(s), {total_bytes} bytes",
            ip_address=request.remote_addr,
        )
        db.commit()
    finally:
        db.close()

    logger.info(f"Deleted {removed} orphaned reel file(s)")
    return jsonify({"deleted": removed, "bytes": total_bytes}), 200
