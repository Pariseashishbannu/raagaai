# Raaga.AI — AI Telugu Song Creator

Create beautiful Telugu songs with AI. Describe what you want — romantic, devotional, or upbeat — and Raaga.AI composes melody, Telugu lyrics, beats, and vocals for you.

Built on authentic Carnatic ragas with a 5-layer generation pipeline: raga validation, tala rhythm, melody composition, Telugu lyric generation, and full audio synthesis with percussion, bass, vocals, and tambura drone.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Vite 7, React Router v7, Axios, Lucide Icons |
| Backend | Python 3.12+, FastAPI 0.115+, Uvicorn |
| Database | PostgreSQL 16+ (SQLAlchemy 2.0 async + asyncpg) |
| Migrations | Alembic |
| Task Queue | Celery 5.4+ with Redis broker |
| Object Storage | MinIO (S3-compatible) |
| Auth | JWT (HS256) + bcrypt |

## Prerequisites

- **Python 3.12+**
- **Node.js 18+** and **npm**
- **Docker** and **Docker Compose** (for PostgreSQL, Redis, MinIO)
- **Git**

## Quick Start

### 1. Clone and Install

```bash
git clone <repo-url>
cd raagaai

# Python dependencies
pip install -r requirements.txt

# Frontend dependencies
cd frontend
npm install
cd ..
```

### 2. Environment Variables

Copy the `.env` file or create one in the project root:

```env
# App
APP_ENV=development
APP_DEBUG=true
APP_SECRET_KEY=dev-secret-key-not-for-production
APP_PORT=8000

# Database
DATABASE_URL=postgresql+asyncpg://raaga:raaga@localhost:5433/raaga_db

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# MinIO (S3)
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_AUDIO=raaga-audio
MINIO_BUCKET_MODELS=raaga-models
MINIO_BUCKET_CHECKPOINTS=raaga-checkpoints
MINIO_SECURE=false

# Auth
JWT_SECRET=dev-jwt-secret-not-for-production
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

> **Note:** If you have a local PostgreSQL running on port 5432, the Docker container maps to port **5433** to avoid conflicts. Adjust `DATABASE_URL` accordingly.

### 3. Start Infrastructure (Docker)

```bash
docker compose up -d
```

This starts:
- **PostgreSQL** on port 5433
- **Redis** on port 6379
- **MinIO** on port 9000 (console on 9001)

### 4. Run Database Migrations

```bash
alembic upgrade head
```

### 5. Seed the Database

Loads 86+ ragas, 7 talas, and a demo user:

```bash
python -m scripts.seed_db
```

Demo credentials after seeding:
- Email: `demo@raaga.ai`
- Password: `demo1234`

### 6. Start the Backend API

```bash
uvicorn "src.api.main:create_app" --factory --reload --port 8000
```

The API runs at `http://localhost:8000`. Docs at `http://localhost:8000/docs`.

> **Important:** The app uses a factory pattern (`create_app()`), so the `--factory` flag is required.

### 7. Start the Celery Worker

Open a **separate terminal**:

```bash
celery -A src.workers.celery_app worker --loglevel=info -Q celery,generation --pool=solo
```

> The `generation` queue is required — tasks are routed there. Use `--pool=solo` on Windows.

### 8. Start the Frontend Dev Server

Open another **separate terminal**:

```bash


```

The frontend runs at `http://localhost:3000` and proxies API requests to `localhost:8000`.

### 9. Open the App

Visit **http://localhost:3000** in your browser.

## How to Use

### Simple Mode (Recommended)
1. Go to the **Create** page
2. Type a prompt like *"Romantic love song in Mohanam"* or click a suggestion chip
3. Click **Create Song**
4. Wait for the pipeline to complete (melody, lyrics, audio, beats)
5. Listen to your song, view the Telugu lyrics by section

