from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.compliance.risk import DISCLAIMER
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import ComparisonResult, Document, Requirement

router = APIRouter(tags=["requirements"])


def req_out(r: Requirement, doc_name: str = "") -> dict:
    return {"id": r.id, "code": r.code, "title": r.title, "requirement": r.text, "category": r.category,
            "mandatory": r.mandatory, "source": doc_name or (r.document.name if r.document else ""),
            "document_id": r.document_id, "section": r.section_number, "page": r.page, "chunk_id": r.chunk_id,
            "method": r.method}


@router.get("/requirements")
def list_requirements(document_id: int | None = None, category: str = "", mandatory: bool | None = None,
                      q: str = "", limit: int = 200, offset: int = 0,
                      db: Session = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(Requirement, Document.name).join(Document, Document.id == Requirement.document_id)
    if document_id:
        stmt = stmt.where(Requirement.document_id == document_id)
    if category:
        stmt = stmt.where(Requirement.category == category)
    if mandatory is not None:
        stmt = stmt.where(Requirement.mandatory == mandatory)
    if q:
        stmt = stmt.where(Requirement.text.ilike(f"%{q}%"))
    rows = db.execute(stmt.order_by(Requirement.id).limit(min(limit, 500)).offset(offset)).all()
    return [req_out(r, n) for r, n in rows]


@router.get("/requirements/categories")
def categories(db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.execute(select(Requirement.category, func.count()).group_by(Requirement.category)).all()
    return [{"category": c, "count": n} for c, n in rows]


@router.get("/gaps")
def list_gaps(comparison_id: int | None = None, risk: str = "", status: str = "",
              db: Session = Depends(get_db), _=Depends(get_current_user)):
    """FR-09: gaps = results that are MISSING or PARTIALLY_SATISFIED."""
    stmt = select(ComparisonResult).where(ComparisonResult.status.in_(["MISSING", "PARTIALLY_SATISFIED"]))
    if comparison_id:
        stmt = stmt.where(ComparisonResult.comparison_id == comparison_id)
    if risk:
        stmt = stmt.where(ComparisonResult.risk == risk)
    if status:
        stmt = stmt.where(ComparisonResult.status == status)
    rows = db.scalars(stmt.order_by(ComparisonResult.risk_score.desc()).limit(500)).all()
    from app.comparison.router import result_out
    return {"disclaimer": DISCLAIMER, "gaps": [result_out(r) for r in rows]}
