"""FR-04: extract compliance requirements from regulation chunks (LLM-structured when available, heuristic otherwise)."""
import logging
import re

from sqlalchemy.orm import Session

from app.ai import llm
from app.ai.embeddings import embed_texts
from app.models import Chunk, Document, Requirement

log = logging.getLogger("regulens.extraction")

CATEGORIES = ["KYC", "AML", "Customer Due Diligence", "Digital Banking", "Customer Protection", "Capital",
              "Liquidity", "Risk Management", "Governance", "Reporting", "Data & Privacy", "Other"]
MODAL = re.compile(r"\b(shall|must|should|required to|is required|are required|need to|obliged|prohibited|mandatory|may not)\b", re.I)
MANDATORY = re.compile(r"\b(shall|must|required|obliged|prohibited|mandatory|may not)\b", re.I)
KEYWORDS = {
    "KYC": ["kyc", "know your customer", "identification", "identity", "customer information", "re-kyc", "periodic updat"],
    "AML": ["money laundering", "suspicious", "terror", "str ", "aml", "cft"],
    "Customer Due Diligence": ["due diligence", "beneficial owner", "cdd", "edd", "risk categori"],
    "Digital Banking": ["digital", "online", "mobile", "internet banking", "video"],
    "Customer Protection": ["grievance", "complaint", "consumer", "customer protection", "redress", "liability"],
    "Capital": ["capital", "tier 1", "cet1", "leverage"],
    "Liquidity": ["liquidity", "lcr", "nsfr"],
    "Risk Management": ["risk management", "stress test", "operational risk", "credit risk"],
    "Governance": ["board", "committee", "senior management", "governance", "officer"],
    "Reporting": ["report", "submit", "disclos", "return"],
    "Data & Privacy": ["data", "privacy", "confidential", "retention", "record"],
}


def _category(text: str) -> str:
    t = text.lower()
    best, score = "Other", 0
    for cat, kws in KEYWORDS.items():
        s = sum(t.count(k) for k in kws)
        if s > score:
            best, score = cat, s
    return best


def _candidates(chunk: Chunk) -> list[str]:
    sents = re.split(r"(?<=[.;])\s+(?=[A-Z(\d])", chunk.text.replace("\n", " "))
    return [s.strip() for s in sents if 30 <= len(s.strip()) <= 700 and MODAL.search(s)]


def _structure_llm(batch: list[str]) -> list[dict | None]:
    items = "\n".join(f"{i}. {s}" for i, s in enumerate(batch))
    prompt = f"""You extract compliance requirements from regulatory text.
For each numbered sentence decide if it states an obligation/prohibition on a regulated entity.
Return JSON: {{"items":[{{"id":<number>,"is_requirement":true|false,"title":"<=10 word title",
"requirement":"one self-contained sentence restating the obligation","category":"one of {CATEGORIES}",
"mandatory":true|false}}]}}
Use mandatory=true for shall/must/required/prohibited and false for should/may/recommended.

SENTENCES:
{items}"""
    data = llm.generate_json(prompt)
    out: list[dict | None] = [None] * len(batch)
    for it in data.get("items", []):
        i = it.get("id")
        if isinstance(i, int) and 0 <= i < len(batch) and it.get("is_requirement"):
            if it.get("category") not in CATEGORIES:
                it["category"] = _category(batch[i])
            out[i] = it
    return out


def extract_requirements(db: Session, doc: Document) -> int:
    chunks = db.query(Chunk).filter(Chunk.document_id == doc.id).order_by(Chunk.chunk_index).all()
    cands = [(c, s) for c in chunks for s in _candidates(c)]
    use_llm = llm.is_available()
    structured: list[dict | None] = []
    for i in range(0, len(cands), 12):
        batch = [s for _, s in cands[i:i + 12]]
        res = None
        if use_llm:
            try:
                res = _structure_llm(batch)
            except llm.LLMUnavailable:
                log.warning("LLM unavailable during extraction; falling back to heuristics")
                use_llm = False
        if res is None:
            res = [{"title": s[:70], "requirement": s, "category": _category(s),
                    "mandatory": bool(MANDATORY.search(s)), "heuristic": True} for s in batch]
        structured.extend(res)

    seen, rows = set(), []
    for (chunk, sent), item in zip(cands, structured):
        if not item:
            continue
        text = item["requirement"].strip()
        key = re.sub(r"\W+", " ", text.lower())
        if key in seen:
            continue
        seen.add(key)
        rows.append(Requirement(
            document_id=doc.id, chunk_id=chunk.id, title=(item.get("title") or text)[:290], text=text,
            source_sentence=sent, category=item["category"], mandatory=bool(item["mandatory"]),
            section_number=chunk.section_number, page=chunk.page,
            method="heuristic" if item.get("heuristic") else "llm"))
    if not rows:
        return 0
    vecs = embed_texts([r.text for r in rows])
    for r, v in zip(rows, vecs):
        r.embedding = v
    db.add_all(rows)
    db.flush()
    for r in rows:
        r.code = f"REG-{r.id:05d}"
    db.commit()
    return len(rows)
