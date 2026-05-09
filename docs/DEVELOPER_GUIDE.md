# Raaga.AI — Developer Guide

A single end-to-end reference for engineers contributing to or running the system. Covers architecture, code layout, data flow, ML pipeline, API, storage, async jobs, frontend, local dev, extension recipes, and deployment.

> Companion files: `CLAUDE.md` (one-page overview), `docs/DATA_SOURCES.md` (training-data sourcing), `docs/CLOUD_TRAINING.md` (remote training), `README.md` (quick install).

---

## 1. What is Raaga.AI?

A platform that **generates structured Carnatic compositions** — svara sequences, lyrics (sahityam), and synthesized audio — for any raga + tala the user picks. The generation engine is **rule-based first**, **neural-augmented second**:

- A pure-Python **constraint engine** enforces raga (`arohanam`/`avarohanam` membership, characteristic phrases) and tala (beat grids, stress patterns) rules. This is the safety net — output is never out-of-raga.
- A small **Transformer** (`SvaraTransformer`) is trained on real and synthetic Carnatic notation. At inference its logits are masked by the constraint engine, so the neural model can only choose between rule-valid svaras.
- Lyrics are **template-based** Telugu text aligned to svara positions.
- Audio is synthesized by an **additive vocal model + tambura drone**, written to WAV.

The whole generation is asynchronous: a request creates a Celery job, status streams back through Redis, and the final WAV / metadata is uploaded to MinIO.

## 2. Tech stack at a glance

| Layer | Technology | Where it lives |
|---|---|---|
| HTTP API | FastAPI 0.115+, Uvicorn | `src/api/` |
| Job queue | Celery 5.4+ + Redis broker | `src/workers/` |
| DB | PostgreSQL 16 via SQLAlchemy 2.0 async + asyncpg | `src/db/` |
| Migrations | Alembic | `src/db/migrations/` |
| Object store | MinIO (S3-compatible) | `src/storage/` |
| Auth | JWT (HS256) + bcrypt | `src/api/middleware/auth.py` |
| Constraint engine | Pure Python | `src/constraint_engine/` |
| ML model | PyTorch 2.11 (CUDA optional) | `src/ml/` |
| Audio synth | NumPy / scipy | `src/synthesis/` |
| Lyrics | Templates | `src/sahityam/` |
| Frontend | React 19, Vite 7, Axios | `frontend/` |
| Observability | Prometheus + Grafana | `infra/` |
| Lint / type | ruff (line-length 100), mypy | `pyproject.toml` |

Python 3.12+ required. Repo has been verified on Python 3.14 with `torch 2.11.0+cu126` (cu126 is the only Py3.14 channel today).

## 3. Repository layout

