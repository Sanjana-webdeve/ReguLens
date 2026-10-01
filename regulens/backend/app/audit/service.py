import logging

from sqlalchemy.orm import Session

from app.models import AuditLog

log_ = logging.getLogger("regulens.audit")


def log(db: Session, action: str, user=None, resource_type: str = "", resource_id="", details: dict | None = None,
        result: str = "success"):
    """WHO / WHAT / WHEN / DOCUMENT / VERSION / ACTION / RESULT (NFR-07). Never raises."""
    try:
        db.add(AuditLog(
            user_id=getattr(user, "id", None),
            username=getattr(user, "email", None) or "system",
            action=action, resource_type=resource_type, resource_id=str(resource_id),
            details=details or {}, result=result,
        ))
        db.commit()
    except Exception:  # audit failure must not break the request
        db.rollback()
        log_.exception("audit write failed")
