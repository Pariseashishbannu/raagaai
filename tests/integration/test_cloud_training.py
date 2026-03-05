"""Integration tests for cloud training endpoints."""

import json
import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.api.main import create_app
from src.api.config import settings
from src.db.base import Base
from src.db.models import User, CloudTrainingJob
from src.db.repositories.cloud_training_job_repo import CloudTrainingJobRepository


@pytest.fixture
async def db_session():
    """Create in-memory test database session."""
    # Use SQLite in-memory for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    session = async_session()
    yield session
    await session.close()
    await engine.dispose()


@pytest.fixture
def app():
    """Create FastAPI test app."""
    return create_app()


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_user(db_session):
    """Create test user."""
    user = User(
        id=uuid4(),
        email="test@example.com",
        hashed_password="hashed_password",
        tier="studio",
        monthly_generations_used=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestCloudTrainingEndpoints:
    """Test suite for cloud training endpoints."""

    @pytest.mark.asyncio
    async def test_submit_training_job_gcp(self, db_session, client, test_user):
        """Test submitting a training job to GCP."""
        with patch("src.api.routers.cloud_training._has_celery_workers", return_value=False):
            with patch("src.api.routers.cloud_training._submit_training_sync"):
                response = client.post(
                    "/api/v1/training/cloud/submit",
                    json={
                        "platform": "gcp",
                        "job_name": "test-training-job",
                        "config": {
                            "epochs": 50,
                            "batch_size": 32,
                            "learning_rate": 0.0003,
                        },
                    },
                    headers={"Authorization": f"Bearer test-token"},
                )

        assert response.status_code == 202
        data = response.json()
        assert data["platform"] == "gcp"
        assert data["status"] == "submitted"
        assert "job_id" in data

    @pytest.mark.asyncio
    async def test_submit_training_job_aws(self, db_session, client, test_user):
        """Test submitting a training job to AWS."""
        with patch("src.api.routers.cloud_training._has_celery_workers", return_value=False):
            with patch("src.api.routers.cloud_training._submit_training_sync"):
                response = client.post(
                    "/api/v1/training/cloud/submit",
                    json={
                        "platform": "aws",
                        "job_name": "aws-training",
                        "config": {
                            "epochs": 100,
                            "batch_size": 64,
                        },
                    },
                )

        assert response.status_code == 202
        data = response.json()
        assert data["platform"] == "aws"

    @pytest.mark.asyncio
    async def test_submit_training_free_tier_rejected(self, db_session, client):
        """Test that free tier users cannot submit cloud training jobs."""
        # Create free tier user
        free_user = User(
            id=uuid4(),
            email="free@example.com",
            hashed_password="hashed",
            tier="free",
        )
        db_session.add(free_user)
        db_session.commit()

        response = client.post(
            "/api/v1/training/cloud/submit",
            json={
                "platform": "gcp",
                "job_name": "test",
                "config": {"epochs": 50},
            },
        )

        # Should be rejected (no auth or tier check)
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    async def test_get_job_status(self, db_session, client, test_user):
        """Test retrieving job status."""
        # Create a test job
        job_id = uuid4()
        job = CloudTrainingJob(
            id=job_id,
            user_id=test_user.id,
            platform="gcp",
            job_name="test-job",
            status="running",
            progress=0.45,
            current_stage="training",
            submitted_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
        )
        db_session.add(job)
        db_session.commit()

        response = client.get(f"/api/v1/training/cloud/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == str(job_id)
        assert data["status"] == "running"
        assert data["progress"] == 0.45

    @pytest.mark.asyncio
    async def test_list_training_jobs(self, db_session, client, test_user):
        """Test listing training jobs for a user."""
        # Create multiple test jobs
        for i in range(3):
            job = CloudTrainingJob(
                id=uuid4(),
                user_id=test_user.id,
                platform="gcp" if i % 2 == 0 else "aws",
                job_name=f"test-job-{i}",
                status="completed" if i == 0 else "running",
                submitted_at=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ),
            )
            db_session.add(job)
        db_session.commit()

        response = client.get("/api/v1/training/cloud")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["jobs"]) == 3

    @pytest.mark.asyncio
    async def test_cancel_training_job(self, db_session, client, test_user):
        """Test cancelling a training job."""
        job_id = uuid4()
        job = CloudTrainingJob(
            id=job_id,
            user_id=test_user.id,
            platform="gcp",
            job_name="test-job",
            status="running",
            cloud_job_id="cloud-job-123",
            submitted_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
        )
        db_session.add(job)
        db_session.commit()

        with patch("src.api.routers.cloud_training._has_celery_workers", return_value=False):
            response = client.delete(f"/api/v1/training/cloud/{job_id}")

        assert response.status_code == 204

    def test_invalid_job_id_format(self, client):
        """Test error handling for invalid job ID."""
        response = client.get("/api/v1/training/cloud/invalid-uuid")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_download_link_completed_job(self, db_session, client, test_user):
        """Test getting download link for completed job."""
        job_id = uuid4()
        job = CloudTrainingJob(
            id=job_id,
            user_id=test_user.id,
            platform="gcp",
            job_name="test-job",
            status="completed",
            model_download_url="https://storage.example.com/model.pt",
            submitted_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
            completed_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
        )
        db_session.add(job)
        db_session.commit()

        response = client.get(f"/api/v1/training/cloud/{job_id}/download")

        assert response.status_code == 200
        data = response.json()
        assert "download_url" in data
        assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_download_link_not_completed(self, db_session, client, test_user):
        """Test error when job not completed."""
        job_id = uuid4()
        job = CloudTrainingJob(
            id=job_id,
            user_id=test_user.id,
            platform="gcp",
            job_name="test-job",
            status="running",
            submitted_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
        )
        db_session.add(job)
        db_session.commit()

        response = client.get(f"/api/v1/training/cloud/{job_id}/download")

        assert response.status_code == 409
        assert "not ready" in response.json()["detail"]


