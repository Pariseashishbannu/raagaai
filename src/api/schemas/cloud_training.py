"""API schemas for cloud training endpoints."""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from uuid import UUID


class CloudPlatform(str, Enum):
    """Supported cloud platforms."""
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"


class CloudTrainingConfig(BaseModel):
    """Training hyperparameters."""
    epochs: int = Field(default=50, ge=1, le=500)
    batch_size: int = Field(default=32, ge=1, le=256)
    learning_rate: float = Field(default=3e-4, ge=1e-6, le=1e-1)
    embed_dim: int = Field(default=128, ge=64, le=512)
    num_heads: int = Field(default=4, ge=1, le=16)
    num_layers: int = Field(default=4, ge=1, le=12)
    dropout: float = Field(default=0.1, ge=0.0, le=0.5)
    grad_clip: float = Field(default=1.0, ge=0.1, le=10.0)
    max_seq_len: int = Field(default=256, ge=64, le=1024)
    val_split: float = Field(default=0.1, ge=0.01, le=0.5)
    patience: int = Field(default=10, ge=1, le=100)

    class Config:
        json_schema_extra = {
            "example": {
                "epochs": 50,
                "batch_size": 32,
                "learning_rate": 0.0003,
                "embed_dim": 128,
                "num_heads": 4,
                "num_layers": 4,
            }
        }


class CloudTrainingRequest(BaseModel):
    """Request to submit a cloud training job."""
    
    platform: CloudPlatform = Field(description="Target cloud platform")
    job_name: str = Field(desc="User-friendly name for the job", min_length=1, max_length=200)
    config: CloudTrainingConfig = Field(default_factory=CloudTrainingConfig)
    
    # Platform-specific configuration (optional)
    platform_config: dict | None = Field(
        default=None, 
        description="Platform-specific settings (AWS: instance_type, GCP: region, Azure: compute_target)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "platform": "gcp",
                "job_name": "raaga-model-v2-experiment-1",
                "config": {
                    "epochs": 50,
                    "batch_size": 32,
                    "learning_rate": 0.0003,
                },
                "platform_config": {
                    "region": "us-central1",
                    "machine_type": "n1-standard-4",
                }
            }
        }


class CloudTrainingResponse(BaseModel):
    """Response after submitting a cloud training job."""
    
    job_id: UUID = Field(description="Raaga.AI job ID (UUID)")
    cloud_job_id: str | None = Field(default=None, description="Cloud platform job ID/ARN")
    platform: CloudPlatform
    status: str = Field(description="Initial status (usually 'submitted')")
    message: str = Field(description="Confirmation message")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "cloud_job_id": None,
                "platform": "gcp",
                "status": "submitted",
                "message": "Job submitted successfully. Check status via GET /api/v1/training/cloud/{job_id}"
            }
        }


class CloudTrainingJobStatus(BaseModel):
    """Status of a cloud training job."""
    
    job_id: UUID
    platform: CloudPlatform
    status: str = Field(description="Job status: submitted|queued|running|completed|failed|cancelled")
    progress: float = Field(ge=0.0, le=1.0, description="Progress from 0.0 to 1.0")
    current_stage: str | None = Field(description="Current training stage (e.g., 'training', 'finalizing')")
    
    # Cloud platform references
    cloud_job_id: str | None = Field(description="Job ID on cloud platform")
    platform_logs_url: str | None = Field(description="URL to view logs on cloud platform")
    
    # Timing
    submitted_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    
    # Results
    metrics: dict | None = Field(description="Training metrics: {val_loss, training_time, etc.}")
    model_download_url: str | None = Field(description="URL to download trained model")
    error_message: str | None = Field(description="Error details if job failed")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "platform": "gcp",
                "status": "running",
                "progress": 0.45,
                "current_stage": "training",
                "cloud_job_id": "projects/my-project/locations/us-central1/customJobs/1234567890",
                "platform_logs_url": "https://console.cloud.google.com/vertex-ai/...",
                "metrics": {
                    "epochs_completed": 22,
                    "current_val_loss": 0.482,
                },
                "model_download_url": None,
                "error_message": None
            }
        }


class CloudTrainingListItem(BaseModel):
    """Brief summary of a cloud training job for list endpoints."""
    
    job_id: UUID
    platform: CloudPlatform
    job_name: str
    status: str
    progress: float
    submitted_at: datetime
    completed_at: datetime | None

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "platform": "gcp",
                "job_name": "raaga-model-v2",
                "status": "running",
                "progress": 0.45,
                "submitted_at": "2026-03-04T10:30:00Z",
                "completed_at": None
            }
        }


class CloudTrainingListResponse(BaseModel):
    """List of cloud training jobs."""
    
    jobs: list[CloudTrainingListItem]
    total: int = Field(description="Total number of jobs")
    offset: int = Field(description="Pagination offset")
    limit: int = Field(description="Pagination limit")


class ModelDownloadInfo(BaseModel):
    """Information for downloading trained model."""
    
    job_id: UUID
    status: str
    download_url: str | None = Field(description="Signed URL for downloading model.pt")
    expiry_time: datetime | None = Field(description="When the download URL expires")
    file_size_mb: float | None = Field(description="Size of the model file in MB")
    message: str = Field(description="Status message")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "status": "completed",
                "download_url": "https://storage.googleapis.com/my-bucket/models/svara_transformer.pt?...",
                "expiry_time": "2026-03-11T10:30:00Z",
                "file_size_mb": 125.5,
                "message": "Model ready for download"
            }
        }
