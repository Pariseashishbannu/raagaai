"""AWS SageMaker training adapter."""

import logging
from typing import Optional

from src.cloud_training.base import TrainingConfig, BaseCloudTrainer

logger = logging.getLogger(__name__)


class SageMakerTrainer(BaseCloudTrainer):
    """AWS SageMaker training adapter."""

    def __init__(self, config: TrainingConfig, role_arn: str, bucket: str):
        """Initialize SageMaker trainer.

        Args:
            config: Training configuration
            role_arn: AWS SageMaker execution role ARN
            bucket: S3 bucket for training data and models
        """
        super().__init__(config)
        self.role_arn = role_arn
        self.bucket = bucket
        self.config.output_model_dir = f"s3://{bucket}/models"
        self.config.checkpoint_prefix = f"s3://{bucket}/checkpoints"
        self.config.tensorboard_prefix = f"s3://{bucket}/tb-logs"

        try:
            import boto3
            self.sagemaker_client = boto3.client("sagemaker")
            self.s3_client = boto3.client("s3")
        except ImportError:
            raise ImportError("boto3 is required for AWS SageMaker. Install with: pip install boto3")

    def validate_credentials(self) -> bool:
        """Validate AWS credentials and role."""
        try:
            self.sagemaker_client.list_training_jobs(MaxResults=1)
            logger.info("✓ AWS credentials validated")
            return True
        except Exception as e:
            logger.error(f"✗ AWS credential validation failed: {e}")
            return False

    def upload_training_data(self, local_path: str, remote_path: str) -> bool:
        """Upload training data to S3."""
        try:
            self.s3_client.upload_file(local_path, self.bucket, remote_path)
            logger.info(f"✓ Uploaded {local_path} to s3://{self.bucket}/{remote_path}")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to upload training data: {e}")
            return False

    def submit_training_job(self, job_name: str) -> str:
        """Submit training job to SageMaker."""
        try:
            response = self.sagemaker_client.create_training_job(
                TrainingJobName=job_name,
                RoleArn=self.role_arn,
                AlgorithmSpecification={
                    "TrainingImage": "246618743249.dkr.ecr.us-east-1.amazonaws.com/sagemaker-pytorch:2.0-gpu-py310",
                    "TrainingInputMode": "File",
                },
                InputDataConfig=[
                    {
                        "ChannelName": "training",
                        "DataSource": {
                            "S3DataSource": {
                                "S3DataType": "S3Prefix",
                                "S3Uri": f"s3://{self.bucket}/data/training",
                                "S3DataDistributionType": "FullyReplicated",
                            }
                        },
                        "ContentType": "application/x-recordio-protobuf",
                        "CompressionType": "None",
                    }
                ],
                OutputDataConfig={"S3OutputPath": f"s3://{self.bucket}/models"},
                ResourceConfig={
                    "InstanceType": "ml.g4dn.xlarge",
                    "InstanceCount": 1,
                    "VolumeSizeInGB": 30,
                },
                StoppingCondition={"MaxRuntimeInSeconds": 86400},
                HyperParameters={
                    "epochs": str(self.config.epochs),
                    "batch_size": str(self.config.batch_size),
                    "lr": str(self.config.learning_rate),
                    "embed_dim": str(self.config.embed_dim),
                    "num_heads": str(self.config.num_heads),
                    "num_layers": str(self.config.num_layers),
                    "dropout": str(self.config.dropout),
                },
                StaticHyperParameters={
                    "entry_point": "scripts/train_model.py",
                    "source_dir": "s3://{}/code".format(self.bucket),
                },
                EnableSageMakerMetricsTimeSeries=True,
            )

            job_id = response["TrainingJobArn"]
            logger.info(f"✓ SageMaker training job submitted: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"✗ Failed to submit SageMaker job: {e}")
            raise

    def get_job_status(self, job_id: str) -> dict:
        """Get SageMaker job status."""
        try:
            # Extract training job name from ARN
            job_name = job_id.split("/")[-1]
            response = self.sagemaker_client.describe_training_job(TrainingJobName=job_name)

            status_map = {
                "InProgress": "RUNNING",
                "Completed": "SUCCESS",
                "Failed": "FAILED",
                "Stopping": "STOPPING",
                "Stopped": "STOPPED",
            }

            return {
                "status": status_map.get(response["TrainingJobStatus"], response["TrainingJobStatus"]),
                "job_id": job_id,
                "creation_time": response["CreationTime"].isoformat(),
                "last_modified": response["LastModifiedTime"].isoformat(),
                "final_status": response.get("FinalModelArtifacts", {}).get("S3ModelArtifacts"),
                "logs": response.get("CloudWatchLogGroupName"),
            }
        except Exception as e:
            logger.error(f"✗ Failed to get job status: {e}")
            return {"status": "UNKNOWN", "error": str(e)}

    def download_model(self, job_id: str, local_dir: str) -> bool:
        """Download trained model from S3."""
        try:
            import os

            os.makedirs(local_dir, exist_ok=True)

            # Get job status to find model artifacts
            status = self.get_job_status(job_id)
            model_uri = status.get("final_status")

            if not model_uri:
                logger.error("✗ No model artifacts found")
                return False

            # Parse S3 URI and download
            parts = model_uri.replace("s3://", "").split("/", 1)
            bucket, key = parts[0], parts[1]

            self.s3_client.download_file(bucket, key, f"{local_dir}/model.tar.gz")
            logger.info(f"✓ Downloaded model to {local_dir}")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to download model: {e}")
            return False

    def cancel_job(self, job_id: str) -> bool:
        """Cancel SageMaker training job."""
        try:
            job_name = job_id.split("/")[-1]
            self.sagemaker_client.stop_training_job(TrainingJobName=job_name)
            logger.info(f"✓ Cancelled SageMaker job: {job_name}")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to cancel job: {e}")
            return False
