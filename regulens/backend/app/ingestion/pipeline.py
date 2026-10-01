"""FR-03 pipeline: file -> extract -> clean -> sections -> chunks -> embeddings -> pgvector -> requirements."""
import logging
import time

from app.ai.embeddings import embed_texts
from app.audit import service as audit
from app.compliance.extraction import extract_requirements
from app.core import metrics
from app.core.database import SessionLocal
from app.ingestion.chunker import build_chunks, clean_pages
from app.ingestion.parser import ParseError, parse_file
from app.models import Chunk, Document, Requirement, User

log = logging.getLogger("regulens.ingestion")


def process_document(doc_id: int, user_id: int | None = None):
    db = SessionLocal()
    t0 = time.perf_counter()
    try:
        doc = db.get(Document, doc_id)
        user = db.get(User, user_id) if user_id else None
        if not doc:
            return
        doc.status, doc.status_message = "processing", ""
        db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
        db.query(Requirement).filter(Requirement.document_id == doc.id).delete()
        db.commit()
        try:
            pages = clean_pages(parse_file(doc.file_path, doc.file_ext))
            chunks = build_chunks(pages)
            if not chunks:
                raise ParseError("The document contained no usable text after cleaning.")
            vecs = embed_texts([f"{c.heading}\n{c.text}" if c.heading else c.text for c in chunks])
            db.add_all([Chunk(document_id=doc.id, chunk_index=i, page=c.page, page_end=c.page_end,
                              section_number=c.section_number, heading=c.heading[:300], text=c.text, embedding=v)
                        for i, (c, v) in enumerate(zip(chunks, vecs))])
            doc.page_count = len(pages)
            db.commit()
            audit.log(db, "document.chunked", user, "document", doc.id, {"chunks": len(chunks)})

            msg = ""
            if doc.doc_type == "regulation":
                try:
                    n = extract_requirements(db, doc)
                    audit.log(db, "requirements.extracted", user, "document", doc.id, {"count": n})
                except Exception:
                    db.rollback()
                    log.exception("requirement extraction failed")
                    msg = "Document indexed, but requirement extraction failed. Use 'Re-process' to retry."
            doc.status, doc.status_message = "ready", msg
            db.commit()
        except ParseError as e:
            db.rollback()
            doc.status, doc.status_message = "failed", f"Document processing failed: {e}"
            db.commit()
            metrics.incr("document_failures")
            audit.log(db, "document.processing", user, "document", doc.id, {"error": str(e)}, "failure")
        except Exception as e:
            db.rollback()
            log.exception("processing failed")
            doc.status = "failed"
            doc.status_message = "Document processing failed unexpectedly. Please try again or contact an administrator."
            db.commit()
            metrics.incr("document_failures")
            audit.log(db, "document.processing", user, "document", doc.id, {"error": repr(e)}, "failure")
    finally:
        metrics.observe("ingestion_seconds", (time.perf_counter() - t0) * 1000)
        db.close()