```
src/                          # Python backend
  api/                        # FastAPI app
    main.py                   # create_app() factory
    config.py                 # pydantic-settings (.env)
    routers/                  # one file per resource
      generate.py             # POST/GET /api/generate
      compositions.py         # CRUD over completed jobs
      ragas.py, talas.py      # static data lookup
      users.py                # register/login/refresh/me
      health.py               # /health, /health/ready
      cloud_training.py       # remote training jobs
    schemas/                  # Pydantic request/response models
    middleware/               # auth (JWT), rate_limit (Redis), logging (structlog)
  constraint_engine/          # Rule-based core
    raga_engine.py            # RagaEngine: load raga JSON, validate, mask logits
    tala_engine.py            # TalaEngine: beat grids, stress, sam positions
    validators.py             # cross-cutting checks
  ml/                         # Neural model + tokenizer + training data
    model.py                  # SvaraTransformer (Llama-style: RoPE, RMSNorm, GQA, SwiGLU)
    carnatic_gpt.py           # CarnaticGPT — neural-or-fallback generator
    tokenizer.py              # SvaraTokenizer (svara + meta + raga tokens)
    data/
      dataset.py              # SvaraDataset (PyTorch Dataset)
      scraper.py              # SaragaScraper, KarnatikScraper, ShivkumarScraper,
                              #   DunyaFetcher, LocalRagaSynthesizer, augment_sequences
  sahityam/                   # Telugu lyric generation
    generator.py              # template selection
    alignment.py              # align syllables to svara positions
    telugu_utils.py           # transliteration helpers
  synthesis/                  # Audio pipeline
    pipeline.py               # orchestrates pitch → vocal → tambura → WAV
    vocal_synth.py            # additive synth from pitch contour
    gamaka_renderer.py        # gamaka inflections
    tambura.py, percussion.py, bass.py
    vocoder.py, export.py     # WAV writer
  workers/                    # Celery
    celery_app.py             # broker config, queue routing
    tasks/
      generate_composition.py # the long-running generation task
      cloud_training.py       # remote training submitter
    callbacks.py              # job state writes to Redis
  db/                         # SQLAlchemy
    base.py                   # Base, TimestampMixin
    session.py                # async engine + sessionmaker
    models/                   # users, generation_jobs, compositions, ragas, talas, cloud_training_jobs
    repositories/             # one repo per aggregate
    migrations/               # Alembic versions
  storage/
    client.py                 # MinIO wrapper
  core/
    constants.py              # Svara / Octave / GamakaType enums, ALL_SVARAS
    exceptions.py             # RagaError, GenerationError, SynthesisError ...
    types.py                  # shared TypedDicts / NewTypes

frontend/                     # React + Vite SPA
  src/
    pages/                    # Home, Explore, Generate, Login
    components/               # Navbar, AudioPlayer, ProgressTracker, RagaCard, SvaraDisplay
    hooks/                    # useAuth, usePolling
    api/client.js             # Axios instance with /api proxy → :8000

data/                         # Local JSON / training corpus
  ragas/                      # melakarta.json + janya.json (raga definitions)
  talas/                      # tala definitions
  tokenizer/                  # vocab files
  training/                   # svara_sequences.jsonl (built artifact)
  models/                     # svara_transformer.pt + tokenizer_vocab.json

scripts/                      # CLI entry points
  build_dataset.py            # build training JSONL (synthetic + scrape + Saraga + Dunya)
  train_model.py              # train SvaraTransformer
  cloud_train.py              # submit a remote training job
  generate_melakarta_data.py  # programmatic raga JSON generator
  maestro_to_svara.py         # MAESTRO MIDI → svara converter (legacy, not recommended)
  seed_db.py                  # seed users / ragas / talas

tests/                        # pytest
  unit/, integration/, fixtures/

infra/                        # Docker, nginx, Prometheus/Grafana configs
docs/                         # this guide + others
```

## 4. The 5-stage generation pipeline

End-to-end from request → audio:

```
POST /api/generate
   │
   ▼
GenerationJob row created (status=pending)
Celery task `generate_composition` enqueued on queue=generation
   │
   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ L1  RagaEngine     load raga spec; build allowed-svara set            │
│ L2  TalaEngine     build beat grid (sam, stress, beats-in-cycle)      │
│ L3  CarnaticGPT    generate svaras per section (pallavi/anupallavi/   │
│                    charanam/chittaswaram).                            │
│                    - If trained checkpoint present → SvaraTransformer │
│                      with raga-constrained logit mask (EOS + non-     │
│                      svara tokens hard-masked to -inf).               │
│                    - Else → weighted random walk over arohanam /      │
│                      avarohanam with melodic heuristics.              │
│ L4  Sahityam       select Telugu template, align syllables to         │
│                    svara positions.                                   │
│ L5  SynthesisPipe  pitch contour from svaras (with gamakas) →         │
│                    vocal synth → mix with tambura drone →             │
│                    write 44.1 kHz WAV → upload to MinIO.              │
└────────────────────────────────────────────────────────────────────────┘
   │
   ▼
GenerationJob.status=completed
Composition row inserted (svaras, lyrics, audio_url, metadata jsonb)
   │
   ▼
Frontend polls GET /api/generate/{job_id} via usePolling, displays AudioPlayer
```

Checkpoints between stages are saved to MinIO so a failed L5 can be retried without re-running L1–L4.

## 5. Backend module deep-dive

### 5.1 `src/constraint_engine/`

Pure Python, no ML dependencies. Loaded by both the API process and the worker.

