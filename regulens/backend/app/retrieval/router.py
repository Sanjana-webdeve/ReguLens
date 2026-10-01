import re
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai import llm
from app.ai.evaluation import CITE_RE, evaluate
from app.audit import service as audit
from app.core import metrics
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Chunk, ComparisonResult, Document, QAInteraction, Requirement, User
from app.retrieval.service import retrieve

router = APIRouter(tags=["qa"])

SYSTEM = """You are ReguLens, a compliance assistant for financial institutions.
Answer ONLY from the numbered SOURCES. After every factual statement add the supporting source number like [1] or [2][3].
If the sources do not contain the answer, say so plainly. Never invent requirements, section numbers or page numbers.
Be concise and structured."""


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    document_ids: list[int] | None = None
    doc_type: str | None = None
    regulator: str | None = None
    top_k: int = Field(6, ge=1, le=12)


def cite_out(n: int, h) -> dict:
    return {"n": n, "chunk_id": h.chunk.id, "document_id": h.document.id, "document": h.document.name,
            "version": h.document.version, "doc_type": h.document.doc_type, "section": h.chunk.section_number,
            "heading": h.chunk.heading, "page": h.chunk.page, "score": round(h.score, 3),
            "snippet": h.chunk.text[:400]}


@router.post("/qa")
def ask(body: AskIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t0 = time.perf_counter()
    hits = retrieve(db, body.question, body.top_k, body.document_ids, body.doc_type, body.regulator)
    citations = [cite_out(i + 1, h) for i, h in enumerate(hits)]
    if not hits:
        return {"answer": "No relevant content was found. Upload and process documents first.", "citations": [],
                "evaluation": None, "llm_used": False}
    ctx = "\n\n".join(f"[{i + 1}] ({h.document.name} v{h.document.version}, Section {h.chunk.section_number or 'n/a'}, "
                      f"Page {h.chunk.page})\n{h.chunk.text}" for i, h in enumerate(hits))
    evaluation, llm_used = None, True
    try:
        answer = llm.generate(f"SOURCES:\n{ctx}\n\nQUESTION: {body.question}", system=SYSTEM)
        evaluation = evaluate(body.question, answer, [h.chunk.text for h in hits])
        used = {int(x) for x in CITE_RE.findall(answer)}
        for c in citations:
            c["cited"] = c["n"] in used
    except llm.LLMUnavailable:
        llm_used = False
        answer = ("The AI assistant is currently unavailable, so no generated answer is shown. "
                  "The most relevant passages from your documents are listed below as evidence.")
        metrics.incr("qa_degraded")
    metrics.observe("qa_latency", (time.perf_counter() - t0) * 1000)
    db.add(QAInteraction(user_id=user.id, question=body.question, answer=answer, citations=citations,
                         evaluation=evaluation or {}))
    db.commit()
    audit.log(db, "qa.ask", user, "qa", "", {"question": body.question[:200], "sources": len(hits), "llm": llm_used})
    return {"answer": answer, "citations": citations, "evaluation": evaluation, "llm_used": llm_used}


@router.get("/qa/history")
def history(limit: int = 20, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(QAInteraction).where(QAInteraction.user_id == user.id)
                      .order_by(QAInteraction.id.desc()).limit(limit)).all()
    return [{"id": r.id, "question": r.question, "answer": r.answer, "citations": r.citations,
             "evaluation": r.evaluation, "created_at": r.created_at} for r in rows]


@router.get("/evidence/{chunk_id}")
def evidence(chunk_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """FR-06: click Source -> Section -> Page and view the underlying text (with neighbouring chunks for context)."""
    c = db.get(Chunk, chunk_id)
    if not c:
        raise HTTPException(404, "Evidence not found. The document may have been deleted.")
    d = db.get(Document, c.document_id)
    neigh = db.scalars(select(Chunk).where(Chunk.document_id == c.document_id,
                                           Chunk.chunk_index.in_([c.chunk_index - 1, c.chunk_index + 1]))
                       .order_by(Chunk.chunk_index)).all()
    f = lambda x: {"id": x.id, "section": x.section_number, "page": x.page, "text": x.text}
    return {"chunk": {**f(c), "heading": c.heading, "page_end": c.page_end},
            "document": {"id": d.id, "name": d.name, "version": d.version, "regulator": d.regulator,
                         "doc_type": d.doc_type, "file_ext": d.file_ext},
            "before": [f(x) for x in neigh if x.chunk_index < c.chunk_index],
            "after": [f(x) for x in neigh if x.chunk_index > c.chunk_index]}


@router.get("/search")
def search(q: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """FR-13: search regulations, policies, requirements, sections and gaps."""
    q = q.strip()
    if len(q) < 2:
        return {"documents": [], "sections": [], "requirements": [], "gaps": []}
    like = f"%{re.sub(r'[%_]', '', q)}%"
    docs = db.scalars(select(Document).where(or_(Document.name.ilike(like), Document.regulator.ilike(like),
                                                 Document.category.ilike(like))).limit(10)).all()
    hits = retrieve(db, q, top_k=10)
    reqs = db.scalars(select(Requirement).where(or_(Requirement.text.ilike(like), Requirement.code.ilike(like),
                                                    Requirement.title.ilike(like))).limit(15)).all()
    gaps = db.execute(select(ComparisonResult, Requirement).join(Requirement, Requirement.id == ComparisonResult.requirement_id)
                      .where(ComparisonResult.status.in_(["MISSING", "PARTIALLY_SATISFIED"]),
                             or_(Requirement.text.ilike(like), ComparisonResult.rationale.ilike(like)))
                      .order_by(ComparisonResult.id.desc()).limit(15)).all()
    return {
        "documents": [{"id": d.id, "name": d.name, "doc_type": d.doc_type, "regulator": d.regulator,
                       "category": d.category, "version": d.version} for d in docs],
        "sections": [{**cite_out(i + 1, h), "text": h.chunk.text[:300]} for i, h in enumerate(hits)],
        "requirements": [{"id": r.id, "code": r.code, "title": r.title, "text": r.text, "section": r.section_number,
                          "page": r.page, "chunk_id": r.chunk_id} for r in reqs],
        "gaps": [{"id": g.id, "gap_code": g.gap_code, "comparison_id": g.comparison_id, "status": g.status,
                  "risk": g.risk, "requirement": r.text} for g, r in gaps],
    }
