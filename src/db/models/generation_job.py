"""GenerationJob ORM model."""

import uuid
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from src.db.base import Base, TimestampMixin


class GenerationJob(Base, TimestampMixin):
    __tablename__ = "generation_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    raga_id = Column(String(100), ForeignKey("ragas.id"), nullable=False)
    tala_id = Column(String(50), ForeignKey("talas.id"), nullable=False)
    kala = Column(String(20), default="madhyama")
    language = Column(String(20), default="telugu")
    theme = Column(String(100), nullable=True)
    sections = Column(Integer, default=3)
    include_chittaswaram = Column(String(5), default="false")
    status = Column(String(20), default="queued", index=True)
    current_stage = Column(String(50), nullable=True)
    progress = Column(Float, default=0.0)
    checkpoints = Column(JSONB, default=dict)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="jobs")
    composition = relationship("Composition", back_populates="job", uselist=False)