- **`RagaEngine(data_dir)`** — globs `data/ragas/*.json`, builds `dict[str, RagaSpec]`. Each `RagaSpec` exposes `arohanam`, `avarohanam`, `allowed_svaras` (frozenset), `characteristic_phrases`, `vadi`, `samvadi`. Methods:
  - `validate(raga_id, svaras)` → bool — every svara in `allowed_svaras`?
  - `get_valid_next(raga_id, context)` → list[str] — biased toward arohanam/avarohanam neighbors of the last svara, plus Sa/Pa.
  - `get_logit_mask(raga_id, context, vocab)` → list[float] of `0.0` / `-inf` — additive mask for model logits.
- **`TalaEngine()`** — loads tala definitions from JSON. `generate_grid(tala_id, n_avartanams)` returns a list of `BeatPosition(beat_in_cycle, is_sam, stress)`. Used by the GPT to know how many svaras to generate per section and which beats are stressed.

### 5.2 `src/ml/`

- **`tokenizer.py`** → `SvaraTokenizer`
  - Base vocab (`SVARA_VOCAB`): 12 svaras + special (`<pad>`, `<bos>`, `<eos>`) + section tokens (`pallavi`, `anupallavi`, …) + kala tokens (`vilamba`, `madhyama`, `dhrita`).
  - `add_raga_tokens(ids)` and `add_tala_tokens(ids)` extend the vocab in place; `vocab_size` updates.
  - `encode_conditioning(raga, tala, section, kala) → list[int]` — emits the prefix the model conditions on.
- **`model.py`** → `SvaraTransformer`
  - Llama-style: RMSNorm, RoPE, Grouped Query Attention (4 query / 2 KV heads), SwiGLU FFN, weight-tied head.
  - Default size: 4 layers, 128 dim, ~760k params, fits in <500 MB VRAM.
  - `forward(input_ids, labels=None) → {"logits", "loss"}` (cross-entropy with `ignore_index=-100`).
  - `generate(input_ids, max_new_tokens, temperature, top_k, logit_mask, eos_token_id)` — sampling with raga-constrained logit mask added each step.
  - Latent bug fixes already applied: RoPE `_build_cache` uses `device=self.inv_freq.device` (no CUDA crash on cache extension); padding embedding row is re-zeroed after `_init_weights` (gradient masking + zero init keeps it correct).
