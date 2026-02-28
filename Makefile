.PHONY: install dev test lint serve docker-build docker-run deploy clean config \
       ai-config ai-reviewers ai-todos ai-lint ai-validate ai-summary

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

# --- Claude Code Helpers ---
# Usage: make ai-validate DRAFT=drafts/pdspp_pilot_pex.yaml
DRAFT ?= drafts/example_idea.yaml

ai-config:
	claude -p "Read config.yaml and summarize: LLM providers, models, review panel, and pipeline settings"

ai-reviewers:
	claude -p "Read config.yaml and list all reviewer IDs, their providers, models, and perspectives" \
		--output-format json

ai-todos:
	claude -p "List all TODO, FIXME, HACK, and XXX comments in src/" \
		--output-format json

ai-lint:
	claude -p "Read and fix any ruff or mypy errors in src/" --yes

ai-validate:
	claude -p "Read $(DRAFT) and validate it against data/schemas/draft_idea.json. Report any missing or invalid fields."

ai-summary:
	claude -p "Read $(DRAFT) and produce a 1-paragraph executive summary of the research proposal."

# --- Cleanup ---
clean:
	rm -rf output/ __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
