"""FastAPI application factory with lifespan management."""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.config import settings
from src.api.routers import generate, ragas, talas, compositions, users, health, cloud_training
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.middleware.logging import RequestLoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup — lazy-init DB and storage; skip if services unavailable
    try:
        from src.db.session import init_db
        await init_db()
        print("[INFO] DB models registered")
    except Exception as e:
        print(f"[WARN] DB init skipped: {e}")

    # Storage init runs in a thread with a hard timeout
    def _try_storage():
        try:
            from src.storage.client import init_storage
            init_storage()
            print("[INFO] MinIO storage ready")
        except Exception as e:
            print(f"[WARN] Storage init skipped: {e}")

    import threading
    t = threading.Thread(target=_try_storage, daemon=True)
    t.start()
    t.join(timeout=5.0)
    if t.is_alive():
        print("[WARN] Storage init timed out, continuing without MinIO")

    print("[INFO] Application startup complete")
    yield

    # Shutdown
    try:
        from src.db.session import close_db
        await close_db()
    except Exception:
        pass


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title="Raaga.AI API",
        description="Carnatic classical music generation platform",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        redis_url=settings.REDIS_URL,
        default_limit="60/minute",
    )

    # Routers
    app.include_router(health.router, prefix="/api/v1/health", tags=["health"])
    app.include_router(generate.router, prefix="/api/v1/generate", tags=["generation"])
    app.include_router(cloud_training.router, prefix="/api/v1", tags=["cloud-training"])
    app.include_router(ragas.router, prefix="/api/v1/ragas", tags=["ragas"])
    app.include_router(talas.router, prefix="/api/v1/talas", tags=["talas"])
    app.include_router(compositions.router, prefix="/api/v1/compositions", tags=["compositions"])
    app.include_router(users.router, prefix="/api/v1/auth", tags=["auth"])

    # Serve locally generated audio files in dev mode
    from fastapi.responses import FileResponse
    import os

    @app.get("/api/v1/audio/{audio_path:path}")
    async def serve_audio(audio_path: str):
        path = os.path.join("data", "audio", audio_path)
        if not os.path.exists(path):
            from fastapi import HTTPException
            raise HTTPException(404, "Audio file not found")
        return FileResponse(path, media_type="audio/wav")

    @app.get("/")
    async def root():
        return {
            "service": "Raaga.AI",
            "version": "1.0.0",
            "docs": "/docs",
            "description": "Carnatic classical music generation API",
        }

    return app