class TestCloudTrainingJobRepository:
    """Test suite for CloudTrainingJobRepository."""

    @pytest.mark.asyncio
    async def test_get_by_user(self, db_session, test_user):
        """Test retrieving jobs by user."""
        # Create test jobs
        for i in range(3):
            job = CloudTrainingJob(
                id=uuid4(),
                user_id=test_user.id,
                platform="gcp",
                job_name=f"job-{i}",
                submitted_at=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ),
            )
            db_session.add(job)
        db_session.commit()

        repo = CloudTrainingJobRepository(db_session)
        jobs = await repo.get_by_user(test_user.id)

        assert len(jobs) == 3

    @pytest.mark.asyncio
    async def test_update_status(self, db_session, test_user):
        """Test updating job status."""
        job_id = uuid4()
        job = CloudTrainingJob(
            id=job_id,
            user_id=test_user.id,
            platform="gcp",
            job_name="test",
            status="queued",
            submitted_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
        )
        db_session.add(job)
        db_session.commit()

        repo = CloudTrainingJobRepository(db_session)
        updated = await repo.update_status(
            job_id,
            status="running",
            stage="training",
            progress=0.5,
        )

        assert updated.status == "running"
        assert updated.progress == 0.5

    @pytest.mark.asyncio
    async def test_get_pending_jobs(self, db_session, test_user):
        """Test retrieving pending jobs."""
        # Create completed and pending jobs
        completed_job = CloudTrainingJob(
            id=uuid4(),
            user_id=test_user.id,
            platform="gcp",
            job_name="completed",
            status="completed",
            submitted_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
        )
        pending_job = CloudTrainingJob(
            id=uuid4(),
            user_id=test_user.id,
            platform="aws",
            job_name="pending",
            status="running",
            submitted_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
        )
        db_session.add(completed_job)
        db_session.add(pending_job)
        db_session.commit()

        repo = CloudTrainingJobRepository(db_session)
        pending = await repo.get_pending_jobs()

        assert len(pending) == 1
        assert pending[0].job_name == "pending"
