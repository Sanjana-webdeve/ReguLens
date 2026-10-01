from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import metrics
from app.core.database import get_db
from app.core.deps import ADMIN, AUDITOR, require_roles
from app.models import AuditLog

router = APIRouter(tags=["audit"])


@router.get("/audit")
def list_audit(action: str = "", username: str = "", limit: int = 100, offset: int = 0,
               db: Session = Depends(get_db), _=Depends(require_roles(ADMIN, AUDITOR))):
    q = select(AuditLog).order_by(AuditLog.id.desc())
    if action:
        q = q.where(AuditLog.action.ilike(f"%{action}%"))
    if username:
        q = q.where(AuditLog.username.ilike(f"%{username}%"))
    rows = db.scalars(q.limit(min(limit, 500)).offset(offset)).all()
    return [{"id": r.id, "time": r.created_at, "user": r.username, "action": r.action,
             "resource_type": r.resource_type, "resource_id": r.resource_id,
             "details": r.details, "result": r.result} for r in rows]


@router.get("/admin/metrics")
def get_metrics(_=Depends(require_roles(ADMIN))):
    return metrics.summary()
