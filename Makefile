.PHONY: install dev test lint serve docker-build docker-run deploy clean config

# --- Setup ---
install:
	pip install -e .

dev:
	pip install -e ".[dev]"
	pre-commit install

# --- Quality ---
test:
	pytest tests/ -v --cov=src --cov-report=term-missing

lint:
	ruff check src/ tests/
	mypy src/ --ignore-missing-imports

format:
	ruff format src/ tests/

# --- Run ---
serve:
	uvicorn src.api.app:app --reload --port 8080

config:
	fct-engine config --show

generate:
	fct-engine generate -i drafts/example_idea.yaml

review:
	fct-engine review -i output/proposal.json

pipeline:
	fct-engine pipeline -i drafts/example_idea.yaml

# --- Docker ---
docker-build:
	docker build -t fct-engine .

docker-run:
	docker compose up -d

docker-stop:
	docker compose down

# --- GCP ---
deploy-init:
	./scripts/deploy.sh --init

deploy:
	./scripts/deploy.sh

deploy-infra:
	cd infra/terraform && terraform init && terraform apply

# --- Cleanup ---
clean:
	rm -rf output/ __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
