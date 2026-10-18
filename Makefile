.PHONY: infra-up infra-down migrate seed run-api run-worker install test train-data train-model cloud-train-aws cloud-train-gcp cloud-train-azure cloud-deps acestep-local

install:
	pip install -e ".[dev]"

cloud-deps:
	pip install -r requirements-cloud.txt

infra-up:
	docker compose up -d

infra-down:
	docker compose down

migrate:
	alembic upgrade head

seed:
	python -m scripts.seed_db

run-api:
	PYTHONUTF8=1 uvicorn src.api.main:create_app --factory --reload --port 8000

run-worker:
	PYTHONUTF8=1 celery -A src.workers.celery_app worker --loglevel=info --queues=generation,synthesis --concurrency=2

test:
	pytest tests/ -v

train-data:
	python -m scripts.build_dataset --synthetic-per-raga 200

train-model:
	python -m scripts.train_model --epochs 50 --batch-size 32

cloud-train-aws:
	python -m scripts.cloud_train --platform aws --role-arn $(ROLE_ARN) --bucket $(BUCKET) --monitor

cloud-train-gcp:
	python -m scripts.cloud_train --platform gcp --project-id $(PROJECT_ID) --bucket $(BUCKET) --monitor

cloud-train-azure:
	python -m scripts.cloud_train --platform azure --subscription-id $(SUBSCRIPTION_ID) --resource-group $(RESOURCE_GROUP) --workspace-name $(WORKSPACE) --monitor

full-stack:
	docker compose -f docker-compose.prod.yml up -d --build

# ACE-Step 1.5 API server on this machine (clone https://github.com/ace-step/ACE-Step-1.5
# next to this repo and `uv sync` there first). The base model needs ~5 GB, so on a
# 4 GB GPU it runs with CPU offload — slow; prefer notebooks/acestep_server_colab.ipynb.
ACESTEP_DIR ?= ../ACE-Step-1.5
acestep-local:
	cd $(ACESTEP_DIR) && ACESTEP_CONFIG_PATH=acestep-v15-base ACESTEP_INIT_LLM=false \
		ACESTEP_OFFLOAD_TO_CPU=true ACESTEP_OFFLOAD_DIT_TO_CPU=true \
		uv run acestep-api --host 127.0.0.1 --port 8001
