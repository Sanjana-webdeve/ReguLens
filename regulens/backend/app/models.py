from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    doc_type: Mapped[str] = mapped_column(String(20), index=True)  # regulation | policy
    regulator: Mapped[str] = mapped_column(String(120), default="", index=True)  # RBI, Basel, or org name for policies
    category: Mapped[str] = mapped_column(String(120), default="", index=True)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    version: Mapped[str] = mapped_column(String(50), default="1")
    file_path: Mapped[str] = mapped_column(String(500))
    file_ext: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="processing")  # processing | ready | failed
    status_message: Mapped[str] = mapped_column(Text, default="")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    uploader = relationship("User")
    chunks = relationship("Chunk", cascade="all, delete-orphan", passive_deletes=True)
    requirements = relationship("Requirement", cascade="all, delete-orphan", passive_deletes=True)


class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    page: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    section_number: Mapped[str] = mapped_column(String(50), default="")
    heading: Mapped[str] = mapped_column(String(300), default="")
    text: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(Vector(settings.EMBEDDING_DIM))

    document = relationship("Document")


class Requirement(Base):
    __tablename__ = "requirements"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), default="", index=True)  # REG-00124
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text)
    source_sentence: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(100), default="Other")
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    section_number: Mapped[str] = mapped_column(String(50), default="")
    page: Mapped[int] = mapped_column(Integer, default=0)
    method: Mapped[str] = mapped_column(String(20), default="heuristic")  # llm | heuristic
    embedding = mapped_column(Vector(settings.EMBEDDING_DIM))

    document = relationship("Document")


class Comparison(Base):
    __tablename__ = "comparisons"
    id: Mapped[int] = mapped_column(primary_key=True)
    regulation_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    policy_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | completed | failed
    total: Mapped[int] = mapped_column(Integer, default=0)
    done: Mapped[int] = mapped_column(Integer, default=0)
    used_llm: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    regulation = relationship("Document", foreign_keys=[regulation_id])
    policy = relationship("Document", foreign_keys=[policy_id])
    results = relationship("ComparisonResult", cascade="all, delete-orphan", passive_deletes=True)


class ComparisonResult(Base):
    __tablename__ = "comparison_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    comparison_id: Mapped[int] = mapped_column(ForeignKey("comparisons.id", ondelete="CASCADE"), index=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("requirements.id", ondelete="CASCADE"))
    gap_code: Mapped[str] = mapped_column(String(20), default="")
    status: Mapped[str] = mapped_column(String(30))  # SATISFIED | PARTIALLY_SATISFIED | MISSING | NOT_APPLICABLE
    policy_chunk_id: Mapped[int | None] = mapped_column(ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True)
    policy_section: Mapped[str] = mapped_column(String(50), default="")
    policy_page: Mapped[int] = mapped_column(Integer, default=0)
    evidence_text: Mapped[str] = mapped_column(Text, default="")
    rationale: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(Text, default="")
    risk: Mapped[str | None] = mapped_column(String(10), nullable=True)  # HIGH | MEDIUM | LOW
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    risk_factors: Mapped[list] = mapped_column(JSON, default=list)
    similarity: Mapped[float] = mapped_column(Float, default=0)
    method: Mapped[str] = mapped_column(String(20), default="llm")

    requirement = relationship("Requirement")


class QAInteraction(Base):
    __tablename__ = "qa_interactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    evaluation: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    username: Mapped[str] = mapped_column(String(255), default="system")
    action: Mapped[str] = mapped_column(String(80), index=True)
    resource_type: Mapped[str] = mapped_column(String(50), default="")
    resource_id: Mapped[str] = mapped_column(String(50), default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[str] = mapped_column(String(20), default="success")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
