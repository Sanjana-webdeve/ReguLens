import csv
import io
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.comparison.router import result_out
from app.comparison.service import summarize
from app.compliance.risk import DISCLAIMER
from app.models import Comparison, ComparisonResult


def build_report(db: Session, comp: Comparison, org: str = "") -> dict:
    results = db.scalars(select(ComparisonResult).where(ComparisonResult.comparison_id == comp.id)
                         .order_by(ComparisonResult.risk_score.desc(), ComparisonResult.id)).all()
    return {
        "title": "Compliance Assessment Report",
        "organization": org or comp.policy.regulator or "",
        "regulation": f"{comp.regulation.name} (v{comp.regulation.version})",
        "policy": f"{comp.policy.name} (v{comp.policy.version})",
        "assessment_date": (comp.created_at or datetime.utcnow()).strftime("%d-%m-%Y"),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "analysis_method": "LLM-assisted with retrieval evidence" if comp.used_llm else "Heuristic semantic matching (AI reviewer unavailable)",
        "disclaimer": DISCLAIMER,
        "summary": summarize(db, comp),
        "findings": [result_out(r) for r in results],
    }


def to_csv(report: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    cols = ["gap_code", "requirement_code", "requirement", "category", "mandatory", "status", "risk", "reg_section",
            "reg_page", "policy_section", "policy_page", "rationale", "recommendation", "method"]
    w.writerow(cols)
    for f in report["findings"]:
        w.writerow([f.get(c, "") for c in cols])
    return buf.getvalue()


def to_pdf(report: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape as esc

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36,
                            title=report["title"])
    st = getSampleStyleSheet()
    small = st["BodyText"].clone("small", fontSize=8, leading=10)
    s = report["summary"]
    el = [Paragraph(report["title"], st["Title"]),
          Paragraph(f"<b>Organization:</b> {esc(report['organization'])}<br/><b>Regulation:</b> {esc(report['regulation'])}<br/>"
                    f"<b>Policy:</b> {esc(report['policy'])}<br/><b>Assessment date:</b> {report['assessment_date']}<br/>"
                    f"<b>Method:</b> {esc(report['analysis_method'])}", st["BodyText"]), Spacer(1, 10)]
    t = Table([["Overall coverage", f"{s['coverage_pct']}%"], ["Satisfied", f"{s['satisfied_pct']}%"],
               ["Partially satisfied", f"{s['partial_pct']}%"], ["Missing", f"{s['missing_pct']}%"],
               ["High-priority gaps", s["high_priority_gaps"]]], colWidths=[200, 100])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke)]))
    el += [t, Spacer(1, 6), Paragraph(f"<i>{esc(report['disclaimer'])}</i>", small), Spacer(1, 12),
           Paragraph("Detailed findings", st["Heading2"])]
    rows = [["Ref", "Requirement", "Status / Risk", "Regulatory evidence", "Policy coverage"]]
    for f in report["findings"]:
        rows.append([
            Paragraph(esc(f"{f['gap_code'] or f['requirement_code']}"), small),
            Paragraph(esc(f["requirement"][:350]), small),
            Paragraph(esc(f"{f['status'].replace('_', ' ')}<br/>{f['risk'] or ''}".replace("<br/>", " / ")), small),
            Paragraph(esc(f"Sec {f['reg_section'] or '-'}, p.{f['reg_page']}"), small),
            Paragraph(esc(f"Sec {f['policy_section'] or '-'}, p.{f['policy_page']}" if f["policy_chunk_id"] else "Not found"), small)])
    ft = Table(rows, colWidths=[55, 250, 80, 75, 75], repeatRows=1)
    ft.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                            ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el.append(ft)
    gaps = [f for f in report["findings"] if f["risk"]]
    if gaps:
        el += [Spacer(1, 12), Paragraph("Recommendations", st["Heading2"])]
        for f in gaps:
            el.append(Paragraph(f"<b>{esc(f['gap_code'])} ({f['risk']})</b>: {esc(f['recommendation'])}<br/>"
                                f"<i>Regulatory basis: Sec {esc(f['reg_section'] or '-')}, page {f['reg_page']}</i>", small))
            el.append(Spacer(1, 4))
    doc.build(el)
    return buf.getvalue()
