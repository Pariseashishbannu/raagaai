"""Tala ORM model."""

from sqlalchemy import Column, String, Integer
from sqlalchemy.dialects.postgresql import JSONB
from src.db.base import Base


class Tala(Base):
    __tablename__ = "talas"

    id = Column(String(50), primary_key=True)
    name = Column(String(200), nullable=False)
    beats = Column(Integer, nullable=False)
    jathi = Column(String(20), nullable=False)
    structure = Column(JSONB, nullable=False)
