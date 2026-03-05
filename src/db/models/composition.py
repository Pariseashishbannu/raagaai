"""Composition ORM model."""

import uuid
from sqlalchemy import Column, String, Integer, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from src.db.base import Base, TimestampMixin


class Composition(Base, TimestampMixin):
    __tablename__ = "compositions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("generation_jobs.id"), unique=True)
    raga_id = Column(String(100), ForeignKey("ragas.id"))
    tala_id = Column(String(50), ForeignKey("talas.id"))
    audio_key = Column(String(500))
    notation_key = Column(String(500), nullable=True)
    sahityam = Column(Text, nullable=True)
    svara_sequence = Column(JSONB)
    duration_seconds = Column(Integer)
    metadata_ = Column("metadata", JSONB, default=dict)
    is_public = Column(Boolean, default=False)

    user = relationship("User", back_populates="compositions")
    job = relationship("GenerationJob", back_populates="composition")
