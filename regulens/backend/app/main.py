import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.ai import llm
from app.audit.router import router as audit_router
from app.auth.router import router as auth_router
from app.comparison.router import router as comparison_router
from app.compliance.router import router as requirements_router
from app.core import metrics
from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.core.security import hash_password
from app.dashboard.router import router as dashboard_router
from app.documents.router import router as documents_router
from app.models import Document, User
from app.reports.router import router as reports_router
from app.retrieval.router import router as qa_router
from app.versions.router import router as versions_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("regulens")


def bootstrap():
    db = SessionLocal()
    try:
        if settings.ADMIN_EMAIL and settings.ADMIN_PASSWORD and not db.scalar(select(func.count(User.id))):
            db.add(User(email=settings.ADMIN_EMAIL.lower(), full_name="Administrator",
                        password_hash=hash_password(settings.ADMIN_PASSWORD), role="admin"))
            db.commit()
            log.info("Created bootstrap admin %s", settings.ADMIN_EMAIL)
        if settings.RETENTION_DAYS > 0:  # configurable data retention (NFR-04)
            cutoff = datetime.utcnow() - timedelta(days=settings.RETENTION_DAYS)
            for d in db.scalars(select(Document).where(Document.uploaded_at < cutoff)).all():
                if os.path.exists(d.file_path):
                    os.remove(d.file_path)
                db.delete(d)
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    bootstrap()
    yield


app = FastAPI(title="ReguLens API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def timing(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    metrics.observe("api_latency", (time.perf_counter() - t0) * 1000)
    if response.status_code >= 500:
        metrics.incr("failed_requests")
    return response


@app.exception_handler(llm.LLMUnavailable)
async def llm_handler(request: Request, exc: llm.LLMUnavailable):
    return JSONResponse(status_code=503, content={"detail": "The AI service is temporarily unavailable. "
                                                            "Document browsing and search still work."})


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s", request.url.path)
    metrics.incr("failed_requests")
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side. Please try again."})


@app.get("/health")
def health():
    return {"status": "ok", "llm_configured": llm.is_available()}


for r in (auth_router, documents_router, requirements_router, qa_router, comparison_router, reports_router,
          versions_router, dashboard_router, audit_router):
    app.include_router(r)
