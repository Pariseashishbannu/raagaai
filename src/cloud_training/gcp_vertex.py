"""Google Cloud Platform Vertex AI training adapter."""

import logging
from typing import Optional

from src.cloud_training.base import TrainingConfig, BaseCloudTrainer

logger = logging.getLogger(__name__)


class VertexAITrainer(BaseCloudTrainer):
    """Google Cloud Vertex AI training adapter."""

    def __init__(config: TrainingConfig, project_id: str, bucket: str, region: str = "us-central1"):
        """Initialize Vertex AI trainer.

        Args:
            config: Training configuration
            project_id: GCP project ID
            bucket: GCS bucket for training data and models
            region: GCP region for training
        """
        super().__init__(config)
        self.project_id = project_id
        self.bucket = bucket
        self.region = region
        self.config.output_model_dir = f"gs://{bucket}/models"
        self.config.checkpoint_prefix = f"gs://{bucket}/checkpoints"
        self.config.tensorboard_prefix = f"gs://{bucket}/tb-logs"

        try:
            from google.cloud import aiplatform, storage
            from google.oauth2 import service_account

            self.aiplatform = aiplatform
            self.storage = storage
            aiplatform.init(project=project_id, location=region)
            self.gcs_client = storage.Client(project=project_id)
        except ImportError:
            raise ImportError(
                "google-cloud-aiplatform is required. Install with: "
                "pip install google-cloud-aiplatform google-cloud-storage"
            )

    def validate_credentials(self) -> bool:
        """Validate GCP credentials."""
        try:
            self.aiplatform.match_model_names([])
            logger.info("✓ GCP credentials validated")
            return True
        except Exception as e:
            logger.error(f"✗ GCP credential validation failed: {e}")
            return False

    def upload_training_data(self, local_path: str, remote_path: str) -> bool:
        """Upload training data to GCS."""
        try:
            bucket = self.gcs_client.bucket(self.bucket)
            blob = bucket.blob(remote_path)
            blob.upload_from_filename(local_path)
            logger.info(f"✓ Uploaded {local_path} to gs://{self.bucket}/{remote_path}")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to upload training data: {e}")
            return False

    def submit_training_job(self, job_name: str) -> str:
        """Submit training job to Vertex AI."""
        try:
            container_image_uri = (
                f"us-docker.pkg.dev/{self.project_id}/docker-repo/raaga-ai-trainer:latest"
            )

            job = self.aiplatform.CustomTrainingJob(
                display_name=job_name,
                script_path="scripts/train_model.py",
                container_uri=container_image_uri,
                requirements=["torch>=2.1", "torchaudio>=2.1"],
                model_serving_container_image_uri=None,  # Not a serving model
            )

            response = job.run(
                args=self._get_training_args(),
                replica_count=1,
                machine_type=self.config.machine_type,
                accelerator_type=self.config.gpu_type,
                accelerator_count=self.config.num_gpus,
                tensorboard=self.config.tensorboard_prefix,
                sync=False,
            )

            job_id = response.name
            logger.info(f"✓ Vertex AI training job submitted: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"✗ Failed to submit Vertex AI job: {e}")
            raise

    def get_job_status(self, job_id: str) -> dict:
        """Get Vertex AI job status."""
        try:
            job = self.aiplatform.CustomTrainingJob.get(job_id)

            state_map = {
                "JOB_STATE_QUEUED": "QUEUED",
                "JOB_STATE_PREPARING": "PREPARING",
                "JOB_STATE_RUNNING": "RUNNING",
                "JOB_STATE_SUCCEEDED": "SUCCESS",
                "JOB_STATE_FAILED": "FAILED",
                "JOB_STATE_CANCELLING": "CANCELLING",
                "JOB_STATE_CANCELLED": "CANCELLED",
            }

            return {
                "status": state_map.get(job.state.name, job.state.name),
                "job_id": job_id,
                "creation_time": job.create_time.isoformat() if job.create_time else None,
                "update_time": job.update_time.isoformat() if job.update_time else None,
                "display_name": job.display_name,
                "tensorboard": self.config.tensorboard_prefix,
            }
        except Exception as e:
            logger.error(f"✗ Failed to get job status: {e}")
            return {"status": "UNKNOWN", "error": str(e)}

    def download_model(self, job_id: str, local_dir: str) -> bool:
        """Download trained model from GCS."""
        try:
            import os
            import tarfile

            os.makedirs(local_dir, exist_ok=True)

            bucket = self.gcs_client.bucket(self.bucket)
            model_blob = bucket.blob("models/svara_transformer.pt")

            local_tar = f"{local_dir}/model.tar.gz"
            model_blob.download_to_filename(local_tar)

            # Extract tarball
            if local_tar.endswith(".tar.gz"):
                with tarfile.open(local_tar, "r:gz") as tar:
                    tar.extractall(path=local_dir)

            logger.info(f"✓ Downloaded model to {local_dir}")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to download model: {e}")
            return False

    def cancel_job(self, job_id: str) -> bool:
        """Cancel Vertex AI training job."""
        try:
            job = self.aiplatform.CustomTrainingJob.get(job_id)
            job.cancel()
            logger.info(f"✓ Cancelled Vertex AI job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to cancel job: {e}")
            return False

    def _get_training_args(self) -> list[str]:
        """Get command-line arguments for training."""
        return [
            "--epochs",
            str(self.config.epochs),
            "--batch-size",
            str(self.config.batch_size),
            "--lr",
            str(self.config.learning_rate),
            "--embed-dim",
            str(self.config.embed_dim),
            "--num-heads",
            str(self.config.num_heads),
            "--num-layers",
            str(self.config.num_layers),
            "--dropout",
            str(self.config.dropout),
            "--grad-clip",
            str(self.config.grad_clip),
            "--max-seq-len",
            str(self.config.max_seq_len),
            "--val-split",
            str(self.config.val_split),
            "--patience",
            str(self.config.patience),
        ]
