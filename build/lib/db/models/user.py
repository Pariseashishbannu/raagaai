"""User ORM model."""

import uuid
from sqlalchemy import Column, String, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from src.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    tier = Column(String(20), default="free")  # free|pro|studio|enterprise
    monthly_generations_used = Column(Integer, default=0)

    jobs = relationship("GenerationJob", back_populates="user", lazy="selectin")
    compositions = relationship("Composition", back_populates="user", lazy="selectin")
    cloud_training_jobs = relationship("CloudTrainingJob", back_populates="user", lazy="selectin")
