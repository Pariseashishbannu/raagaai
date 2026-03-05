"""Microsoft Azure Machine Learning training adapter."""

import logging
from typing import Optional

from src.cloud_training.base import TrainingConfig, BaseCloudTrainer

logger = logging.getLogger(__name__)


class AzureMLTrainer(BaseCloudTrainer):
    """Microsoft Azure Machine Learning training adapter."""

    def __init__(
        self,
        config: TrainingConfig,
        subscription_id: str,
        resource_group: str,
        workspace_name: str,
        datastore_name: str = "workspaceblobstore",
    ):
        """Initialize Azure ML trainer.

        Args:
            config: Training configuration
            subscription_id: Azure subscription ID
            resource_group: Azure resource group name
            workspace_name: Azure ML workspace name
            datastore_name: Azure datastore for training data
        """
        super().__init__(config)
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.workspace_name = workspace_name
        self.datastore_name = datastore_name
        self.config.output_model_dir = f"azureml://datastore/{datastore_name}/models"
        self.config.checkpoint_prefix = f"azureml://datastore/{datastore_name}/checkpoints"

        try:
            from azure.ai.ml import MLClient
            from azure.identity import DefaultAzureCredential

            self.credential = DefaultAzureCredential()
            self.ml_client = MLClient(
                credential=self.credential,
                subscription_id=subscription_id,
                resource_group_name=resource_group,
                workspace_name=workspace_name,
            )
        except ImportError:
            raise ImportError(
                "azure-ai-ml is required. Install with: "
                "pip install azure-ai-ml azure-identity"
            )

    def validate_credentials(self) -> bool:
        """Validate Azure credentials."""
        try:
            self.ml_client.workspaces.get(name=self.workspace_name)
            logger.info("✓ Azure ML credentials validated")
            return True
        except Exception as e:
            logger.error(f"✗ Azure ML credential validation failed: {e}")
            return False

    def upload_training_data(self, local_path: str, remote_path: str) -> bool:
        """Upload training data to Azure blob storage."""
        try:
            from azure.storage.blob import BlobServiceClient

            # Get datastore connection info
            datastore = self.ml_client.datastores.get(name=self.datastore_name)
            account_name = datastore.account_name
            account_key = datastore.account_key

            blob_service_client = BlobServiceClient(
                account_url=f"https://{account_name}.blob.core.windows.net",
                credential=account_key,
            )

            container_client = blob_service_client.get_container_client(
                container=datastore.container_name
            )

            with open(local_path, "rb") as data:
                container_client.upload_blob(name=remote_path, data=data, overwrite=True)

            logger.info(f"✓ Uploaded {local_path} to Azure blob: {remote_path}")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to upload training data: {e}")
            return False

    def submit_training_job(self, job_name: str) -> str:
        """Submit training job to Azure ML."""
        try:
            from azure.ai.ml import command, Input, Output
            from azure.ai.ml.constants import AssetTypes

            # Create command job
            job = command(
                code="scripts",
                command=self.get_training_command(),
                environment="AzureML-pytorch-1.13-gpu:latest",
                compute="gpu-cluster",
                inputs={
                    "training_data": Input(
                        type=AssetTypes.URI_FILE,
                        path=f"azureml://datastore/{self.datastore_name}/data/training/svara_sequences.jsonl",
                    )
                },
                outputs={
                    "model_output": Output(
                        type=AssetTypes.MODEL,
                        path=f"azureml://datastore/{self.datastore_name}/models",
                    )
                },
                display_name=job_name,
                name=job_name,
            )

            # Set hyperparameters
            job.command = (
                f"{job.command} "
                f"--data ${{{{inputs.training_data}}}} "
                f"--output-dir ${{{{outputs.model_output}}}}"
            )

            # Submit job
            submitted_job = self.ml_client.create_or_update(job)
            job_id = submitted_job.name
            logger.info(f"✓ Azure ML training job submitted: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"✗ Failed to submit Azure ML job: {e}")
            raise

    def get_job_status(self, job_id: str) -> dict:
        """Get Azure ML job status."""
        try:
            job = self.ml_client.jobs.get(name=job_id)

            status_map = {
                "NotStarted": "QUEUED",
                "Starting": "PREPARING",
                "Running": "RUNNING",
                "Finalizing": "FINALIZING",
                "Completed": "SUCCESS",
                "Failed": "FAILED",
                "Canceled": "CANCELLED",
                "NotResponding": "ERROR",
            }

            return {
                "status": status_map.get(job.status, job.status),
                "job_id": job_id,
                "creation_time": job.creation_context.created_at.isoformat()
                if job.creation_context and job.creation_context.created_at
                else None,
                "display_name": job.display_name,
                "type": job.type,
            }
        except Exception as e:
            logger.error(f"✗ Failed to get job status: {e}")
            return {"status": "UNKNOWN", "error": str(e)}

    def download_model(self, job_id: str, local_dir: str) -> bool:
        """Download trained model from Azure blob storage."""
        try:
            import os
            import tarfile

            os.makedirs(local_dir, exist_ok=True)

            from azure.storage.blob import BlobServiceClient

            # Get datastore connection info
            datastore = self.ml_client.datastores.get(name=self.datastore_name)
            account_name = datastore.account_name
            account_key = datastore.account_key

            blob_service_client = BlobServiceClient(
                account_url=f"https://{account_name}.blob.core.windows.net",
                credential=account_key,
            )

            container_client = blob_service_client.get_container_client(
                container=datastore.container_name
            )

            local_tar = f"{local_dir}/model.tar.gz"
            with open(local_tar, "wb") as file_stream:
                download_stream = container_client.download_blob(
                    "models/svara_transformer.pt"
                )
                file_stream.write(download_stream.readall())

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
        """Cancel Azure ML training job."""
        try:
            self.ml_client.jobs.cancel(name=job_id)
            logger.info(f"✓ Cancelled Azure ML job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to cancel job: {e}")
            return False
