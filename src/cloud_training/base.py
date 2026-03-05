"""Base cloud training interface."""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Standard training configuration for cloud platforms."""

    # Model hyperparameters
    epochs: int = 50
    batch_size: int = 32
    learning_rate: float = 3e-4
    embed_dim: int = 128
    num_heads: int = 4
    num_layers: int = 4
    dropout: float = 0.1
    grad_clip: float = 1.0
    max_seq_len: int = 256
    val_split: float = 0.1
    patience: int = 10

    # Cloud configuration
    machine_type: str = "n1-standard-4"  # GCP machine type
    gpu_type: Optional[str] = "NVIDIA_TESLA_T4"  # GCP GPU type
    num_gpus: int = 1

    # Data configuration
    training_data_path: str = "data/training/svara_sequences.jsonl"
    output_model_dir: str = "gs://bucket/models"  # Will be overridden per platform

    # Monitoring
    tensorboard_prefix: str = "gs://bucket/tb-logs"
    checkpoint_prefix: str = "gs://bucket/checkpoints"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class BaseCloudTrainer(ABC):
    """Abstract base class for cloud trainers."""

    def __init__(self, config: TrainingConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def validate_credentials(self) -> bool:
        """Validate cloud credentials. Return True if valid."""
        pass

    @abstractmethod
    def upload_training_data(self, local_path: str, remote_path: str) -> bool:
        """Upload training data to cloud storage."""
        pass

    @abstractmethod
    def submit_training_job(self, job_name: str) -> str:
        """Submit training job to cloud. Return job ID."""
        pass

    @abstractmethod
    def get_job_status(self, job_id: str) -> dict:
        """Get training job status. Returns {'status': str, 'progress': float, ...}."""
        pass

    @abstractmethod
    def download_model(self, job_id: str, local_dir: str) -> bool:
        """Download trained model from cloud to local directory."""
        pass

    @abstractmethod
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running training job."""
        pass

    def get_training_command(self) -> str:
        """Get the training command to run on cloud."""
        return (
            f"python -m scripts.train_model "
            f"--epochs {self.config.epochs} "
            f"--batch-size {self.config.batch_size} "
            f"--lr {self.config.learning_rate} "
            f"--embed-dim {self.config.embed_dim} "
            f"--num-heads {self.config.num_heads} "
            f"--num-layers {self.config.num_layers} "
            f"--dropout {self.config.dropout} "
            f"--grad-clip {self.config.grad_clip} "
            f"--max-seq-len {self.config.max_seq_len} "
            f"--val-split {self.config.val_split} "
            f"--patience {self.config.patience}"
        )
