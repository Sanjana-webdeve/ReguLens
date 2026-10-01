import os
import uuid
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import ADMIN, ANALYST, get_current_user, require_roles
from app.ingestion.pipeline import process_document
from app.models import Document, User

router = APIRouter(prefix="/documents", tags=["documents"])

MAGIC = {"pdf": b"%PDF", "docx": b"PK\x03\x04"}
ALLOWED = {"pdf", "docx", "txt"}


def doc_out(d: Document) -> dict:
    return {"id": d.id, "name": d.name, "doc_type": d.doc_type, "regulator": d.regulator, "category": d.category,
            "publication_date": d.publication_date, "version": d.version, "status": d.status,
            "status_message": d.status_message, "page_count": d.page_count, "file_ext": d.file_ext,
            "uploaded_at": d.uploaded_at, "uploaded_by": d.uploader.full_name if d.uploader else None}


@router.post("", status_code=201)
async def upload(background: BackgroundTasks, file: UploadFile = File(...), doc_type: str = Form("regulation"),
                 regulator: str = Form(""), category: str = Form(""), version: str = Form("1"),
                 publication_date: date | None = Form(None), name: str = Form(""),
                 db: Session = Depends(get_db), user: User = Depends(require_roles(ADMIN, ANALYST))):
    if doc_type not in ("regulation", "policy"):
        raise HTTPException(400, "doc_type must be 'regulation' or 'policy'.")
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        raise HTTPException(400, "Unsupported file type. Upload a PDF, DOCX or TXT file.")
    data = await file.read()
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {settings.MAX_UPLOAD_MB} MB.")
    if not data:
        raise HTTPException(400, "The uploaded file is empty.")
    if ext in MAGIC and not data.startswith(MAGIC[ext]):
        raise HTTPException(400, f"The file content does not look like a valid .{ext} file.")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4().hex}.{ext}")  # never trust the client filename for paths
    with open(path, "wb") as f:
        f.write(data)
    doc = Document(name=(name or file.filename or "Untitled")[:500], doc_type=doc_type, regulator=regulator.strip(),
                   category=category.strip(), version=version.strip() or "1", publication_date=publication_date,
                   file_path=path, file_ext=ext, uploaded_by=user.id, status="processing")
    db.add(doc)
    db.commit()
    audit.log(db, "document.upload", user, "document", doc.id,
              {"name": doc.name, "type": doc_type, "version": doc.version, "regulator": doc.regulator})
    background.add_task(process_document, doc.id, user.id)
    return doc_out(doc)


@router.get("")
def list_documents(doc_type: str = "", regulator: str = "", category: str = "", q: str = "",
                   db: Session = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(Document).order_by(Document.id.desc())
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)
    if regulator:
        stmt = stmt.where(Document.regulator == regulator)
    if category:
        stmt = stmt.where(Document.category == category)
    if q:
        stmt = stmt.where(Document.name.ilike(f"%{q}%"))
    return [doc_out(d) for d in db.scalars(stmt).all()]


@router.get("/tree")
def tree(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Regulator -> Category -> documents, as in FR-02."""
    out: dict = {}
    for d in db.scalars(select(Document).where(Document.doc_type == "regulation").order_by(Document.name)):
        out.setdefault(d.regulator or "Uncategorised", {}).setdefault(d.category or "General", []).append(
            {"id": d.id, "name": d.name, "version": d.version})
    return out


@router.get("/{doc_id}")
def get_document(doc_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "Document not found.")
    return doc_out(d)


@router.get("/{doc_id}/file")
def download(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    d = db.get(Document, doc_id)
    if not d or not os.path.exists(d.file_path):
        raise HTTPException(404, "File not found.")
    audit.log(db, "document.download", user, "document", d.id)
    return FileResponse(d.file_path, filename=f"{d.name}", media_type="application/octet-stream")


@router.post("/{doc_id}/reprocess")
def reprocess(doc_id: int, background: BackgroundTasks, db: Session = Depends(get_db),
              user: User = Depends(require_roles(ADMIN, ANALYST))):
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "Document not found.")
    d.status = "processing"
    db.commit()
    audit.log(db, "document.reprocess", user, "document", d.id)
    background.add_task(process_document, d.id, user.id)
    return doc_out(d)


@router.delete("/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(ADMIN, ANALYST))):
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "Document not found.")
    path, name = d.file_path, d.name
    db.delete(d)
    db.commit()
    if os.path.exists(path):
        os.remove(path)
    audit.log(db, "document.delete", user, "document", doc_id, {"name": name})
    return {"ok": True}
