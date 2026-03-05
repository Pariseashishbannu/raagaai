# Raaga.AI

Carnatic music generation platform — rule-based composition with audio synthesis.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+, FastAPI 0.115+, Uvicorn |
| Frontend | React 19, Vite 7, React Router v7, Axios |
| Database | PostgreSQL 16+ via SQLAlchemy 2.0 (async) + asyncpg |
| Migrations | Alembic (`src/db/migrations/`) |
| Task Queue | Celery 5.4+ with Redis broker |
| Object Storage | MinIO (S3-compatible) |
| Auth | JWT (HS256) + bcrypt |
| Monitoring | Prometheus + Grafana |
| Testing | pytest + pytest-asyncio |
| Linting | ruff (line-length 100), mypy |

## Project Structure

```
src/                        # Python backend
  api/                      # FastAPI app, config, routers, schemas, middleware
    routers/                # generate, ragas, talas, users, compositions, health
    schemas/                # Pydantic request/response models
    middleware/              # auth (JWT), rate_limit (Redis), logging (structlog)
  constraint_engine/        # Raga/tala rule validation (pure Python)
  ml/                       # CarnaticGPT (weighted random walk), tokenizer
  sahityam/                 # Template-based Telugu lyric generation
  synthesis/                # Audio pipeline: pitch → vocal → tambura → WAV
  workers/                  # Celery tasks (generation + synthesis queues)
  db/                       # SQLAlchemy models, repositories, migrations
  storage/                  # MinIO client wrapper
  core/                     # Constants (Svara, Octave, GamakaType enums), exceptions, types
frontend/                   # React + Vite SPA
  src/pages/                # Home, Explore, Generate, Login
  src/components/           # Navbar, AudioPlayer, ProgressTracker, RagaCard, SvaraDisplay
  src/hooks/                # useAuth, useJobPolling
  src/api/                  # Axios client (proxied to backend)
data/                       # Raga/tala JSON definitions, tokenizer vocabulary
tests/                      # unit/ and integration/ tests
  fixtures/                 # Sample test data
infra/                      # Docker, nginx, Prometheus, Grafana configs
scripts/                    # seed_db, benchmarks
```

## Architecture

The generation pipeline runs in 5 stages (L1→L5):
1. **L1 Raga** — Constraint engine validates svara sequences against raga rules
2. **L2 Tala** — Beat grid generation with stress patterns
3. **L3 GPT** — Weighted random walk generating svaras by section (pallavi, anupallavi, charanam, chittaswaram)
4. **L4 Sahityam** — Template-based Telugu lyrics aligned to svara positions
5. **L5 Synthesis** — Pitch contours → vocal synth → tambura drone → WAV (44.1kHz)

Jobs are queued via Celery, status tracked in Redis, checkpoints saved to MinIO.

## Code Conventions

- **Files:** snake_case (`raga_engine.py`)
- **Classes:** PascalCase (`RagaEngine`, `GenerationJob`)
- **Functions:** snake_case (`validate_sequence()`)
- **Constants:** UPPER_SNAKE_CASE (`SVARA_SEMITONES`, `DEFAULT_TONIC_HZ`)
- **Private methods:** `_method_name()`
- **Type hints:** Python 3.12+ style — `list[str]`, `dict[str, int]`, `X | None`
- **Imports:** stdlib → third-party → local (separated by blank lines)
- **No wildcard imports**

## Backend Patterns

- **API:** Routers with `@router.get/post` + `response_model`, schemas in `schemas/`, dependency injection via `Depends()`
- **DB:** Model in `models/`, repository in `repositories/`, async `AsyncSession`
- **Middleware:** `BaseHTTPMiddleware` subclasses
- **Singletons:** `@lru_cache()` for lazy-loaded dependencies
- **Tasks:** `@app.task(bind=True, max_retries=N)` with Redis state updates
- **Errors:** Custom exception hierarchy in `core/exceptions.py` — `RagaError`, `GenerationError`, `SynthesisError`
- **Logging:** structlog with correlation IDs

## Frontend Patterns

- Components as default exports (JSX)
- State via React hooks (`useState`, `useContext`)
- Styling: CSS-in-JS with CSS variables (`--bg-card`, `--primary`, `--glass`)
- Glassmorphism design with backdrop filters
- API calls via Axios instance with `/api` proxy → `localhost:8000`

## Common Commands

```bash
make infra-up        # Start postgres, redis, minio, nginx, prometheus, grafana
make migrate         # alembic upgrade head
make seed            # python -m scripts.seed_db
make run-api         # uvicorn src.api.main:app --reload --port 8000
make run-worker      # celery worker
make test            # pytest
make train-data      # Build training dataset
make train-model     # Train SvaraTransformer model
make full-stack      # docker compose -f docker-compose.prod.yml up -d --build
```

## Environment

See `.env.example` for all config variables. Key ones:
- `DATABASE_URL` — PostgreSQL connection (asyncpg driver)
- `REDIS_URL` — Redis for Celery broker + rate limiting + job state
- `MINIO_*` — Object storage credentials and bucket names
- `JWT_SECRET` — Token signing key
- `APP_ENV` — `development` | `production`

## Database

5 tables: `users`, `generation_jobs`, `compositions`, `ragas`, `talas`.
UUIDs for PKs (except ragas/talas which use string IDs). JSONB for flexible fields (arohanam, checkpoints, metadata). `TimestampMixin` adds `created_at`/`updated_at`.

## Testing

```bash
pytest                      # Run all tests
pytest tests/unit/          # Unit tests only
pytest tests/integration/   # Integration tests only
```

Async mode: `asyncio_mode = "auto"`. Fixtures in `tests/conftest.py` provide engine/GPT instances.
