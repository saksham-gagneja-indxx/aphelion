"""Audit log.

Records who did what. Exists because the moment a second person can use this
tool, "who published that post" and "who deactivated that account" stop being
rhetorical questions.

Design notes:

* `actor_name` is DENORMALISED on purpose. Joining to users would lose the
  record's meaning if that user is later deleted, and an audit trail that can
  be erased by deleting the actor is not an audit trail.
* `actor_id` is a plain integer, NOT a foreign key, for the same reason - the
  log must outlive the row it points at.
* Entries are append-only. Nothing in the application updates or deletes them.
"""

from sqlalchemy import Column, DateTime, Integer, String, Text

from backend.utils.database import Base
from backend.utils.timeutil import utcnow


class AuditLog(Base):
    """An append-only record of a consequential action."""

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)

    # Who. Denormalised so the entry survives the user being removed.
    actor_id = Column(Integer, nullable=True, index=True)
    actor_name = Column(String(255), nullable=True)

    # What. A stable machine-readable verb, e.g. "post.published",
    # "user.role_changed", "linkedin.connected".
    action = Column(String(100), nullable=False, index=True)

    # Which thing it happened to, e.g. "post:42" or "user:7".
    target = Column(String(255), nullable=True)

    # Free-form context. Never put tokens or secrets in here.
    detail = Column(Text, nullable=True)

    # Where from. Useful for spotting an access pattern that looks wrong.
    ip_address = Column(String(64), nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<AuditLog({self.action} by {self.actor_name} on {self.target})>"

    def to_dict(self):
        return {
            "id": self.id,
            "actor_id": self.actor_id,
            "actor_name": self.actor_name,
            "action": self.action,
            "target": self.target,
            "detail": self.detail,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def record(
    db,
    action: str,
    actor=None,
    target: str = None,
    detail: str = None,
    ip_address: str = None,
) -> None:
    """Append an audit entry.

    Deliberately swallows its own errors: an audit write must never be the
    reason a user-facing action fails. A missing log line is bad; a failed
    publish because logging broke is worse.
    """
    try:
        db.add(
            AuditLog(
                actor_id=getattr(actor, "id", None),
                actor_name=getattr(actor, "full_name", None)
                or getattr(actor, "email", None),
                action=action,
                target=target,
                detail=detail,
                ip_address=ip_address,
            )
        )
        db.flush()
    except Exception:  # pragma: no cover - best-effort by design
        from backend.utils.logger import get_logger

        get_logger("social_media_automation.audit").exception(
            f"Failed to write audit entry for action={action}"
        )
