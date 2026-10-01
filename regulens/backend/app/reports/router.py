import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.core.database import get_db
from app.core.deps import ADMIN, ANALYST, AUDITOR, require_roles
from app.models import Comparison, User
from app.reports.generator import build_report, to_csv, to_pdf

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{comp_id}")
def get_report(comp_id: int, format: str = "json", db: Session = Depends(get_db),
               user: User = Depends(require_roles(ADMIN, ANALYST, AUDITOR))):
    comp = db.get(Comparison, comp_id)
    if not comp or comp.status != "completed":
        raise HTTPException(404, "Completed comparison not found.")
    if format not in ("json", "csv", "pdf"):
        raise HTTPException(400, "format must be json, csv or pdf.")
    report = build_report(db, comp)
    audit.log(db, "report.generate", user, "comparison", comp.id, {"format": format})
    fname = f"regulens_report_{comp.id}"
    if format == "json":
        return Response(json.dumps(report, default=str, indent=2), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{fname}.json"'})
    if format == "csv":
        return Response(to_csv(report), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{fname}.csv"'})
    return Response(to_pdf(report), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}.pdf"'})
