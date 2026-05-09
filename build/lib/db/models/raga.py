"""Raga ORM model."""

from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from src.db.base import Base


class Raga(Base):
    __tablename__ = "ragas"

    id = Column(String(100), primary_key=True)
    name_english = Column(String(200), nullable=False)
    name_telugu = Column(String(200), nullable=True)
    melakarta_number = Column(Integer, nullable=True)
    arohanam = Column(JSONB, nullable=False)
    avarohanam = Column(JSONB, nullable=False)
    varja_svaras = Column(JSONB, default=list)
    characteristic_phrases = Column(JSONB, default=list)
    gamaka_rules = Column(JSONB, default=dict)
    janya_of = Column(String(100), ForeignKey("ragas.id"), nullable=True)
    rasa_tags = Column(JSONB, default=list)
