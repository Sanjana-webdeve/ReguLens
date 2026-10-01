from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import AuditLog, Comparison, ComparisonResult, Document, QAInteraction, Requirement

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _=Depends(get_current_user)):
    count = lambda m, *w: db.scalar(select(func.count(m.id)).where(*w)) or 0
    # latest completed comparison per (regulation, policy) pair
    latest = select(func.max(Comparison.id)).where(Comparison.status == "completed") \
        .group_by(Comparison.regulation_id, Comparison.policy_id)
    ids = [i for i in db.scalars(latest)]
    st = {"SATISFIED": 0, "PARTIALLY_SATISFIED": 0, "MISSING": 0, "NOT_APPLICABLE": 0}
    top = []
    if ids:
        for s, n in db.execute(select(ComparisonResult.status, func.count()).where(ComparisonResult.comparison_id.in_(ids))
                               .group_by(ComparisonResult.status)):
            st[s] = n
        rows = db.execute(select(ComparisonResult, Requirement).join(Requirement, Requirement.id == ComparisonResult.requirement_id)
                          .where(ComparisonResult.comparison_id.in_(ids), ComparisonResult.risk == "HIGH")
                          .order_by(ComparisonResult.risk_score.desc()).limit(8)).all()
        top = [{"gap_code": g.gap_code, "requirement": r.title or r.text[:90], "comparison_id": g.comparison_id,
                "status": g.status} for g, r in rows]
    applicable = sum(v for k, v in st.items() if k != "NOT_APPLICABLE")
    pct = lambda n: round(100 * n / applicable, 1) if applicable else 0
    qa = db.scalars(select(QAInteraction.evaluation).order_by(QAInteraction.id.desc()).limit(50)).all()
    qa = [e for e in qa if e]
    avg = lambda k: round(100 * sum(e.get(k, 0) for e in qa) / len(qa), 1) if qa else None
    recent = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(8)).all()
    return {
        "counts": {"regulations": count(Document, Document.doc_type == "regulation"),
                   "policies": count(Document, Document.doc_type == "policy"),
                   "requirements": count(Requirement), "comparisons": count(Comparison)},
        "status": st, "percent": {"satisfied": pct(st["SATISFIED"]), "partial": pct(st["PARTIALLY_SATISFIED"]),
                                   "missing": pct(st["MISSING"])},
        "top_gaps": top,
        "ai_quality": {"grounding": avg("grounding"), "citation_accuracy": avg("citation_accuracy"),
                       "relevance": avg("relevance"), "samples": len(qa)},
        "recent_activity": [{"time": r.created_at, "user": r.username, "action": r.action} for r in recent],
    }
