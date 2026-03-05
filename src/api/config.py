from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_SECRET_KEY: str = "change-me"
    APP_PORT: int = 8000

    DATABASE_URL: str = "postgresql+asyncpg://raaga:raaga@localhost:5432/raaga_db"

    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_AUDIO: str = "raaga-audio"
    MINIO_BUCKET_MODELS: str = "raaga-models"
    MINIO_BUCKET_CHECKPOINTS: str = "raaga-checkpoints"
    MINIO_SECURE: bool = False
    MINIO_BUCKET_TRAINING: str = "raaga-training-data"

    VOCODER_ENABLED: bool = False
    COLLECT_TRAINING_DATA: bool = False

    JWT_SECRET: str = "change-me-jwt"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
