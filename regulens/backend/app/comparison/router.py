from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.comparison.service import run_comparison, summarize
from app.compliance.risk import DISCLAIMER
from app.core.database import get_db
from app.core.deps import ADMIN, ANALYST, get_current_user, require_roles
from app.models import Comparison, ComparisonResult, Document, User

router = APIRouter(prefix="/comparisons", tags=["comparison"])


class CompareIn(BaseModel):
    regulation_id: int
    policy_id: int


def comp_out(c: Comparison, summary: dict | None = None) -> dict:
    return {"id": c.id, "regulation_id": c.regulation_id, "policy_id": c.policy_id,
            "regulation": c.regulation.name, "policy": c.policy.name, "status": c.status, "total": c.total,
            "done": c.done, "used_llm": c.used_llm, "error": c.error, "created_at": c.created_at, "summary": summary}


def result_out(r: ComparisonResult) -> dict:
    q = r.requirement
    return {"id": r.id, "gap_code": r.gap_code, "comparison_id": r.comparison_id, "status": r.status,
            "requirement_id": q.id, "requirement_code": q.code, "requirement": q.text, "category": q.category,
            "mandatory": q.mandatory, "reg_section": q.section_number, "reg_page": q.page, "reg_chunk_id": q.chunk_id,
            "policy_section": r.policy_section, "policy_page": r.policy_page, "policy_chunk_id": r.policy_chunk_id,
            "evidence_text": r.evidence_text, "rationale": r.rationale, "recommendation": r.recommendation,
            "risk": r.risk, "risk_score": r.risk_score, "risk_factors": r.risk_factors,
            "similarity": round(r.similarity, 3), "method": r.method}


@router.post("", status_code=202)
def create(body: CompareIn, background: BackgroundTasks, db: Session = Depends(get_db),
           user: User = Depends(require_roles(ADMIN, ANALYST))):
    reg, pol = db.get(Document, body.regulation_id), db.get(Document, body.policy_id)
    if not reg or reg.doc_type != "regulation":
        raise HTTPException(400, "Select a valid regulation.")
    if not pol or pol.doc_type != "policy":
        raise HTTPException(400, "Select a valid internal policy.")
    if reg.status != "ready" or pol.status != "ready":
        raise HTTPException(409, "Both documents must finish processing before they can be compared.")
    comp = Comparison(regulation_id=reg.id, policy_id=pol.id, created_by=user.id)
    db.add(comp)
    db.commit()
    audit.log(db, "comparison.started", user, "comparison", comp.id,
              {"regulation": f"{reg.name} v{reg.version}", "policy": f"{pol.name} v{pol.version}"})
    background.add_task(run_comparison, comp.id, user.id)
    return comp_out(comp)


@router.get("")
def list_comparisons(db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.scalars(select(Comparison).order_by(Comparison.id.desc()).limit(100)).all()
    return [comp_out(c, summarize(db, c) if c.status == "completed" else None) for c in rows]


@router.get("/{comp_id}")
def get_comparison(comp_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    c = db.get(Comparison, comp_id)
    if not c:
        raise HTTPException(404, "Comparison not found.")
    return {**comp_out(c, summarize(db, c)), "disclaimer": DISCLAIMER}


@router.get("/{comp_id}/results")
def results(comp_id: int, status: str = "", risk: str = "", db: Session = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(ComparisonResult).where(ComparisonResult.comparison_id == comp_id)
    if status:
        stmt = stmt.where(ComparisonResult.status == status)
    if risk:
        stmt = stmt.where(ComparisonResult.risk == risk)
    return [result_out(r) for r in db.scalars(stmt.order_by(ComparisonResult.id)).all()]
