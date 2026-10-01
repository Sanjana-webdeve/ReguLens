"""FR-08/09/10/11: compare regulation requirements against an internal policy using retrieval + LLM judging."""
import logging

from sqlalchemy import select

from app.ai import llm
from app.ai.embeddings import embed_queries
from app.audit import service as audit
from app.compliance.risk import classify
from app.core.database import SessionLocal
from app.models import Comparison, ComparisonResult, Requirement, User
from app.retrieval.service import retrieve

log = logging.getLogger("regulens.comparison")
STATUSES = {"SATISFIED", "PARTIALLY_SATISFIED", "MISSING", "NOT_APPLICABLE"}
TOP_K = 4

SYSTEM = """You are a meticulous compliance reviewer. Decide whether the internal POLICY EXCERPTS satisfy the REGULATORY REQUIREMENT.
Statuses: SATISFIED (clearly and fully addressed), PARTIALLY_SATISFIED (addressed but vague/incomplete/missing an element),
MISSING (not addressed), NOT_APPLICABLE (requirement clearly does not apply to this kind of institution/policy).
Base your decision ONLY on the excerpts. Do not assume anything not written. Be conservative: if unsure choose PARTIALLY_SATISFIED."""


def _judge_llm(req: Requirement, hits) -> dict:
    ctx = "\n\n".join(f"[{i + 1}] (Section {h.chunk.section_number or 'n/a'}, Page {h.chunk.page})\n{h.chunk.text}"
                      for i, h in enumerate(hits))
    prompt = f"""REGULATORY REQUIREMENT ({req.code}, {req.category}, {'mandatory' if req.mandatory else 'optional'}):
{req.text}

POLICY EXCERPTS:
{ctx}

Return JSON: {{"status":"SATISFIED|PARTIALLY_SATISFIED|MISSING|NOT_APPLICABLE",
"best_source": <excerpt number or null>, "rationale":"1-3 sentences citing what the policy says or fails to say",
"recommendation":"if not satisfied: a concrete policy amendment, otherwise empty string"}}"""
    d = llm.generate_json(prompt)
    status = str(d.get("status", "")).upper().replace(" ", "_")
    if status not in STATUSES:
        raise llm.LLMUnavailable("invalid status from LLM")
    src = d.get("best_source")
    src = src if isinstance(src, int) and 1 <= src <= len(hits) else None
    if status in ("SATISFIED", "PARTIALLY_SATISFIED") and src is None:
        status, d["rationale"] = "MISSING", (d.get("rationale", "") + " (No supporting policy excerpt could be identified.)").strip()
    return {"status": status, "source": src, "rationale": d.get("rationale", ""),
            "recommendation": d.get("recommendation", "")}


def _judge_heuristic(req: Requirement, hits) -> dict:
    top = hits[0].score if hits else 0
    if top >= 0.78:
        status = "SATISFIED"
    elif top >= 0.62:
        status = "PARTIALLY_SATISFIED"
    else:
        status = "MISSING"
    rec = ""
    if status != "SATISFIED":
        rec = (f"Review the internal policy and add or clarify wording that explicitly addresses: {req.text[:250]}")
    return {"status": status, "source": 1 if hits and status != "MISSING" else None,
            "rationale": f"Heuristic semantic match (similarity {top:.2f}); AI reviewer unavailable, manual review advised.",
            "recommendation": rec}


def run_comparison(comparison_id: int, user_id: int | None):
    db = SessionLocal()
    try:
        comp = db.get(Comparison, comparison_id)
        user = db.get(User, user_id) if user_id else None
        reqs = db.scalars(select(Requirement).where(Requirement.document_id == comp.regulation_id)
                          .order_by(Requirement.id)).all()
        comp.total, comp.done, comp.used_llm = len(reqs), 0, llm.is_available()
        db.commit()
        qvecs = embed_queries([r.text for r in reqs]) if reqs else []
        use_llm = comp.used_llm
        for req, qv in zip(reqs, qvecs):
            hits = retrieve(db, req.text, TOP_K, document_ids=[comp.policy_id], query_vec=qv)
            judged, method = None, "heuristic"
            if use_llm and hits:
                try:
                    judged, method = _judge_llm(req, hits), "llm"
                except llm.LLMUnavailable:
                    use_llm = False
                    comp.used_llm = False
            if judged is None:
                judged = _judge_heuristic(req, hits) if hits else {
                    "status": "MISSING", "source": None, "rationale": "No policy content was retrieved.", "recommendation": ""}
            best = hits[judged["source"] - 1] if judged["source"] else None
            risk, score, factors = classify(judged["status"], req.mandatory, req.category, req.text)
            if judged["status"] in ("MISSING", "PARTIALLY_SATISFIED") and not judged["recommendation"]:
                judged["recommendation"] = f"Update the policy to explicitly address: {req.text[:250]}"
            res = ComparisonResult(
                comparison_id=comp.id, requirement_id=req.id, status=judged["status"],
                policy_chunk_id=best.chunk.id if best else None,
                policy_section=best.chunk.section_number if best else "", policy_page=best.chunk.page if best else 0,
                evidence_text=best.chunk.text[:1500] if best else "", rationale=judged["rationale"],
                recommendation=judged["recommendation"], risk=risk, risk_score=score, risk_factors=factors,
                similarity=hits[0].score if hits else 0, method=method)
            db.add(res)
            db.flush()
            if risk:
                res.gap_code = f"GAP-{res.id:04d}"
            comp.done += 1
            db.commit()
        comp.status = "completed"
        db.commit()
        audit.log(db, "comparison.completed", user, "comparison", comp.id, {"requirements": len(reqs), "llm": comp.used_llm})
    except Exception as e:
        log.exception("comparison failed")
        db.rollback()
        comp = db.get(Comparison, comparison_id)
        comp.status, comp.error = "failed", "The comparison failed unexpectedly. Please try again."
        db.commit()
        audit.log(db, "comparison.completed", None, "comparison", comparison_id, {"error": repr(e)}, "failure")
    finally:
        db.close()


def summarize(db, comp: Comparison) -> dict:
    results = db.scalars(select(ComparisonResult).where(ComparisonResult.comparison_id == comp.id)).all()
    c = {"SATISFIED": 0, "PARTIALLY_SATISFIED": 0, "MISSING": 0, "NOT_APPLICABLE": 0}
    for r in results:
        c[r.status] += 1
    applicable = len(results) - c["NOT_APPLICABLE"]
    pct = lambda n: round(100 * n / applicable, 1) if applicable else 0
    return {
        "total": len(results), "applicable": applicable, "counts": c,
        "satisfied_pct": pct(c["SATISFIED"]), "partial_pct": pct(c["PARTIALLY_SATISFIED"]), "missing_pct": pct(c["MISSING"]),
        "coverage_pct": round(100 * (c["SATISFIED"] + 0.5 * c["PARTIALLY_SATISFIED"]) / applicable, 1) if applicable else 0,
        "high_priority_gaps": sum(1 for r in results if r.risk == "HIGH"),
        "medium_gaps": sum(1 for r in results if r.risk == "MEDIUM"),
        "low_gaps": sum(1 for r in results if r.risk == "LOW"),
    }
