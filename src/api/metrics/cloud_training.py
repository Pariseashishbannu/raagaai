"""Prometheus metrics for cloud training features."""

from prometheus_client import Counter, Histogram, Gauge

# Cloud training job metrics
cloud_training_jobs_submitted = Counter(
    "cloud_training_jobs_submitted_total",
    "Total number of cloud training jobs submitted",
    ["platform"],  # AWS, GCP, Azure
)

cloud_training_jobs_completed = Counter(
    "cloud_training_jobs_completed_total",
    "Total number of cloud training jobs completed successfully",
    ["platform"],
)

cloud_training_jobs_failed = Counter(
    "cloud_training_jobs_failed_total",
    "Total number of cloud training jobs that failed",
    ["platform"],
)

cloud_training_jobs_cancelled = Counter(
    "cloud_training_jobs_cancelled_total",
    "Total number of cloud training jobs cancelled by users",
    ["platform"],
)

cloud_training_job_duration_seconds = Histogram(
    "cloud_training_job_duration_seconds",
    "Duration of cloud training jobs in seconds",
    ["platform"],
    buckets=(60, 300, 900, 1800, 3600, 7200, 14400, 28800, 86400),  # 1min to 24h
)

cloud_training_job_progress = Gauge(
    "cloud_training_job_progress",
    "Current progress of cloud training jobs (0.0-1.0)",
    ["job_id", "platform"],
)

cloud_training_active_jobs = Gauge(
    "cloud_training_active_jobs",
    "Number of active cloud training jobs",
    ["platform", "status"],
)

cloud_training_data_upload_duration_seconds = Histogram(
    "cloud_training_data_upload_duration_seconds",
    "Time taken to upload training data to cloud",
    ["platform"],
    buckets=(1, 5, 10, 30, 60, 300, 900),  # 1s to 15min
)

cloud_training_model_download_duration_seconds = Histogram(
    "cloud_training_model_download_duration_seconds",
    "Time taken to download trained model from cloud",
    ["platform"],
    buckets=(10, 30, 60, 300, 900, 1800),  # 10s to 30min
)

# Cloud training feature adoption metrics
cloud_training_users_active = Gauge(
    "cloud_training_users_active",
    "Number of unique users with active cloud training jobs",
    ["tier"],  # pro, studio, enterprise
)

cloud_training_usage_by_tier = Counter(
    "cloud_training_usage_by_tier_total",
    "Total cloud training job submissions by user tier",
    ["tier"],
)

cloud_training_platform_preference = Counter(
    "cloud_training_platform_preference_total",
    "User preference for cloud platforms (based on job submissions)",
    ["platform"],
)


def record_job_submitted(platform: str):
    """Record a job submission."""
    cloud_training_jobs_submitted.labels(platform=platform).inc()
    cloud_training_usage_by_tier.labels(tier="*").inc()  # Aggregate


def record_job_completed(platform: str, duration_seconds: float):
    """Record a completed job."""
    cloud_training_jobs_completed.labels(platform=platform).inc()
    cloud_training_job_duration_seconds.labels(platform=platform).observe(duration_seconds)


def record_job_failed(platform: str):
    """Record a failed job."""
    cloud_training_jobs_failed.labels(platform=platform).inc()


def record_job_cancelled(platform: str):
    """Record a cancelled job."""
    cloud_training_jobs_cancelled.labels(platform=platform).inc()


def record_data_upload(platform: str, duration_seconds: float):
    """Record data upload metric."""
    cloud_training_data_upload_duration_seconds.labels(platform=platform).observe(duration_seconds)


def record_model_download(platform: str, duration_seconds: float):
    """Record model download metric."""
    cloud_training_model_download_duration_seconds.labels(platform=platform).observe(duration_seconds)
