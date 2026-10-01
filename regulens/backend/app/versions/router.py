"""FR-17 / FR-18: document version management and regulation change detection."""
import re

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import llm
from app.audit import service as audit
from app.core.database import get_db
from app.core.deps import ADMIN, ANALYST, get_current_user, require_roles
from app.models import Document, Requirement, User

router = APIRouter(prefix="/versions", tags=["versions"])
UNCHANGED_T, MODIFIED_T = 0.97, 0.75


class DiffIn(BaseModel):
    old_id: int
    new_id: int


def _norm(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()


@router.get("/families")
def families(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Group regulation documents by regulator + name so versions can be listed together."""
    fam: dict = {}
    for d in db.scalars(select(Document).where(Document.doc_type == "regulation").order_by(Document.uploaded_at)):
        base = re.sub(r"[\s_-]*(v|version)?\s*\d+(\.\d+)*$", "", d.name.rsplit(".", 1)[0], flags=re.I).strip().lower()
        key = f"{d.regulator}|{base}"
        fam.setdefault(key, []).append({"id": d.id, "name": d.name, "version": d.version,
                                        "publication_date": d.publication_date, "status": d.status})
    return [{"key": k, "regulator": k.split("|")[0], "versions": v} for k, v in fam.items()]


@router.post("/diff")
def diff(body: DiffIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    old_d, new_d = db.get(Document, body.old_id), db.get(Document, body.new_id)
    if not old_d or not new_d:
        raise HTTPException(404, "Document not found.")
    old = db.scalars(select(Requirement).where(Requirement.document_id == old_d.id)).all()
    new = db.scalars(select(Requirement).where(Requirement.document_id == new_d.id)).all()
    if not old or not new:
        raise HTTPException(409, "Both versions need extracted requirements before they can be compared.")
    A = np.array([r.embedding for r in old], dtype=float)
    B = np.array([r.embedding for r in new], dtype=float)
    sim = B @ A.T  # embeddings are normalised -> cosine

    ref = lambda r: {"id": r.id, "code": r.code, "text": r.text, "section": r.section_number, "page": r.page,
                     "chunk_id": r.chunk_id}
    changes, matched_old = [], set()
    for i, r in enumerate(new):
        j = int(sim[i].argmax())
        s = float(sim[i, j])
        if s >= UNCHANGED_T or _norm(r.text) == _norm(old[j].text):
            kind = "UNCHANGED"
        elif s >= MODIFIED_T:
            kind = "MODIFIED"
        else:
            kind = "NEW"
        if kind != "NEW":
            matched_old.add(j)
        changes.append({"change": kind, "similarity": round(s, 3), "current": ref(r),
                        "previous": ref(old[j]) if kind != "NEW" else None, "summary": ""})
    for j, r in enumerate(old):
        if j not in matched_old and float(sim[:, j].max()) < MODIFIED_T:
            changes.append({"change": "REMOVED", "similarity": round(float(sim[:, j].max()), 3), "current": None,
                            "previous": ref(r), "summary": ""})

    if llm.is_available():  # one-line explanation of each modification (best effort)
        mods = [c for c in changes if c["change"] == "MODIFIED"][:20]
        if mods:
            try:
                items = "\n".join(f"{k}. OLD: {c['previous']['text']}\n   NEW: {c['current']['text']}" for k, c in enumerate(mods))
                data = llm.generate_json(f'For each pair, state in one short sentence what changed. '
                                         f'Return JSON {{"items":[{{"id":n,"summary":"..."}}]}}\n{items}')
                for it in data.get("items", []):
                    if isinstance(it.get("id"), int) and it["id"] < len(mods):
                        mods[it["id"]]["summary"] = it.get("summary", "")
            except llm.LLMUnavailable:
                pass

    order = {"NEW": 0, "MODIFIED": 1, "REMOVED": 2, "UNCHANGED": 3}
    changes.sort(key=lambda c: order[c["change"]])
    counts = {k: sum(1 for c in changes if c["change"] == k) for k in order}
    audit.log(db, "versions.diff", user, "document", new_d.id, {"old": old_d.id, "new": new_d.id, **counts})
    return {"old": {"id": old_d.id, "name": old_d.name, "version": old_d.version},
            "new": {"id": new_d.id, "name": new_d.name, "version": new_d.version},
            "counts": counts, "changes": changes}