- **`carnatic_gpt.py`** → `CarnaticGPT`
  - Constructor signature: `(raga_engine, tala_engine, checkpoint_path)`.
  - `_try_load_model()` silently no-ops if checkpoint missing → falls back to rule-based walk.
  - `generate_svaras(raga_id, tala_id, section, kala, num_avartanams)` returns `GeneratedSvaras(svaras, source)`. Source is `"neural"` or `"walk"`.
  - `_generate_neural` builds a *strict* logit mask (only this raga's svaras pass; EOS + all metadata tokens are `-inf`), so the body is svara-only by construction. Under-fill falls back to a random allowed svara, never a drone repeat.
  - `_generate_walk` is the fallback: weighted random walk biased by stepwise motion, characteristic phrases, sam-on-strong-svara, and direction flips at cycle boundaries.

### 5.3 `src/ml/data/`

- **`dataset.py`** → `SvaraDataset(jsonl_path, tokenizer, max_length)` — reads JSONL, calls `tokenizer.add_raga_tokens(unique_ids)` so the embedding table covers every raga in the file. Each item is `{input_ids, labels}` with labels left-shifted for next-token prediction.
- **`scraper.py`** — five sources, each emitting `[{"raga_id", "section", "svaras"}]`:
  | Class | Source | Notes |
  |---|---|---|
  | `SaragaScraper` | Saraga 1.5 JSON annotations | Manual download (Zenodo). Best quality. |
  | `KarnatikScraper` | karnatik.com | Old `/c[a-z].shtml` index dead — needs rebuild. |
  | `ShivkumarScraper` | shivkumar.org | 2-level crawl, polite (2 s, robots.txt). ~430 candidate notation pages, ~4.7k svara sequences extracted at last build. |
  | `DunyaFetcher` | CompMusic Dunya REST API | Needs free token (`DUNYA_TOKEN` env). Pitch contour → svara via cents-from-tonic. |
  | `LocalRagaSynthesizer` | Local raga JSONs | Always available, no network. Pure random walks over arohanam/avarohanam. |
  - `augment_sequences(seqs)` is **raga-preserving**: sub-phrase repetition + 2 random sub-window samples per input. Chromatic transposition was removed (it shifts svaras out of raga while keeping the raga label → silent label noise).

### 5.4 `src/sahityam/`

Template-based Telugu lyric generation. `generator.py` selects a template by section (pallavi vs charanam tend to be different lengths and themes). `alignment.py` distributes syllables across the svara grid (one syllable per beat, padding shorter lines). `telugu_utils.py` handles transliteration (English → Telugu Unicode).

This module is intentionally simple — neural lyric generation is **out of scope**; lyrics are a template fill-in.

### 5.5 `src/synthesis/`

- **`pipeline.py`** orchestrates: svaras → pitch contour (Hz) → vocal_synth → mix(tambura, optional bass/percussion) → WAV.
- **`vocal_synth.py`** is additive — fundamental + 6–8 harmonics with ADSR envelope. Not a true vocoder; intentionally stylized.
- **`gamaka_renderer.py`** applies inflections (kampita, jaaru, sphurita) by perturbing the pitch contour around target svaras.
- **`tambura.py`** synthesises a tonic drone (Sa-Pa-Sa-low-Sa) with subtle inharmonicity to approximate the natural beat.
- **`export.py`** writes 44.1 kHz mono WAV via `scipy.io.wavfile`.

### 5.6 `src/api/`

- **`main.py`** has `create_app()` (factory pattern, used by `uvicorn src.api.main:create_app --factory`).
- **Routers** are mounted at `/api/<resource>` in `main.py`. Conventions:
  - `response_model=` on every endpoint
  - DI via `Depends(get_session)`, `Depends(get_current_user)`, `Depends(get_raga_engine)` (cached singletons)
  - 202 Accepted for long-running submissions, with `job_id` returned for polling
- **Middleware** (registered in `main.py`):
  - `auth.py` — JWT bearer extraction, populates `request.state.user`
  - `rate_limit.py` — token bucket in Redis keyed by user id (or IP for unauthenticated)
  - `logging.py` — structlog with correlation IDs

### 5.7 `src/db/`

- **Models** (5 + cloud_training): `User`, `GenerationJob`, `Composition`, `Raga`, `Tala`. UUID primary keys (except `ragas`/`talas` which use string IDs like `shankarabharanam`). JSONB for flexible fields (arohanam list, checkpoints dict, metadata).
- **Repositories** wrap query patterns — never let routers write SQLAlchemy directly; always go through a repo so transactions and joins are testable.
- **`session.py`** — `async_engine = create_async_engine(DATABASE_URL, ...)`, `AsyncSessionLocal = async_sessionmaker(...)`. `get_session()` is the `Depends` factory.
- **Migrations** — `alembic upgrade head` (or `make migrate`). Always inspect generated SQL before merging; auto-generation misses partial-index changes.

### 5.8 `src/workers/`

- **`celery_app.py`** — broker = `REDIS_URL`, two queues: `generation` (composition jobs) and `synthesis` (audio-only retries). Task acks late, max retries via `@app.task(bind=True, max_retries=3)`.
- **`tasks/generate_composition.py`** — the long-running task. Reads job_id, runs L1–L5, updates `redis.hset("job:{id}", ...)` after each stage so `usePolling` can stream progress.
- **`callbacks.py`** — wraps `redis.set("job:{id}:status", ...)` and DB updates on success/failure.

### 5.9 `src/storage/`

`MinioClient` wraps `boto3` against MinIO. Buckets:
- `checkpoints` — per-job pickled stage outputs
- `audio` — final WAV
- `models` — trained `.pt` checkpoints (when promoted)

## 6. ML pipeline deep-dive

### 6.1 Data → JSONL

```bash
.venv/Scripts/python.exe -m scripts.build_dataset \
    [--saraga-dir PATH] \
    [--scrape-karnatik] [--scrape-shivkumar] [--max-web-pages N] \
    [--dunya-token TOKEN | $DUNYA_TOKEN] [--dunya-recordings N] \
    [--synthetic-per-raga N] \
    [--no-augment]
```

Always emits to `data/training/svara_sequences.jsonl`. Each line:
```json
{"raga_id": "shankarabharanam", "section": "pallavi", "svaras": ["Sa","Ri2","Ga2",...]}
```

Pipeline order in `build_dataset.py:main`: synthetic → Saraga → karnatik → shivkumar → Dunya → augment → shuffle → write. Stats logged at end (raga count, section histogram, total svaras, avg length).

### 6.2 Train

```bash
.venv/Scripts/python.exe -m scripts.train_model [flags]
# or: make train-model
```

Flags worth knowing: `--epochs`, `--batch-size`, `--grad-accum`, `--lr`, `--min-lr`, `--warmup-ratio`, `--weight-decay`, `--max-seq-len`, `--embed-dim`, `--num-heads`, `--num-layers`, `--dropout`, `--patience`, `--device cpu|cuda`, `--resume PATH`.

Training loop highlights (`scripts/train_model.py`):
- Linear warmup → cosine decay LR, applied **before** `scaler.step()` (so step 0 actually runs at LR=0 — warmup works).
- AMP (`torch.amp.autocast` + `GradScaler`) on CUDA. `scaler.state_dict()` is checkpointed, so `--resume` doesn't restart with default `init_scale=65536`.
- `random_split` is seeded (`Generator().manual_seed(42)`) — resumed runs see the same train/val partition.
- Tokenizer vocab restored from checkpoint **before** the dataset is built — guarantees raga→ID mapping is identical across runs.
- Best checkpoint saved to `data/models/svara_transformer.pt` with `model_state_dict, optimizer_state_dict, scaler_state_dict, config, tokenizer_vocab, epoch, global_step, val_loss`.

Typical numbers on RTX 3050 with the current 38k-sequence corpus:
- 4 layers / 128d / 4 heads → 760k params, ~73 s/epoch, val_loss ~1.08 after 50 epochs.

### 6.3 Inference

```python
from src.constraint_engine.raga_engine import RagaEngine
from src.constraint_engine.tala_engine import TalaEngine
from src.ml.carnatic_gpt import CarnaticGPT

gpt = CarnaticGPT(
    raga_engine=RagaEngine("data/ragas"),
    tala_engine=TalaEngine(),
    checkpoint_path="data/models/svara_transformer.pt",
)
out = gpt.generate_svaras(
    raga_id="shankarabharanam", tala_id="adi",
    section="pallavi", kala="madhyama", num_avartanams=2,
)
print(out.svaras, out.source)  # source ∈ {"neural", "walk"}
```

The neural path applies a strict mask (only this raga's svaras + EOS suppressed + metadata tokens suppressed) so output is svara-only and 100% in-raga. The fallback walk path is reachable by deleting the checkpoint or breaking it.

## 7. HTTP API surface

Base path: `/api`. JWT bearer required except for `/users/register`, `/users/login`, `/health*`, `/ragas`, `/talas`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/users/register` | Register new user |
| POST | `/users/login` | Issue access + refresh tokens |
| POST | `/users/refresh` | Rotate access token |
| GET | `/users/me` | Current user profile |
| GET | `/ragas` | List ragas (paginated) |
| GET | `/ragas/{id}` | Raga detail |
| GET | `/talas` | List talas |
| GET | `/talas/{id}` | Tala detail |
| POST | `/generate` | Enqueue a generation job → 202 + `{job_id}` |
| GET | `/generate/{job_id}` | Poll job status + intermediate metadata |
| DELETE | `/generate/{job_id}` | Cancel a queued/running job |
| GET | `/compositions` | List user's completed compositions |
| GET | `/compositions/{id}` | Composition detail (audio URL, svaras, lyrics) |
| DELETE | `/compositions/{id}` | Delete |
| POST | `/cloud-training/submit` | Submit a remote training job |
| GET | `/cloud-training/{job_id}` | Status |
| GET | `/cloud-training` | List |
| GET | `/cloud-training/{job_id}/download` | Get model download URL |
| DELETE | `/cloud-training/{job_id}` | Cancel |
| GET | `/health` | Liveness |
| GET | `/health/ready` | Readiness (DB + Redis + MinIO ping) |

OpenAPI/Swagger UI mounted at `/docs` in dev (`APP_ENV=development`).

## 8. Database schema

UUID PKs everywhere except ragas/talas (string IDs match the constraint-engine JSON keys).

```
users (id uuid PK, email unique, password_hash, created_at, updated_at)
generation_jobs (
    id uuid PK, user_id FK→users, status enum,
    raga_id, tala_id, section, kala,            -- request payload
    progress jsonb,                              -- per-stage status
    checkpoints jsonb,                           -- MinIO keys per stage
    error_message, created_at, updated_at
)
compositions (
    id uuid PK, job_id FK→generation_jobs, user_id FK→users,
    raga_id, tala_id, svaras jsonb, lyrics text,
    audio_url, duration_sec, metadata jsonb,
    created_at, updated_at
)
ragas (id text PK, name, melakarta_number, arohanam jsonb, avarohanam jsonb,
       characteristic_phrases jsonb, vadi, samvadi, metadata jsonb)
talas (id text PK, name, beats_per_cycle, structure jsonb, metadata jsonb)
cloud_training_jobs (id uuid PK, user_id FK, provider enum, status,
                     config jsonb, model_url, logs_url, ...)
```

`TimestampMixin` adds `created_at` / `updated_at` to every row.

## 9. Async job lifecycle

```
POST /api/generate ─▶ row(status=pending) + redis.hset(job:{id}, ...) + celery.send_task
                                                         │
                                                         ▼
                                           worker picks up from queue=generation
                                                         │
                              ┌──────────── L1 ──── L2 ── L3 ──── L4 ──── L5 ─────┐
                              │ each stage:                                       │
                              │   redis.hset(job:{id}, stage=L*, progress=X%)     │
                              │   on success → checkpoint to MinIO                │
                              │   on error  → status=failed + error_message       │
                              └────────────────────────────────────────────────────┘
                                                         │
                                                         ▼
                              composition row inserted, status=completed,
                              audio uploaded to s3://audio/{job_id}.wav
```

Frontend polls `GET /api/generate/{job_id}` via `usePolling` hook (default 1.5 s interval, exponential back-off after failures). Status fields: `pending → running → completed | failed | cancelled`.

## 10. Frontend

React 19 + Vite 7. State via hooks, no Redux. Routing via React Router v7.

| File | Purpose |
|---|---|
| `pages/Home.jsx` | Landing |
| `pages/Explore.jsx` | Browse ragas (grid of `RagaCard`) |
| `pages/Generate.jsx` | Form → POST /generate → poll → AudioPlayer |
| `pages/Login.jsx` | Login / register form |
| `components/AudioPlayer.jsx` | HTML5 `<audio>` with seek bar |
| `components/ProgressTracker.jsx` | Per-stage status from job polling |
| `components/SvaraDisplay.jsx` | Renders svara sequence with section markers |
| `hooks/useAuth.jsx` | JWT in `localStorage`, refresh-on-401 |
| `hooks/usePolling.js` | Generic polling with abort/back-off |
| `api/client.js` | Axios instance, attaches `Authorization: Bearer` automatically |

Vite proxies `/api/*` → `http://localhost:8000` in dev (`vite.config.js`).

Styling is CSS-in-JS with CSS-variable theme (`--bg-card`, `--primary`, `--glass`). Glassmorphism look (backdrop-filter blur).

## 11. Local dev workflow

### Prereqs
- Python 3.12+ (3.14 supported)
- Node 20+
- Docker (for postgres/redis/minio)

### One-time setup
```bash
make install                      # python deps into .venv
cd frontend && npm install        # frontend deps
cp .env.example .env              # fill in DATABASE_URL, REDIS_URL, MINIO_*, JWT_SECRET
make infra-up                     # docker compose up postgres redis minio nginx prometheus grafana
make migrate                      # alembic upgrade head
make seed                         # python -m scripts.seed_db
```

### Day-to-day
```bash
make run-api                      # uvicorn :8000
make run-worker                   # celery worker, queues=generation,synthesis
cd frontend && npm run dev        # vite :5173
```

### Building / training
```bash
make train-data                   # build_dataset.py with synthetic only
make train-model                  # train SvaraTransformer 50 epochs
```

For richer datasets, use the flagged form in `docs/DATA_SOURCES.md`.

### Test
```bash
make test                         # pytest
pytest tests/unit/                # unit only
pytest tests/integration/         # needs running infra
```

`pyproject.toml` sets `asyncio_mode = "auto"` so `async def test_*` work without decorators.

## 12. Common extension recipes

### Add a new raga
1. Append to `data/ragas/janya.json` (or create a new file under `data/ragas/`):
   ```json
   "myraga": {
     "id": "myraga", "name": "My Raga",
     "melakarta_parent": "shankarabharanam",
     "arohanam": ["Sa", "Ri2", "Ga2", "Ma1", "Pa", "Da2", "Sa"],
     "avarohanam": ["Sa", "Ni2", "Da2", "Pa", "Ma1", "Ga2", "Ri2", "Sa"],
     "characteristic_phrases": [["Sa","Ri2","Ga2","Ma1"], ["Pa","Da2","Sa"]],
     "vadi": "Pa", "samvadi": "Sa"
   }
   ```
2. `make seed` to copy JSON → `ragas` table (or write a small migration if you prefer SQL-of-record).
3. Rebuild dataset (`make train-data`) so the tokenizer picks up the new raga token, then retrain (`make train-model`). Without retraining the model treats `myraga` as `<unk>` and the constraint engine carries the entire generation.

### Add a new training data source
1. Add a class to `src/ml/data/scraper.py` exposing `def scrape(self, ...) -> list[dict]` that returns `[{"raga_id", "section", "svaras"}]`.
2. Wire it into `scripts/build_dataset.py:main` between the existing source blocks. Add a CLI flag.
3. Document it in `docs/DATA_SOURCES.md`.
4. `LocalRagaSynthesizer.scrape` shows the minimum interface; `ShivkumarScraper` is a good template for polite web scraping (robots.txt check, rate limit, real UA, multi-level discover).

### Add a new API endpoint
1. New file under `src/api/routers/` or method on existing router. Use `response_model=` from `src/api/schemas/`.
2. Register in `src/api/main.py` (`app.include_router(...)`).
3. If it touches the DB, add a method to the relevant `repositories/`. Don't open SQLAlchemy sessions inline.
4. Add an integration test in `tests/integration/api/`.

### Retrain after data changes
```bash
.venv/Scripts/python.exe -m scripts.build_dataset --scrape-shivkumar --max-web-pages 500
.venv/Scripts/python.exe -m scripts.train_model --epochs 100 --resume data/models/svara_transformer.pt
```
Resume is safe — tokenizer vocab + GradScaler + LR schedule all restore correctly.

### Run an inference smoke test against a checkpoint
```python
from src.constraint_engine.raga_engine import RagaEngine
from src.constraint_engine.tala_engine import TalaEngine
from src.ml.carnatic_gpt import CarnaticGPT

gpt = CarnaticGPT(RagaEngine("data/ragas"), TalaEngine(),
                  "data/models/svara_transformer.pt")
print(gpt.generate_svaras("kalyani", "adi", "pallavi", "madhyama", 2).svaras)
```

## 13. Testing conventions

- `tests/unit/` — no DB / Redis / MinIO. Pure-function tests against the constraint engine, tokenizer, scraper parsers.
- `tests/integration/` — depend on `make infra-up`. Use the `pytest-postgresql` ephemeral DB or the docker-compose Postgres.
- Fixtures live in `tests/conftest.py` and `tests/fixtures/`. Engine + GPT instances are session-scoped to avoid re-init cost.
- Use `pytest.mark.asyncio` only when not relying on `asyncio_mode = "auto"` (which is set in `pyproject.toml`).
- Don't mock the DB in integration tests — use a real Postgres against the real schema, otherwise migrations break silently.

## 14. Deployment

`docker-compose.prod.yml` brings up: nginx (TLS terminating reverse-proxy), the API, two worker replicas, postgres, redis, minio, prometheus, grafana.

```bash
make full-stack                   # docker compose -f docker-compose.prod.yml up -d --build
```

Env vars to set at deploy time (see `.env.example`): `DATABASE_URL`, `REDIS_URL`, `MINIO_*`, `JWT_SECRET`, `APP_ENV=production`.

Health checks:
- `GET /health` (liveness; cheap)
- `GET /health/ready` (readiness — pings DB, Redis, MinIO; use for k8s readinessProbe)

Metrics: Prometheus scrapes `/metrics` on the API and worker. Grafana dashboards under `infra/grafana/`.

## 15. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: torch` | venv not activated, or torch never installed | `pip install torch --index-url https://download.pytorch.org/whl/cu126` (Py3.14) or `/whl/cpu` |
| Generated svaras are all `Sa Sa Sa…` | Old `_neural_generate` (pre-fix) — EOS triggers immediately, pad loop drones | Pull latest `src/ml/carnatic_gpt.py`; mask EOS + non-svara tokens |
| `RuntimeError: Expected all tensors on the same device` in RoPE | Old model with `_build_cache` lacking `device=` | Pull latest `src/ml/model.py`; pad embedding init also re-zeroed |
| `--resume` worse than fresh run | Old script — tokenizer rebuilt fresh, split was random, GradScaler reset | Use updated `train_model.py`; checkpoints saved by it carry `tokenizer_vocab`, `scaler_state_dict`, `global_step` |
| `make train-model` warmup never engages | LR scheduler called after `scaler.step()` (old code) | Updated script sets LR before stepping |
| Build dataset says `Scraped 0` | karnatik.com URL pattern dead | Use `--scrape-shivkumar` instead, or rebuild karnatik scraper |
| Augmented data has wrong raga svaras | Old `augment_sequences` did chromatic transposition | Updated function does sub-window sampling only — re-run `build_dataset.py` |
| API: `405 Method Not Allowed` on `/api/generate` | Forgot trailing slash redirect or wrong verb | POST, not GET; no trailing slash |
| Worker not picking up tasks | Wrong queue name — workers serve `generation,synthesis` | `celery worker -Q generation,synthesis` |
| `alembic upgrade head` fails on `enum` change | Auto-gen doesn't handle PG enums | Hand-write `op.execute("ALTER TYPE ... ADD VALUE ...")` migration |
| Frontend `404 /api/generate` | Vite proxy not configured for the path | Check `vite.config.js` server.proxy entry |

---

## Appendix A — Glossary

| Term | Meaning |
|---|---|
| **Raga** | Carnatic mode — defined by which svaras (notes) are allowed and in what direction |
| **Tala** | Rhythmic cycle — a fixed pattern of beats with stress positions (sam, anudrutam, drutam, laghu) |
| **Svara** | A note. Carnatic uses 7 base names (Sa Ri Ga Ma Pa Da Ni) with variants (Ri1/Ri2 etc.) — 12 total in our vocab |
| **Arohanam / Avarohanam** | Ascending / descending svara sequence that defines a raga |
| **Sam** | Beat 1 of a cycle — strongest stress position |
| **Pallavi / Anupallavi / Charanam** | Sections of a krithi (composition) |
| **Sahityam** | Lyrics |
| **Gamaka** | Ornamentation (kampita = oscillation, jaaru = slide, sphurita = grace note) |
| **Kala** | Tempo class (vilamba = slow, madhyama = medium, dhrita = fast) |
| **Krithi** | A complete composition |
| **Vadi / Samvadi** | Most-emphasized and second-most-emphasized svaras of a raga |

## Appendix B — Files most worth reading first

If you have 30 minutes:
1. `src/constraint_engine/raga_engine.py` (~115 lines) — the safety net.
2. `src/ml/carnatic_gpt.py` (~250 lines) — the generation orchestrator.
3. `scripts/build_dataset.py` (~170 lines) — how data flows in.
4. `scripts/train_model.py` (~300 lines) — the full training loop.
5. `src/workers/tasks/generate_composition.py` — the L1→L5 stage runner.

That's roughly the path of one request from entry to audio.