### Advanced Mode
1. Toggle to **Advanced** mode on the Create page
2. Select a raga, tala, tempo, theme, and structure manually
3. Click **Create Song**

## Project Structure

```
src/                        # Python backend
  api/                      # FastAPI app, routers, schemas, middleware
  constraint_engine/        # Raga/tala rule validation
  ml/                       # CarnaticGPT (weighted random walk melody generator)
  sahityam/                 # Template-based Telugu lyric generation
  synthesis/                # Audio pipeline: vocals + percussion + bass + drone
  workers/                  # Celery tasks
  db/                       # SQLAlchemy models, repositories, migrations
  storage/                  # MinIO client wrapper
  core/                     # Constants, enums, exceptions

frontend/                   # React + Vite SPA
  src/pages/                # Home, Explore, Generate, Login
  src/components/           # Navbar, AudioPlayer, ProgressTracker, etc.

data/                       # Raga/tala JSON definitions
scripts/                    # seed_db, benchmarks
tests/                      # unit/ and integration/ tests
```

## Generation Pipeline

Songs are generated through 5 stages:

| Stage | What Happens |
|-------|-------------|
| Setting Up Raga | Validates raga/tala constraints and rules |
| Composing Melody | Weighted random walk generates svara sequences by section |
| Writing Lyrics | Template-based Telugu lyrics aligned to svaras |
| Producing Audio | Vocal synthesis + percussion beats + bass + tambura drone, mixed to WAV |
| Finalizing | Uploads audio to MinIO, returns result |

Audio mix: 45% vocals, 25% percussion, 18% bass, 12% tambura drone.

## Model Training

The `SvaraTransformer` model can be retrained on new or synthetic data.

### 1. Build Dataset
Generates synthetic sequences and augments them:
```bash
python -m scripts.build_dataset --synthetic-per-raga 200
```

### 2. Train Model
Runs training for 50 epochs (takes ~15-30m on GPU):
```bash
python -m scripts.train_model --epochs 50 --batch-size 32
```
The best model is saved to `data/models/svara_transformer.pt`.

## Common Commands

```bash
# Infrastructure
docker compose up -d              # Start postgres, redis, minio
docker compose down               # Stop all containers

# Database
alembic upgrade head              # Run migrations
python -m scripts.seed_db         # Seed ragas, talas, demo user

# Backend
uvicorn "src.api.main:create_app" --factory --reload --port 8000

# Celery Worker
celery -A src.workers.celery_app worker --loglevel=info -Q celery,generation --pool=solo

# Frontend
cd frontend && npm run dev        # Dev server on port 3000
cd frontend && npm run build      # Production build

# Tests
pytest                            # Run all tests
pytest tests/unit/                # Unit tests only
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| PostgreSQL port conflict | Docker maps to port 5433. Update `DATABASE_URL` if needed |
| Celery task stuck in queue | Ensure worker runs with `-Q celery,generation` |
| `Attribute "app" not found` | Use `--factory` flag: the app uses `create_app()` |
| Unicode errors in seed script | Files use UTF-8 Telugu text — ensure `encoding="utf-8"` in file reads |
| `bcrypt` / `passlib` errors | Project uses direct `bcrypt` (not passlib) for password hashing |
| MinIO bucket not found | MinIO auto-creates buckets on first upload. Ensure MinIO is running |
\

## Production Access

The application is now running in production mode via Docker Compose.

- **Frontend:** [http://localhost](http://localhost) (Nginx proxy)
- **API Documentation:** [http://localhost/api/docs](http://localhost/api/docs)
- **MinIO Console:** [http://localhost:9001](http://localhost:9001) (User: `minioadmin`, Pass: `minioadmin`)
- **Grafana:** [http://localhost:3001](http://localhost:3001) (Default: `admin`/`admin`)
- **Prometheus:** [http://localhost:9091](http://localhost:9091)

To stop the production stack:
```powershell
docker compose -f docker-compose.prod.yml down
```