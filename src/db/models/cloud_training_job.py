"""CloudTrainingJob ORM model for tracking model training on cloud platforms."""

import uuid
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from src.db.base import Base, TimestampMixin


class CloudTrainingJob(Base, TimestampMixin):
    """Tracks SvaraTransformer training jobs submitted to cloud platforms."""

    __tablename__ = "cloud_training_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Platform and job tracking
    platform = Column(String(20), nullable=False)  # "aws", "gcp", "azure"
    cloud_job_id = Column(String(500), nullable=True, index=True)  # Remote job ID/ARN
    platform_logs_url = Column(String(500), nullable=True)  # CloudWatch, Cloud Logging, etc.
    platform_model_uri = Column(String(500), nullable=True)  # S3, GCS, Azure Blob URI

    # Job metadata
    job_name = Column(String(200), nullable=False)  # User-friendly name
    status = Column(String(20), default="submitted", index=True)  # submitted|queued|running|completed|failed|cancelled
    progress = Column(Float, default=0.0)  # 0.0-1.0
    current_stage = Column(String(100), nullable=True)  # "preparing_data", "initializing_model", "training", "finalizing"

    # Training configuration (stored as JSONB for flexibility)
    config_json = Column(JSONB, default=dict)  # {epochs, batch_size, lr, embed_dim, num_heads, num_layers, ...}

    # Results and errors
    model_download_url = Column(String(500), nullable=True)  # URL to download trained model
    metrics = Column(JSONB, default=dict)  # {final_val_loss, best_val_loss, training_time_seconds, ...}
    error_message = Column(Text, nullable=True)

    # Timing
    submitted_at = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Optional: store encrypted credentials if per-user (security consideration)
    # For now, credentials come from env vars or config
    use_custom_credentials = Column(Boolean, default=False)

    # Relationships
    user = relationship("User", back_populates="cloud_training_jobs")

    def __repr__(self) -> str:
        return f"<CloudTrainingJob(id={self.id}, platform={self.platform}, status={self.status})>"
