# Raaga.AI — Backend Architecture

> Production-grade backend for Carnatic classical music generation.
> This document is the single source of truth for setting up, understanding, and contributing to the backend.

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Technology Stack](#2-technology-stack)
3. [Service Architecture](#3-service-architecture)
4. [API Layer](#4-api-layer)
5. [Database Schema](#5-database-schema)
6. [Queue & Task Pipeline](#6-queue--task-pipeline)
7. [Constraint Engine (L1–L2)](#7-constraint-engine-l1l2)
8. [ML Inference Service (L3)](#8-ml-inference-service-l3)
9. [Sahityam Engine (L4)](#9-sahityam-engine-l4)
10. [Audio Synthesis Pipeline (L5)](#10-audio-synthesis-pipeline-l5)
11. [Caching Strategy](#11-caching-strategy)
12. [Authentication & Authorization](#12-authentication--authorization)
13. [Configuration & Environment](#13-configuration--environment)
14. [Monitoring & Observability](#14-monitoring--observability)
15. [Local Development Setup](#15-local-development-setup)
16. [Deployment](#16-deployment)
17. [Testing Strategy](#17-testing-strategy)

---

## 1. Project Structure

```
raaga-ai/
├── docker-compose.yml              # Local dev orchestration
├── docker-compose.prod.yml         # Production overrides
├── Makefile                        # Common commands
├── .env.example                    # Environment template
├── pyproject.toml                  # Python project config (Poetry/PDM)
│
├── src/
│   ├── api/                        # FastAPI application
│   │   ├── __init__.py
│   │   ├── main.py                 # App factory, lifespan events
│   │   ├── config.py               # Pydantic Settings
│   │   ├── dependencies.py         # Dependency injection
│   │   ├── middleware/
│   │   │   ├── rate_limit.py
│   │   │   ├── auth.py
│   │   │   └── logging.py
│   │   ├── routers/
│   │   │   ├── generate.py         # POST /generate, GET /status/{id}
│   │   │   ├── ragas.py            # GET /ragas, GET /ragas/{id}
│   │   │   ├── talas.py            # GET /talas
│   │   │   ├── compositions.py     # CRUD for saved compositions
│   │   │   ├── users.py            # Registration, profile
│   │   │   └── health.py           # Healthcheck endpoints
│   │   └── schemas/
│   │       ├── generation.py       # Request/response models
│   │       ├── raga.py
│   │       ├── tala.py
│   │       ├── composition.py
│   │       └── user.py
│   │
│   ├── core/                       # Shared domain logic
│   │   ├── __init__.py
│   │   ├── constants.py            # Svara enum, tala beats, etc.
│   │   ├── exceptions.py           # Custom exception hierarchy
│   │   ├── events.py               # Domain events
│   │   └── types.py                # Type aliases, NewTypes
│   │
│   ├── constraint_engine/          # L1 + L2: Raga & Tala validation
│   │   ├── __init__.py
│   │   ├── raga_engine.py          # Python bindings to Rust engine
│   │   ├── tala_engine.py          # Tala prastara logic
│   │   ├── validators.py           # Svara sequence validation
│   │   └── rust_bindings/          # PyO3 bridge
│   │       ├── Cargo.toml
│   │       └── src/
│   │           ├── lib.rs          # Rust FFI entry
│   │           ├── raga.rs         # Arohanam/avarohanam, varja rules
│   │           ├── tala.rs         # Beat grid, eduppu
│   │           └── gamaka.rs       # Gamaka classification
│   │
│   ├── ml/                         # L3: Carnatic-GPT inference
│   │   ├── __init__.py
│   │   ├── carnatic_gpt.py         # Model loading, inference wrapper
│   │   ├── constrained_decode.py   # Logit masking with constraint engine
│   │   ├── tokenizer.py            # Custom svara tokenizer
│   │   └── model_registry.py       # Model version management
│   │
│   ├── sahityam/                   # L4: Telugu lyric generation
│   │   ├── __init__.py
│   │   ├── generator.py            # Sahityam generation pipeline
│   │   ├── alignment.py            # Svara-akshara mapping
│   │   ├── chandas.py              # Prosodic meter enforcement
│   │   └── telugu_utils.py         # Transliteration, normalization
│   │
│   ├── synthesis/                  # L5: Audio rendering
│   │   ├── __init__.py
│   │   ├── pipeline.py             # Orchestrates full audio render
│   │   ├── gamaka_renderer.py      # Pitch curve generation
│   │   ├── vocal_synth.py          # Vocal synthesis
│   │   ├── tambura.py              # Drone generation
│   │   ├── timbre.py               # Instrument models
│   │   └── export.py               # WAV/MP3 encoding
│   │
│   ├── workers/                    # Celery task definitions
│   │   ├── __init__.py
│   │   ├── celery_app.py           # Celery config, broker setup
│   │   ├── tasks/
│   │   │   ├── generate_composition.py   # Main orchestrator task
│   │   │   ├── generate_svaras.py        # L3 svara generation
│   │   │   ├── generate_sahityam.py      # L4 lyric generation
│   │   │   ├── synthesize_audio.py       # L5 audio render
│   │   │   └── notify.py                 # Webhook / push notifications
│   │   └── callbacks.py            # Error handlers, retry logic
│   │
│   ├── db/                         # Database layer
│   │   ├── __init__.py
│   │   ├── session.py              # SQLAlchemy async session factory
│   │   ├── models/                 # ORM models
│   │   │   ├── user.py
│   │   │   ├── composition.py
│   │   │   ├── generation_job.py
│   │   │   ├── raga.py
│   │   │   └── tala.py
│   │   ├── repositories/           # Data access layer
│   │   │   ├── base.py
│   │   │   ├── user_repo.py
│   │   │   ├── composition_repo.py
│   │   │   └── job_repo.py
│   │   └── migrations/             # Alembic migrations
│   │       ├── env.py
│   │       └── versions/
│   │
│   └── storage/                    # Object storage abstraction
│       ├── __init__.py
│       ├── client.py               # MinIO/S3 wrapper
│       └── paths.py                # Bucket/key conventions
│
├── data/
│   ├── ragas/                      # Raga JSON definitions
│   │   ├── melakarta.json          # 72 melakarta ragas
│   │   └── janya.json              # Janya ragas
│   ├── talas/
│   │   └── talas.json              # Tala definitions
│   ├── seeds/                      # DB seed data
│   │   └── seed_ragas.py
│   └── tokenizer/
│       └── svara_vocab.json        # Custom tokenizer vocabulary
│
├── infra/
│   ├── nginx/
│   │   └── nginx.conf              # Reverse proxy, rate limit, SSL
│   ├── prometheus/
│   │   └── prometheus.yml
│   ├── grafana/
│   │   └── dashboards/
│   └── docker/
│       ├── Dockerfile.api
│       ├── Dockerfile.worker
│       └── Dockerfile.rust-engine
│
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_raga_engine.py
│   │   ├── test_tala_engine.py
│   │   ├── test_tokenizer.py
│   │   └── test_sahityam.py
│   ├── integration/
│   │   ├── test_generation_pipeline.py
│   │   ├── test_api_endpoints.py
│   │   └── test_worker_tasks.py
│   └── fixtures/
│       ├── sample_svaras.json
│       └── sample_compositions.json
│
└── scripts/
    ├── seed_db.py
    ├── train_carnatic_gpt.py
    ├── train_sahityam.py
    ├── generate_synthetic_data.py
    └── benchmark_inference.py
```

---

## 2. Technology Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| **Language** | Python | 3.12+ | Primary backend language |
| **Framework** | FastAPI | 0.115+ | Async HTTP API |
| **ASGI Server** | Uvicorn | 0.30+ | Production ASGI server |
| **Reverse Proxy** | nginx | 1.26+ | SSL termination, rate limiting, static files |
| **Task Queue** | Celery | 5.4+ | Async job processing |
| **Broker** | Redis | 7.2+ | Message broker + cache + rate limiter |
| **Database** | PostgreSQL | 16+ | Primary relational store |
| **ORM** | SQLAlchemy | 2.0+ | Async ORM with Alembic migrations |
| **Object Storage** | MinIO | Latest | S3-compatible audio/model storage |
| **Constraint Engine** | Rust (PyO3) | 1.76+ | Sub-ms svara validation |
| **ML Inference** | vLLM / TensorRT | — | Transformer inference (Carnatic-GPT) |
| **Audio DSP** | Custom (C++/Python) | — | Gamaka-aware synthesis |
| **Monitoring** | Prometheus + Grafana | — | Metrics, dashboards, alerting |
| **Containerization** | Docker + Compose | — | Local dev & deployment |

---

## 3. Service Architecture

```
                    ┌─────────────────────┐
                    │      nginx          │
                    │  (rate limit, SSL)  │
                    └────────┬────────────┘
                             │
                    ┌────────▼────────────┐
                    │    FastAPI (API)     │
                    │  /generate          │
                    │  /status/{id}       │
                    │  /ragas, /talas     │
                    └────────┬────────────┘
                             │
               ┌─────────────┼─────────────────┐
               │             │                  │
        ┌──────▼──────┐  ┌──▼──────────┐  ┌───▼──────────┐
        │ PostgreSQL   │  │   Redis     │  │    MinIO      │
        │ (metadata,   │  │  (broker,   │  │  (audio,      │
        │  users,      │  │   cache,    │  │   models,     │
        │  jobs)       │  │   sessions) │  │   notation)   │
        └──────────────┘  └──┬──────────┘  └──────────────┘
                             │
                    ┌────────▼────────────┐
                    │   Celery Workers    │
                    │                     │
                    │  ┌───────────────┐  │
                    │  │ L1: Raga      │  │
                    │  │    Engine     │◄─┼── Rust (PyO3)
                    │  └───────┬───────┘  │
                    │  ┌───────▼───────┐  │
                    │  │ L2: Tala      │  │
                    │  │    Engine     │  │
                    │  └───────┬───────┘  │
                    │  ┌───────▼───────┐  │
                    │  │ L3: Carnatic  │  │
                    │  │    GPT        │◄─┼── vLLM / TensorRT
                    │  └───────┬───────┘  │
                    │  ┌───────▼───────┐  │
                    │  │ L4: Sahityam  │  │
                    │  │    Engine     │  │
                    │  └───────┬───────┘  │
                    │  ┌───────▼───────┐  │
                    │  │ L5: Audio     │  │
                    │  │    Synthesis  │  │
                    │  └───────────────┘  │
                    └─────────────────────┘
```

The backend follows a layered pipeline model. The API layer accepts requests and enqueues them. Celery workers execute the five-layer generation pipeline (L1→L5) in sequence. Each layer checkpoints its output so that failures at later stages can retry without re-running earlier ones.

---

## 4. API Layer

### 4.1 Core Endpoints

```
POST   /api/v1/generate              # Submit a generation job
GET    /api/v1/generate/{job_id}     # Poll job status + result
DELETE /api/v1/generate/{job_id}     # Cancel a pending job

GET    /api/v1/ragas                 # List all supported ragas
GET    /api/v1/ragas/{raga_id}       # Raga detail (arohanam, avarohanam, phrases)

GET    /api/v1/talas                 # List supported talas

GET    /api/v1/compositions          # User's saved compositions
GET    /api/v1/compositions/{id}     # Composition detail + download links
DELETE /api/v1/compositions/{id}     # Delete composition

POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh

GET    /api/v1/health                # Liveness probe
GET    /api/v1/health/ready          # Readiness probe (DB, Redis, MinIO)
```

### 4.2 Generation Request Schema

```python
# src/api/schemas/generation.py
from pydantic import BaseModel, Field
from enum import Enum

class Kala(str, Enum):
    VILAMBA = "vilamba"       # slow
    MADHYAMA = "madhyama"    # medium
    DRUTA = "druta"          # fast

class GenerationRequest(BaseModel):
    raga_id: str = Field(..., example="shankarabharanam")
    tala_id: str = Field(..., example="adi")
    kala: Kala = Field(default=Kala.MADHYAMA)
    language: str = Field(default="telugu", pattern="^(telugu|tamil|kannada)$")
    theme: str | None = Field(default=None, example="devotional")
    include_chittaswaram: bool = Field(default=False)
    sections: int = Field(default=3, ge=1, le=5,
        description="Number of charanams")

class GenerationResponse(BaseModel):
    job_id: str
    status: str        # queued | processing | completed | failed
    estimated_wait: int  # seconds
    created_at: str

class JobStatus(BaseModel):
    job_id: str
    status: str
    stage: str | None         # current pipeline stage
    progress: float | None    # 0.0 - 1.0
    result: CompositionResult | None
    error: str | None

class CompositionResult(BaseModel):
    audio_url: str            # presigned MinIO URL
    notation_url: str         # PDF download
    sahityam: str             # raw text
    svara_sequence: list[str] # tokenized svaras
    metadata: dict            # raga, tala, duration, etc.
```

### 4.3 API Application Factory

```python
# src/api/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .config import settings
from .routers import generate, ragas, talas, compositions, users, health
from .middleware.rate_limit import RateLimitMiddleware
from .middleware.logging import RequestLoggingMiddleware
from src.db.session import init_db, close_db
from src.storage.client import init_storage

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    init_storage()
    yield
    # Shutdown
    await close_db()

def create_app() -> FastAPI:
    app = FastAPI(
        title="Raaga.AI API",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware,
        redis_url=settings.REDIS_URL,
        default_limit="60/minute",
    )

    app.include_router(health.router,       prefix="/api/v1/health",       tags=["health"])
    app.include_router(generate.router,     prefix="/api/v1/generate",     tags=["generation"])
    app.include_router(ragas.router,        prefix="/api/v1/ragas",        tags=["ragas"])
    app.include_router(talas.router,        prefix="/api/v1/talas",        tags=["talas"])
    app.include_router(compositions.router, prefix="/api/v1/compositions", tags=["compositions"])
    app.include_router(users.router,        prefix="/api/v1/auth",         tags=["auth"])

    return app
```

---

## 5. Database Schema

### 5.1 ER Diagram (Mermaid)

```mermaid
erDiagram
    USERS ||--o{ GENERATION_JOBS : creates
    USERS ||--o{ COMPOSITIONS : owns
    GENERATION_JOBS ||--o| COMPOSITIONS : produces
    RAGAS ||--o{ GENERATION_JOBS : "used in"
    TALAS ||--o{ GENERATION_JOBS : "used in"

    USERS {
        uuid id PK
        string email UK
        string hashed_password
        string tier "free|pro|studio|enterprise"
        int monthly_generations_used
        timestamp created_at
    }

    RAGAS {
        string id PK "e.g. shankarabharanam"
        string name_telugu
        string name_english
        string melakarta_number
        jsonb arohanam
        jsonb avarohanam
        jsonb varja_svaras
        jsonb characteristic_phrases
        jsonb gamaka_rules
        string janya_of FK
        jsonb rasa_tags
    }

    TALAS {
        string id PK "e.g. adi"
        string name
        int beats
        string jathi
        jsonb structure "laghu, drutam, anudrutam"
    }

    GENERATION_JOBS {
        uuid id PK
        uuid user_id FK
        string raga_id FK
        string tala_id FK
        string kala
        string language
        string theme
        string status "queued|processing|completed|failed"
        string current_stage
        float progress
        jsonb checkpoints "stage -> s3 key for intermediate output"
        string error_message
        string queue "high|standard|batch"
        timestamp created_at
        timestamp started_at
        timestamp completed_at
    }

    COMPOSITIONS {
        uuid id PK
        uuid user_id FK
        uuid job_id FK UK
        string raga_id FK
        string tala_id FK
        string audio_key "MinIO object key"
        string notation_key
        text sahityam
        jsonb svara_sequence
        int duration_seconds
        jsonb metadata
        boolean is_public
        timestamp created_at
    }
```

### 5.2 Migrations

Use Alembic for schema management:

```bash
# Create a new migration
alembic revision --autogenerate -m "add compositions table"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

### 5.3 Indexing Strategy

```sql
-- Hot queries
CREATE INDEX idx_jobs_user_status ON generation_jobs(user_id, status);
CREATE INDEX idx_jobs_status_created ON generation_jobs(status, created_at);
CREATE INDEX idx_compositions_user ON compositions(user_id, created_at DESC);
CREATE INDEX idx_ragas_melakarta ON ragas(melakarta_number);

-- Full-text on sahityam for search
CREATE INDEX idx_compositions_sahityam_fts
    ON compositions USING GIN (to_tsvector('simple', sahityam));
```

---

## 6. Queue & Task Pipeline

### 6.1 Celery Configuration

```python
# src/workers/celery_app.py
from celery import Celery

app = Celery("raaga")

app.config_from_object({
    "broker_url": "redis://redis:6379/0",
    "result_backend": "redis://redis:6379/1",
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "task_track_started": True,
    "task_acks_late": True,          # Requeue on worker crash
    "worker_prefetch_multiplier": 1,  # One task at a time per worker

    "task_routes": {
        "workers.tasks.generate_composition.*": {"queue": "generation"},
        "workers.tasks.synthesize_audio.*":     {"queue": "synthesis"},
    },
    "task_queues": {
        "generation-high":     {"exchange": "generation", "routing_key": "high"},
        "generation-standard": {"exchange": "generation", "routing_key": "standard"},
        "generation-batch":    {"exchange": "generation", "routing_key": "batch"},
        "synthesis":           {"exchange": "synthesis"},
    },
})
```

### 6.2 Main Orchestrator Task

```python
# src/workers/tasks/generate_composition.py
from celery import chain
from src.workers.celery_app import app
from .generate_svaras import generate_svaras
from .generate_sahityam import generate_sahityam
from .synthesize_audio import synthesize_audio

@app.task(bind=True, max_retries=2)
def generate_composition(self, job_id: str, params: dict):
    """
    Orchestrates the five-layer pipeline as a Celery chain.
    Each stage checkpoints its output to MinIO so failures
    can retry from the last successful stage.
    """
    pipeline = chain(
        resolve_constraints.s(job_id, params),    # L1 + L2
        generate_svaras.s(job_id),                # L3
        generate_sahityam.s(job_id),              # L4
        synthesize_audio.s(job_id),               # L5
        finalize_composition.s(job_id),           # Save to DB
    )
    pipeline.apply_async()
```

### 6.3 Stage Checkpointing

Each pipeline stage writes its output to MinIO under `checkpoints/{job_id}/{stage}.json`. If a stage fails, the retry mechanism loads the last checkpoint and resumes from there instead of restarting the entire pipeline.

```python
# Example checkpoint pattern in a task
@app.task(bind=True, max_retries=3)
def synthesize_audio(self, svara_data: dict, job_id: str):
    try:
        update_job_stage(job_id, "audio_synthesis")
        audio = run_synthesis(svara_data)
        checkpoint(job_id, "l5_audio", audio)
        return {"audio_key": upload_audio(job_id, audio)}
    except SynthesisError as e:
        self.retry(exc=e, countdown=10)
```

### 6.4 Dead Letter Queue

Persistently failing jobs (after all retries exhausted) are routed to a dead letter queue (`dlq`). A background process logs these for manual review and sends alerts via Grafana.

---

## 7. Constraint Engine (L1–L2)

### 7.1 Raga Lakshana Engine (L1)

The raga engine is written in Rust for sub-millisecond validation. Python accesses it via PyO3 bindings.

```rust
// src/constraint_engine/rust_bindings/src/raga.rs

pub struct RagaSpec {
    pub id: String,
    pub arohanam: Vec<Svara>,
    pub avarohanam: Vec<Svara>,
    pub varja_svaras: Vec<Svara>,
    pub characteristic_phrases: Vec<Vec<Svara>>,
    pub gamaka_rules: HashMap<Svara, Vec<GamakaType>>,
}

impl RagaSpec {
    /// Returns true if the svara sequence is valid for this raga
    pub fn validate_sequence(&self, sequence: &[Svara]) -> ValidationResult {
        // Check each svara against arohanam/avarohanam
        // Block varja svaras
        // Verify phrase directions
        // ...
    }

    /// Returns the set of valid next svaras given current context
    pub fn valid_next_svaras(&self, context: &[Svara]) -> Vec<Svara> {
        // Used by constrained beam search in L3
    }
}
```

```python
# src/constraint_engine/raga_engine.py
from .rust_bindings import raaga_engine  # PyO3 compiled module

class RagaEngine:
    def __init__(self, raga_data_path: str = "data/ragas/"):
        self._engine = raaga_engine.Engine(raga_data_path)

    def validate(self, raga_id: str, svara_sequence: list[str]) -> bool:
        return self._engine.validate_sequence(raga_id, svara_sequence)

    def get_valid_next(self, raga_id: str, context: list[str]) -> list[str]:
        """Returns valid next svaras for constrained decoding."""
        return self._engine.valid_next_svaras(raga_id, context)

    def get_logit_mask(self, raga_id: str, context: list[str],
                       vocab_size: int) -> list[float]:
        """Returns logit mask: 0.0 for valid svaras, -inf for invalid."""
        valid = set(self.get_valid_next(raga_id, context))
        return [0.0 if i in valid else float('-inf') for i in range(vocab_size)]
```

### 7.2 Tala Prastara Engine (L2)

```python
# src/constraint_engine/tala_engine.py

@dataclass
class TalaSpec:
    id: str
    name: str
    beats: int             # total aksharas per avartanam
    jathi: str             # chatusra, tisra, misra, etc.
    structure: list[str]   # ["laghu", "drutam", "drutam"] for Adi

class TalaEngine:
    def generate_grid(self, tala_id: str, num_avartanams: int,
                      eduppu: int = 0) -> TalaGrid:
        """
        Generates the rhythmic grid for the composition.
        Returns beat positions, stress patterns, and section boundaries.
        """

    def validate_rhythm(self, svara_sequence: list[str],
                        tala_id: str) -> bool:
        """Validates that svara sequence aligns with tala structure."""

    def get_eduppu_options(self, tala_id: str) -> list[int]:
        """Returns valid eduppu (starting beat) positions for a tala."""
```

---

## 8. ML Inference Service (L3)

### 8.1 Carnatic-GPT Wrapper

```python
# src/ml/carnatic_gpt.py

class CarnaticGPT:
    def __init__(self, model_path: str, device: str = "cuda"):
        self.model = load_model(model_path, quantization="int8")
        self.tokenizer = SvaraTokenizer("data/tokenizer/svara_vocab.json")

    def generate_svaras(
        self,
        raga_id: str,
        tala_id: str,
        section: str,            # "pallavi" | "anupallavi" | "charanam"
        kala: str,
        num_avartanams: int,
        raga_engine: RagaEngine,
    ) -> list[str]:
        """
        Generates a svara sequence using constrained beam search.
        The raga engine provides logit masks at each decoding step.
        """
        conditioning = self.tokenizer.encode_conditioning(
            raga_id=raga_id,
            tala_id=tala_id,
            section=section,
            kala=kala,
        )

        return constrained_beam_search(
            model=self.model,
            prefix=conditioning,
            max_length=num_avartanams * tala_beats(tala_id),
            logit_mask_fn=lambda ctx: raga_engine.get_logit_mask(
                raga_id, ctx, self.tokenizer.vocab_size
            ),
            beam_width=4,
            temperature=0.8,
        )
```

### 8.2 Custom Svara Tokenizer

```python
# src/ml/tokenizer.py

SVARA_VOCAB = [
    "<pad>", "<bos>", "<eos>",
    # Conditioning tokens
    "<raga>", "<tala>", "<section>", "<kala>",
    # Svaras (all 16 positions)
    "Sa", "Ri1", "Ri2", "Ga1", "Ga2", "Ma1", "Ma2",
    "Pa", "Da1", "Da2", "Ni1", "Ni2",
    # Octave modifiers
    "<lower>", "<middle>", "<upper>",
    # Rhythmic
    "<rest>", "<sustain>",
    # Gamaka modifiers
    "<kampita>", "<jaru>", "<nokku>", "<odukkal>",
    "<sphurita>", "<pratyahata>",
]

class SvaraTokenizer:
    def __init__(self, vocab_path: str):
        self.token_to_id = load_json(vocab_path)
        self.id_to_token = {v: k for k, v in self.token_to_id.items()}
        self.vocab_size = len(self.token_to_id)

    def encode(self, svaras: list[str]) -> list[int]: ...
    def decode(self, ids: list[int]) -> list[str]: ...

    def encode_conditioning(self, raga_id, tala_id, section, kala) -> list[int]:
        """Prepends conditioning tokens to the sequence."""
        return [
            self.token_to_id["<bos>"],
            self.token_to_id["<raga>"], self.token_to_id[raga_id],
            self.token_to_id["<tala>"], self.token_to_id[tala_id],
            self.token_to_id["<section>"], self.token_to_id[section],
            self.token_to_id["<kala>"], self.token_to_id[kala],
        ]
```

---

## 9. Sahityam Engine (L4)

```python
# src/sahityam/generator.py

class SahityamGenerator:
    def __init__(self, model_path: str):
        self.model = load_indic_model(model_path)
        self.chandas = ChandasChecker()

    def generate(
        self,
        svara_sequence: list[str],
        raga_id: str,
        rasa: str,
        theme: str | None,
        language: str = "telugu",
    ) -> SahityamResult:
        """
        Generates Telugu lyrics aligned to the svara sequence.
        Each akshara (syllable) maps to one svara position.
        """
        raw_text = self.model.generate(
            svara_input=svara_sequence,
            raga=raga_id,
            rasa=rasa,
            theme=theme,
        )

        # Enforce prosodic constraints
        aligned = align_aksharas_to_svaras(raw_text, svara_sequence)
        self.chandas.validate(aligned, svara_sequence)

        return SahityamResult(
            text=aligned.full_text,
            akshara_svara_map=aligned.mapping,
            chandas_meter=aligned.detected_meter,
        )
```

```python
# src/sahityam/alignment.py

def align_aksharas_to_svaras(
    text: str,
    svara_sequence: list[str],
) -> AlignedSahityam:
    """
    Maps each syllable in the sahityam to its corresponding svara.
    Handles:
    - Long vowels spanning two beats
    - Consonant clusters
    - Rest positions (no syllable)
    """
    ...
```

---

## 10. Audio Synthesis Pipeline (L5)

```python
# src/synthesis/pipeline.py

class SynthesisPipeline:
    def __init__(self):
        self.gamaka_renderer = GamakaRenderer()
        self.vocal_synth = VocalSynthesizer()
        self.tambura = TamburaGenerator()

    def render(
        self,
        svara_sequence: list[str],
        sahityam: AlignedSahityam,
        raga_id: str,
        tala_id: str,
        kala: str,
        output_quality: str = "high",  # "low" (16kHz) | "high" (44.1kHz)
    ) -> AudioOutput:
        # 1. Convert svaras to pitch contours (Hz over time)
        pitch_contours = self.gamaka_renderer.render(
            svaras=svara_sequence,
            raga_id=raga_id,
            kala=kala,
        )

        # 2. Synthesize vocal track with sahityam
        vocal_track = self.vocal_synth.synthesize(
            pitch_contours=pitch_contours,
            sahityam=sahityam,
            sample_rate=44100 if output_quality == "high" else 16000,
        )

        # 3. Generate tambura drone
        drone = self.tambura.generate(
            tonic=get_tonic_hz(raga_id),
            duration=vocal_track.duration,
        )

        # 4. Mix and export
        mixed = mix_tracks([vocal_track, drone])
        return AudioOutput(
            wav=mixed.to_wav(),
            mp3=mixed.to_mp3(),
            duration=mixed.duration,
        )
```

---

## 11. Caching Strategy

```python
# Redis cache layers

CACHE_LAYERS = {
    # Layer 1: Raga metadata (rarely changes)
    "raga:{raga_id}":              {"ttl": 86400, "type": "json"},

    # Layer 2: Pre-computed popular compositions
    "precomputed:{raga_id}:{tala_id}:{kala}": {"ttl": 3600, "type": "audio_key"},

    # Layer 3: Session state for polling
    "job:{job_id}":                {"ttl": 7200, "type": "json"},

    # Layer 4: Rate limiting
    "ratelimit:{user_id}":         {"ttl": 60,   "type": "counter"},

    # Layer 5: Hot svara sequences (recently generated)
    "svaras:{hash}":               {"ttl": 1800, "type": "json"},
}
```

Pre-computation strategy for the top 40% of requests: the 10 most popular raga-tala-kala combinations (e.g., Shankarabharanam + Adi + Madhyama) are pre-generated during off-peak hours and served directly from cache. This eliminates GPU usage for the most common requests.

---

## 12. Authentication & Authorization

### 12.1 Auth Flow

```
Client → POST /auth/login (email, password)
       ← { access_token (JWT, 15min), refresh_token (opaque, 7d) }

Client → GET /api/v1/generate (Authorization: Bearer <access_token>)
       ← Response
```

### 12.2 Tier-Based Rate Limits

| Tier | Generations/Month | Queue Priority | Audio Quality | API Access |
|---|---|---|---|---|
| `free` | 5 | standard | 16kHz mono | No |
| `pro` | 100 | standard | 44.1kHz stereo | No |
| `studio` | Unlimited | high | 44.1kHz stereo | Yes |
| `enterprise` | Unlimited | high (dedicated) | 44.1kHz stereo | Yes + SLA |

Rate limiting is enforced at two levels: nginx (IP-based, 60 req/min global) and application (user-tier-based, via Redis counters).

---

## 13. Configuration & Environment

```bash
# .env.example

# ── App ──
APP_ENV=development          # development | staging | production
APP_DEBUG=true
APP_SECRET_KEY=change-me
APP_PORT=8000

# ── Database ──
DATABASE_URL=postgresql+asyncpg://raaga:raaga@postgres:5432/raaga_db

# ── Redis ──
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# ── MinIO (S3) ──
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_AUDIO=raaga-audio
MINIO_BUCKET_MODELS=raaga-models
MINIO_BUCKET_CHECKPOINTS=raaga-checkpoints

# ── ML Models ──
CARNATIC_GPT_MODEL_PATH=/models/carnatic-gpt-v1
SAHITYAM_MODEL_PATH=/models/sahityam-telugu-v1
VOCODER_MODEL_PATH=/models/vocoder-v1
MODEL_DEVICE=cuda              # cuda | cpu
MODEL_QUANTIZATION=int8        # none | int8 | int4

# ── Monitoring ──
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000

# ── Auth ──
JWT_SECRET=change-me-too
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

All config is loaded via Pydantic Settings with environment variable support and `.env` files:

```python
# src/api/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_ENV: str = "development"
    DATABASE_URL: str
    REDIS_URL: str
    MINIO_ENDPOINT: str
    CARNATIC_GPT_MODEL_PATH: str
    MODEL_DEVICE: str = "cuda"
    MODEL_QUANTIZATION: str = "int8"
    JWT_SECRET: str
    # ...

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## 14. Monitoring & Observability

### 14.1 Key Metrics

| Metric | Type | Description |
|---|---|---|
| `raaga_generation_total` | Counter | Total generation requests by status |
| `raaga_generation_duration_seconds` | Histogram | End-to-end generation time |
| `raaga_pipeline_stage_duration_seconds` | Histogram | Time per pipeline stage (L1–L5) |
| `raaga_constraint_violations_total` | Counter | Svaras rejected by raga engine |
| `raaga_queue_depth` | Gauge | Jobs waiting per queue |
| `raaga_gpu_utilization` | Gauge | GPU usage percentage |
| `raaga_cache_hit_ratio` | Gauge | Cache hits / total requests |
| `raaga_active_users` | Gauge | Currently active users |

### 14.2 Structured Logging

```python
import structlog

logger = structlog.get_logger()

# Every request gets a correlation ID
logger.info("generation.started",
    job_id=job_id,
    raga=raga_id,
    tala=tala_id,
    user_tier=user.tier,
)
```

### 14.3 Alerting Rules (Prometheus)

```yaml
# Key alerts
- alert: GenerationLatencyHigh
  expr: histogram_quantile(0.95, raaga_generation_duration_seconds) > 90
  for: 5m

- alert: ConstraintViolationSpike
  expr: rate(raaga_constraint_violations_total[5m]) > 0.1

- alert: QueueBacklog
  expr: raaga_queue_depth > 50
  for: 10m

- alert: GPUMemoryHigh
  expr: raaga_gpu_memory_usage_bytes / raaga_gpu_memory_total_bytes > 0.9
```

---

## 15. Local Development Setup

### 15.1 Prerequisites

- Docker & Docker Compose
- Rust toolchain (for constraint engine compilation)
- Python 3.12+
- (Optional) NVIDIA GPU + CUDA for local ML inference

### 15.2 Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/raaga-ai/raaga-backend.git
cd raaga-backend
cp .env.example .env

# 2. Build Rust constraint engine
cd src/constraint_engine/rust_bindings
cargo build --release
maturin develop --release
cd ../../..

# 3. Start infrastructure
docker compose up -d postgres redis minio

# 4. Run migrations and seed data
alembic upgrade head
python scripts/seed_db.py

# 5. Start API server (dev mode)
uvicorn src.api.main:create_app --factory --reload --port 8000

# 6. Start Celery worker (separate terminal)
celery -A src.workers.celery_app worker \
    --loglevel=info \
    --queues=generation-standard,synthesis \
    --concurrency=2
```

### 15.3 Docker Compose (Full Stack)

```yaml
# docker-compose.yml
services:
  api:
    build:
      context: .
      dockerfile: infra/docker/Dockerfile.api
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [postgres, redis, minio]
    volumes: ["./src:/app/src"]

  worker:
    build:
      context: .
      dockerfile: infra/docker/Dockerfile.worker
    env_file: .env
    depends_on: [postgres, redis, minio]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: raaga_db
      POSTGRES_USER: raaga
      POSTGRES_PASSWORD: raaga
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports: ["9000:9000", "9001:9001"]
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes: ["miniodata:/data"]

  nginx:
    image: nginx:1.26-alpine
    ports: ["80:80"]
    volumes: ["./infra/nginx/nginx.conf:/etc/nginx/nginx.conf"]
    depends_on: [api]

  prometheus:
    image: prom/prometheus
    ports: ["9090:9090"]
    volumes: ["./infra/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml"]

  grafana:
    image: grafana/grafana
    ports: ["3000:3000"]
    depends_on: [prometheus]

volumes:
  pgdata:
  miniodata:
```

---

## 16. Deployment

### 16.1 Production Topology

```
                  ┌──────────────┐
                  │ Cloudflare   │  CDN / DDoS protection
                  └──────┬───────┘
                         │
                  ┌──────▼───────┐
                  │    nginx     │  Hetzner dedicated (€80/mo)
                  │  (2 replicas)│
                  └──────┬───────┘
                         │
              ┌──────────┼──────────┐
              │                     │
      ┌───────▼──────┐    ┌────────▼──────┐
      │   API (x2)   │    │   API (x2)    │
      │   uvicorn    │    │   uvicorn     │
      └──────────────┘    └───────────────┘
              │
      ┌───────▼──────┐
      │ Celery Workers│  RunPod Serverless (GPU)
      │  (auto-scale) │
      └──────────────┘
```

### 16.2 CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml (simplified)
stages:
  - lint: ruff check + mypy
  - test: pytest (unit + integration against test DB)
  - build-rust: compile constraint engine
  - build-docker: build API + Worker images
  - push: push to container registry
  - deploy-staging: rolling update to staging
  - smoke-test: hit /health + generate one composition
  - deploy-prod: rolling update to production
```

---

## 17. Testing Strategy

### 17.1 Test Pyramid

| Level | Tools | What | Coverage Target |
|---|---|---|---|
| **Unit** | pytest | Raga engine, tala engine, tokenizer, schemas | 90%+ |
| **Integration** | pytest + testcontainers | API endpoints, DB queries, Celery tasks | 80%+ |
| **E2E** | pytest + httpx | Full generation pipeline (mock GPU) | Key paths |
| **Music Quality** | Expert panel | Raga adherence, tala integrity, musicality | 90%+ score |

### 17.2 Critical Test Cases

```python
# tests/unit/test_raga_engine.py

def test_mohanam_blocks_invalid_svaras():
    """Mohanam = Sa Ri2 Ga2 Pa Da2. Ma and Ni must be blocked."""
    engine = RagaEngine()
    seq_with_ma = ["Sa", "Ri2", "Ma1", "Pa"]
    assert engine.validate("mohanam", seq_with_ma) is False

def test_shankarabharanam_allows_all_svaras():
    """Shankarabharanam is a sampoorna raga — all 7 svaras valid."""
    engine = RagaEngine()
    seq = ["Sa", "Ri2", "Ga2", "Ma1", "Pa", "Da2", "Ni2", "Sa"]
    assert engine.validate("shankarabharanam", seq) is True

def test_constrained_decode_zero_violations():
    """Generate 100 sequences in Kalyani; expect 0 constraint violations."""
    engine = RagaEngine()
    model = CarnaticGPT(model_path="...")
    for _ in range(100):
        seq = model.generate_svaras(
            raga_id="kalyani", tala_id="adi",
            section="pallavi", kala="madhyama",
            num_avartanams=4, raga_engine=engine,
        )
        assert engine.validate("kalyani", seq) is True
```

---

> **Next Steps:** Clone the repo, run `docker compose up`, and start with Phase 1 — build the Raga Lakshana Engine in Rust and seed the raga database. Everything else layers on top.
