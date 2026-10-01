"""NFR-10 offline retrieval evaluation: Precision@K, Recall@K, MRR.

Usage (inside the backend container or venv):
  python scripts/eval_retrieval.py goldset.json 5

goldset.json:
[{"question": "What are the requirements for customer due diligence?",
  "relevant": [{"document_id": 1, "section": "10.2"}]}]
A hit is relevant if its (document_id, section_number) is listed.
"""
import json
import sys

sys.path.insert(0, ".")
from app.core.database import SessionLocal  # noqa: E402
from app.retrieval.service import retrieve  # noqa: E402


def main(path: str, k: int):
    gold = json.load(open(path))
    db = SessionLocal()
    p_sum = r_sum = rr_sum = 0.0
    for g in gold:
        rel = {(x["document_id"], x["section"]) for x in g["relevant"]}
        hits = retrieve(db, g["question"], top_k=k)
        flags = [(h.document.id, h.chunk.section_number) in rel for h in hits]
        found = len({(h.document.id, h.chunk.section_number) for h, f in zip(hits, flags) if f})
        p_sum += sum(flags) / k
        r_sum += found / len(rel) if rel else 0
        rr_sum += next((1 / (i + 1) for i, f in enumerate(flags) if f), 0)
    n = len(gold)
    print(f"Questions: {n}\nPrecision@{k}: {p_sum / n:.3f}\nRecall@{k}: {r_sum / n:.3f}\nMRR: {rr_sum / n:.3f}")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 5)
