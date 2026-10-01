"""Hybrid retrieval: pgvector cosine + Postgres full-text, merged with reciprocal-rank fusion."""
import time
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.embeddings import embed_query
from app.core import metrics
from app.models import Chunk, Document


@dataclass
class Hit:
    chunk: Chunk
    document: Document
    score: float  # cosine similarity of the dense match (0..1)


def retrieve(db: Session, query: str, top_k: int = 6, document_ids: list[int] | None = None,
             doc_type: str | None = None, regulator: str | None = None, category: str | None = None,
             query_vec: list[float] | None = None) -> list[Hit]:
    t0 = time.perf_counter()
    qv = query_vec or embed_query(query)
    n = top_k * 3

    def base(stmt):
        stmt = stmt.join(Document, Document.id == Chunk.document_id).where(Document.status == "ready")
        if document_ids:
            stmt = stmt.where(Document.id.in_(document_ids))
        if doc_type:
            stmt = stmt.where(Document.doc_type == doc_type)
        if regulator:
            stmt = stmt.where(Document.regulator == regulator)
        if category:
            stmt = stmt.where(Document.category == category)
        return stmt

    dist = Chunk.embedding.cosine_distance(qv)
    dense = db.execute(base(select(Chunk, (1 - dist).label("sim"))).order_by(dist).limit(n)).all()
    ts = func.plainto_tsquery("english", query)
    vec = func.to_tsvector("english", Chunk.text)
    lexical = db.execute(base(select(Chunk, func.ts_rank(vec, ts).label("r")))
                         .where(vec.op("@@")(ts)).order_by(func.ts_rank(vec, ts).desc()).limit(n)).all()

    scores: dict[int, float] = {}
    sims: dict[int, float] = {}
    chunks: dict[int, Chunk] = {}
    for rank, (c, sim) in enumerate(dense):
        scores[c.id] = scores.get(c.id, 0) + 1 / (60 + rank)
        sims[c.id], chunks[c.id] = float(sim), c
    for rank, (c, _) in enumerate(lexical):
        scores[c.id] = scores.get(c.id, 0) + 1 / (60 + rank)
        chunks.setdefault(c.id, c)
    top = sorted(scores, key=scores.get, reverse=True)[:top_k]
    docs = {d.id: d for d in db.scalars(select(Document).where(Document.id.in_({chunks[i].document_id for i in top})))}
    metrics.observe("retrieval_latency", (time.perf_counter() - t0) * 1000)
    return [Hit(chunks[i], docs[chunks[i].document_id], sims.get(i, 0.0)) for i in top]
