# ReguLens – Regulatory Compliance Intelligence

Upload regulations → extract requirements → ask questions → retrieve evidence → compare policies → find gaps → export an auditable report.

**Stack:** React + Vite · FastAPI · PostgreSQL + pgvector · PyMuPDF · BGE embeddings (sentence-transformers) · Gemini · JWT · Docker

## Quick start (Docker)
```bash
cp .env.example .env        # then edit: SECRET_KEY, DB password, GEMINI_API_KEY
docker compose up --build
```
- App: http://localhost:5173  (log in with ADMIN_EMAIL / ADMIN_PASSWORD from `.env`)
- API docs: http://localhost:8000/docs

The first backend start downloads the embedding model (~130 MB) – wait for "Application startup complete".
Without `GEMINI_API_KEY` the app still works for upload, browse, search, retrieval and heuristic comparison; AI answers/judging are replaced by evidence-only fallbacks (NFR-09).

## Run without Docker
```bash
# 1) database
docker run -d --name regulens-db -p 5432:5432 -e POSTGRES_USER=regulens -e POSTGRES_PASSWORD=regulens -e POSTGRES_DB=regulens pgvector/pgvector:pg16
# 2) backend
cd backend && python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env   # set SECRET_KEY etc; DATABASE_URL defaults to localhost
uvicorn app.main:app --reload
# 3) frontend
cd ../frontend && npm install && npm run dev
```

## How it maps to the spec
| Spec | Where |
|---|---|
| FR-01 auth/roles | `backend/app/auth`, `core/deps.py` (JWT, revocable logout, reset tokens, roles) |
| FR-02/07 documents | `backend/app/documents` |
| FR-03 pipeline | `backend/app/ingestion` (parser → cleaner → section detector → chunker → embeddings → pgvector) |
| FR-04 requirements | `backend/app/compliance/extraction.py` |
| FR-05/06 Q&A + evidence | `backend/app/retrieval` (hybrid dense+full-text, RRF), `/qa`, `/evidence/{chunk}` |
| FR-08–11 compare/gaps/risk/recs | `backend/app/comparison`, `compliance/risk.py` |
| FR-12 dashboard / FR-13 search | `backend/app/dashboard`, `/search` |
| FR-14 reports (PDF/CSV/JSON) | `backend/app/reports` |
| FR-15 / NFR-07 audit | `backend/app/audit` |
| FR-16 AI evaluation | `backend/app/ai/evaluation.py` |
| FR-17/18 versions & change detection | `backend/app/versions` |
| NFR-10 metrics | `backend/scripts/eval_retrieval.py` (Precision@K, Recall@K, MRR) |
| NFR-12 observability | `core/metrics.py`, `GET /admin/metrics` |

## Roles
| Role | Can |
|---|---|
| admin | everything, user management, metrics |
| analyst | upload/delete documents, run comparisons, ask, reports |
| auditor | read everything, reports, audit trail |
| viewer | read-only (documents, requirements, Q&A, results, search) |
The first registered account becomes admin; later sign-ups are viewers until an admin changes their role.

## Design notes
- **Risk is rule-based and explained** (`compliance/risk.py`); the UI and reports state it is *not* a legal determination.
- **Coverage %** = (satisfied + 0.5 × partial) ÷ applicable requirements.
- **Auditability:** every finding stores the regulatory chunk, the matched policy chunk, the rationale and the method (`llm` or `heuristic`).
- **Production hardening to do:** Alembic migrations, a task queue (Celery/RQ) instead of FastAPI BackgroundTasks, OCR for scanned PDFs, email delivery for password reset (set `DEBUG_RETURN_RESET_TOKEN=false`), HTTPS and a reverse proxy, rate limiting, virus scanning on uploads, per-organisation document isolation.
- **Retrieval gold set:** write `goldset.json` (see `scripts/eval_retrieval.py`) and run it to report Precision@K / Recall@K / MRR; RAGAS can be added on top using the stored Q&A interactions.
