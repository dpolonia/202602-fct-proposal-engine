# Claude Code Prompt Sequence — FCT Proposal Engine

## Repository

**GitHub:** `https://github.com/dpolonia/202602-fct-proposal-engine`

The repo already contains the scaffolded project, config.yaml, .gitignore, and supporting files. These prompts clone it, clean it up, and build every module from Phase 1 onward.

## Draft Ideas Folder

All preliminary research ideas go in `drafts/`. Each idea is a YAML file that the pipeline reads as input. The folder ships with `example_idea.yaml` and a `README.md` explaining the format. Users add their own `my_project.yaml` files here.

## How to Use

Paste each prompt **in order**. Wait for completion before pasting the next. Each prompt ends with a git commit.

---

## Phase 0 — Clone & Clean

### Prompt 0.1 — Clone and housekeep

```
Clone the repository:

  git clone https://github.com/dpolonia/202602-fct-proposal-engine.git
  cd 202602-fct-proposal-engine

Then:

1. Remove all Windows Zone.Identifier files:
   find . -name "*:Zone.Identifier" -delete

2. Read config.yaml carefully. Note these are the authoritative values — all code defaults must match:
   - Models: claude-opus-4-6, gpt-5.2-2025-12-11, gemini-3.1-pro-preview, meta-llama/Llama-3.1-70B-Instruct
   - Reviewer IDs: claude_rigor, openai_innovation, gemini_feasibility, llama_domain
   - Pipeline iterations: 3, stop_on_accept: true
   - Scopus: max_results 100, top_abstracts 30
   - Typology default: SR&TD

3. Create drafts/README.md explaining the drafts/ folder:

   # Draft Research Ideas

   Place your preliminary research ideas here as YAML files. Each file is a self-contained
   project draft that the engine reads as input.

   ## Usage

     fct-engine pipeline -i drafts/my_project.yaml
     fct-engine generate -i drafts/my_project.yaml -o output/

   ## File format

   See `example_idea.yaml` for a complete example. Minimum required fields:

     title: "Your Project Title"
     research_topic: "1-3 paragraphs describing the research idea."

   All other fields are optional — the engine fills them from config.yaml defaults
   or generates them using AI.

   ## Files

   | File | Description |
   |------|-------------|
   | example_idea.yaml | Complete DigiResilient example (SR&TD, 36mo, €200k) |
   | *(your files)* | Add .yaml files here for your own proposals |

4. Verify the directory tree has at minimum:
   config.yaml, .gitignore, .env.example (create if missing),
   CLAUDE.md, README.md, Makefile, Dockerfile, docker-compose.yml, pyproject.toml,
   src/ (with config/, generators/, reviewers/, scrapers/, utils/, api/, templates/, cli.py),
   tests/, data/ (rules/, schemas/, prompts/), drafts/, docs/, infra/terraform/, scripts/,
   .github/workflows/

   Create any missing directories or empty __init__.py files.

Commit: "chore: clean repo, add drafts/README.md"
```

---

## Phase 1 — Configuration Layer

### Prompt 1.1 — Two-tier settings (config.yaml + .env)

```
Write src/config/settings.py implementing a two-tier configuration system.

DESIGN PRINCIPLE: config.yaml holds ALL user preferences (LLM providers, models, typology, panel composition, output formats). The .env file holds ONLY API keys/secrets. Source code NEVER hard-codes any user preference.

Read the existing config.yaml in the project root to understand the structure. The defaults in settings.py must match what config.yaml contains.

Implement:

1. class Secrets(pydantic_settings.BaseSettings):
   - Loads from .env only (env_file=".env")
   - Fields: anthropic_api_key, openai_api_key, google_api_key, huggingface_api_key, scopus_api_key, scopus_inst_token, x_api_key, x_api_secret, database_url (default sqlite), redis_url (optional)
   - Method: has_key(provider: str) -> bool — checks if a given provider's key is non-empty

2. class LLMProvider(str, Enum): anthropic, openai, google, huggingface

3. class LLMRole:
   - Constructed from a dict (one level of config.yaml's llm section)
   - Fields: provider (LLMProvider), model (str), temperature (float)
   - Default model: "claude-opus-4-6"

4. class ReviewerDef:
   - Constructed from a dict (one entry in review_panel list)
   - Fields: id, enabled (bool), provider (LLMProvider), model, perspective, focus_criteria (list[str]), persona (str, stripped)
   - Default model: "claude-opus-4-6"

5. class UserConfig:
   - Loads config.yaml via PyYAML (path overridable via FCT_CONFIG env var, default "config.yaml")
   - Sections mapped to typed attributes:
     • project: typology (str), principal_contractor, default_research_units (list), language, target_start_date
     • llm: generator (LLMRole), consensus (LLMRole), revision (LLMRole)
     • review_panel: list of ReviewerDef (ALL entries, not just enabled)
     • pipeline: iterations (int), stop_on_accept (bool), max_concurrent_reviews (int), save_intermediates (bool)
     • scopus: scopus_enabled (bool), scopus_max_results (int), scopus_year_from (int), scopus_enrich_abstracts (bool), scopus_top_abstracts (int)
     • output: output_dir, out_json, out_markdown, out_docx, out_char_report (bools), include_review_narrative (bool)
     • logging: log_level, rich_console (bool)
     • gcp: gcp_project_id, gcp_region, gcs_bucket, cloud_run_service
   - Property: enabled_reviewers -> list[ReviewerDef] (only entries with enabled=True)
   - Method: reload(path?) — hot-reload from disk
   - Derived paths: project_root, data_dir, prompts_dir, rules_dir

6. Module-level singletons:
   secrets = Secrets()
   cfg = UserConfig()

Commit: "feat: two-tier config (config.yaml + .env)"
```

### Prompt 1.2 — FCT call constants

```
Write src/config/fct_constants.py encoding ALL rules from the FCT PTDC 2025 call. This file contains ONLY call rules — never user preferences (those come from config.yaml).

Implement using frozen dataclasses:

1. ProjectType(str, Enum): ICDT = "SR&TD", PEX = "PEX"

2. TypologyRules (frozen dataclass) with TYPOLOGY_RULES dict:
   IC&DT: 36 months, +12 extension, €250,000 max, 30% advance, intermediate payments yes, participating institutions yes, €80M call budget, ~320 projects
   PEX: 18 months, +6 extension, €60,000 max, 75% advance, intermediate payments no, participating institutions no, €24M call budget, ~400 projects

3. CharLimits (frozen dataclass) — ALL character limits from Application Guide republication Dec 2025:
   project_title=255, project_acronym=15, max_keywords=4,
   institution_description=1500,
   career_profile=4000, contributions_new_ideas=5000, contributions_teams=3000, contributions_society=3000, further_details=5000, why_timely_pex=3000,
   consultant_framework=1000, team_cv_synopsis=10000,
   abstract_pt=5000, abstract_en=5000, abstract_publication=5000,
   state_of_art_objectives=6000, research_plan_methods=10000, bibliographic_references=10000, past_publication=600,
   task_denomination=150, task_description=4000, cost_justification=2500,
   deliverable_description=800, milestone_description=300,
   management_structure=3000, ethics_justification=3000,
   other_project_relation=2000,
   computational_platforms=400, computational_justification=400

4. EvalCriteria (frozen dataclass):
   A=0.40 (A1=0.50, A2=0.50 within A), B=0.30 (B1=0.60, B2=0.40 within B), C=0.30
   min_merit_threshold=7.0

5. BudgetRules: indirect_costs_pct=0.25, building_adaptation_max_pct=0.10, ua_minimum_budget_eur=15000

6. CallDates: open=2025-11-27, ua_internal=2026-03-06, fct_deadline=2026-03-11T17:00, commitment=2026-03-25T17:00, results~2026-10

7. DeliverableType(str, Enum): Report, Data Management Plan, Demonstrator, Dissemination/Communication, Dataset, Other

8. ParticipationRules: max_pi=1, max_member_if_pi=1, max_member_if_not_pi=2, max_research_units=3, max_sdgs=3

9. PROPOSAL_SECTIONS list: general_data, institutions, pi_narrative_cv, team_cv_synopsis, abstract_pt, abstract_en, state_of_art_objectives, research_plan_methods, bibliographic_references, tasks, deliverables, milestones, management_structure, ethics, sdg_alignment, budget

Export singletons: CHAR_LIMITS, EVAL_CRITERIA, BUDGET_RULES, CALL_DATES, PARTICIPATION_RULES

Commit: "feat: FCT PTDC 2025 call constants"
```

### Prompt 1.3 — .env.example

```
Write .env.example containing ONLY API key placeholders — no GCP settings, no app preferences (those are in config.yaml):

ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
HUGGINGFACE_API_KEY=hf_...
SCOPUS_API_KEY=...
SCOPUS_INST_TOKEN=...
X_API_KEY=...
X_API_SECRET=...

Add a header comment: "All other settings live in config.yaml."

Commit: "chore: .env.example (secrets only)"
```

---

## Phase 2 — LLM Client & Scopus

### Prompt 2.1 — Unified LLM client

```
Write src/utils/llm_client.py — unified async LLM client with provider abstraction.

Import from src.config.settings: LLMProvider, LLMRole, cfg, secrets

Implement:

1. LLMResponse dataclass: text, model, provider, input_tokens, output_tokens, finish_reason

2. BaseLLMClient (ABC): abstract generate(), concrete generate_json() (appends "JSON ONLY" instruction, temperature=0.1)

3. Four provider implementations — each reads its key from secrets:
   - AnthropicClient: anthropic.AsyncAnthropic, messages API
   - OpenAIClient: openai.AsyncOpenAI, chat completions API
   - GoogleClient: google.genai.Client (sync, wrapped in asyncio run_in_executor)
   - HuggingFaceClient: huggingface_hub.AsyncInferenceClient, chat_completion

4. All clients decorated with @retry(stop_after_attempt=3, wait_exponential(min=2, max=30))

5. _CLIENTS dict mapping LLMProvider → client class

6. Factory functions:
   - get_llm_client(provider?, model?) — defaults to cfg.generator.provider / cfg.generator.model. Validates secrets.has_key() first, raises ValueError with clear message if missing.
   - get_llm_for_role(role: LLMRole) -> BaseLLMClient — convenience for cfg.generator, cfg.consensus, cfg.revision

Commit: "feat: unified async LLM client (4 providers)"
```

### Prompt 2.2 — Scopus scraper

```
Write src/scrapers/scopus_client.py — Scopus API client for literature search.

Import from src.config.settings: cfg, secrets

Implement:

1. ScopusArticle dataclass: scopus_id, title, authors, journal, year, doi, abstract, citation_count, keywords (list), url. Property: apa_reference.

2. ScopusScraper class:
   - __init__: reads secrets.scopus_api_key, secrets.scopus_inst_token, builds headers
   - is_available property: returns cfg.scopus_enabled AND key is non-empty
   - search(): paginated Scopus Search API via httpx.AsyncClient
   - get_abstract(): fetches full abstract from Abstract Retrieval API
   - search_for_proposal(topic, keywords, max_results?, year_from?):
     • max_results defaults to cfg.scopus_max_results (100 per config.yaml)
     • year_from defaults to cfg.scopus_year_from (2019)
     • Multi-query: main topic search + per-keyword searches
     • Deduplicates, sorts by citation count
     • If cfg.scopus_enrich_abstracts: fetches abstracts for top cfg.scopus_top_abstracts (30) articles
   - format_references_apa(articles, max_refs=30)

Commit: "feat: Scopus client (config-driven limits)"
```

---

## Phase 3 — Data Models

### Prompt 3.1 — Pydantic models

```
Write src/generators/models.py — Pydantic v2 data models for the full proposal lifecycle.

Import ProjectType and DeliverableType from src.config.fct_constants.

Implement:

1. TeamMember: name, email, institution, role (pi/co_pi/team_member/to_hire/consultant), expertise, orcid

2. DraftIdea — PI's minimal input (placed in the drafts/ folder as YAML):
   - title (required, max 255), title_pt, acronym (max 15), typology (ProjectType, default ICDT)
   - research_topic (required), research_questions, keywords_en/pt (max 4)
   - scientific_domain/area/subarea
   - pi (TeamMember|None), team_members, hirings_planned
   - principal_contractor (default "Universidade de Aveiro"), research_units (max 3), participating/collaborative_institutions
   - pi_career_summary, related_publications, related_projects, methodology_notes, budget_notes, ethical_considerations
   - sdg_alignment (list[int], max 3, values 1-17)
   - target_start_date, duration_months (0 = use max for typology), estimated_budget

3. TaskBudget: human_resources, missions_travel, equipment, consumables, services, registrations_publications, other. Properties: direct_costs, indirect_costs (25%), total.

4. ProposalTask: number, denomination (max 150), description (max 4000), expected_results, assigned_members, person_months, start_month, duration_months, budget (TaskBudget), cost_justification (max 2500)

5. Deliverable: code, title, type (DeliverableType), description (max 800), related_tasks, due_month

6. Milestone: code, denomination, description (max 300), related_tasks, due_month

7. Proposal — complete myFCT form with all fields and max_lengths matching CharLimits. Include char_count_report() method.

8. CriterionScore, ReviewReport, ConsensusReport for the review lifecycle.

Commit: "feat: Pydantic data models"
```

---

## Phase 4 — Generator

### Prompt 4.1 — Proposal generator

```
Write src/generators/proposal_generator.py.

ProposalGenerator:
- Reads LLM from get_llm_for_role(cfg.generator), Scopus from ScopusScraper
- generate(draft: DraftIdea) -> Proposal:
  1. Apply config.yaml defaults (cfg.typology, cfg.principal_contractor, cfg.default_research_units)
  2. Scopus literature search if available
  3. Generate sections sequentially with coherence: abstract_en, abstract_pt, state_of_art_objectives, research_plan_methods, institution_description, management_structure, ethics_justification
  4. PI narrative sections if pi_career_summary provided
  5. Team synopsis if team_members provided
  6. Tasks, deliverables, milestones as JSON
  7. Budget estimation
- Each section: tailored prompt with FCT criteria context, character limit enforcement, trim if over limit
- Temperature from cfg.generator.temperature

The draft files live in the drafts/ folder and are loaded by path:
  fct-engine generate -i drafts/my_idea.yaml

Commit: "feat: proposal generator"
```

---

## Phase 5 — Review Panel

### Prompt 5.1 — Multi-model reviewer + consensus + revision

```
Write src/reviewers/panel_reviewer.py with three classes.

1. AIReviewer:
   - Built from ReviewerDef (one config.yaml panel entry)
   - System prompt = definition.persona (verbatim from config.yaml)
   - Reviews proposal, returns structured JSON ReviewReport

2. ReviewPanel:
   - Builds roster from cfg.enabled_reviewers
   - Runs all in parallel with asyncio.gather
   - Aggregates scores using FCT weights (A:40%, B:30%, C:30%)
   - Consensus LLM from get_llm_for_role(cfg.consensus) writes panel narrative

3. RevisionEngine:
   - Uses get_llm_for_role(cfg.revision)
   - Maps low-scoring criteria to proposal sections, rewrites with feedback

CRITICAL: reviewer personas come from definition.persona (config.yaml), NOT hard-coded.

Commit: "feat: multi-model AI peer review panel"
```

---

## Phase 6 — Pipeline & Interfaces

### Prompt 6.1 — Pipeline

```
Write src/generators/pipeline.py.

Pipeline.run(draft, iterations?, output_dir?):
- iterations defaults to cfg.iterations (3)
- output_dir defaults to cfg.output_dir / timestamp
- Generate → Review → Revise loop with cfg.stop_on_accept
- Final outputs per cfg.out_json, cfg.out_markdown, cfg.out_char_report

Also: run_pipeline(draft_path, ...) convenience that loads YAML from drafts/ folder.

Commit: "feat: pipeline orchestrator"
```

### Prompt 6.2 — CLI

```
Write src/cli.py using Click + Rich.

Root group: -v/--verbose, -c/--config <path>

Commands:
  generate -i <draft> -o <dir>     (e.g., -i drafts/my_idea.yaml)
  review -i <proposal.json> -o <dir>
  pipeline -i <draft> -o <dir> -n <iterations>
  config --show                     (resolved settings + API key status)

Entry point: fct-engine = "src.cli:main"

All -i paths work relative to project root, so drafts/example_idea.yaml works directly.

Commit: "feat: CLI"
```

### Prompt 6.3 — FastAPI

```
Write src/api/app.py — FastAPI REST API.

Endpoints:
  GET  /health, /config (resolved, no secrets), /rules (FCT constants)
  POST /generate, /review, /pipeline (async jobs)
  GET  /jobs/{job_id}
  POST /validate (char limits), /config/reload

Commit: "feat: FastAPI REST API"
```

---

## Phase 7 — Tests & Data Files

### Prompt 7.1 — Tests

```
Write tests/test_core.py with pytest.

Test classes: TestFCTConstants, TestConfigLoading, TestDraftIdea, TestProposal, TestLLMFactory.
Verify constants, config.yaml loading, model validation, budget calculations.
TestDraftIdea should load drafts/example_idea.yaml and check acronym == "DigiResilient".

Commit: "test: unit tests"
```

### Prompt 7.2 — Data files and example draft

```
Write:

1. data/rules/evaluation_criteria.json — structured FCT evaluation criteria
2. data/schemas/draft_idea.json — JSON Schema for validating draft idea YAML files in drafts/
3. drafts/example_idea.yaml — complete DigiResilient example (SR&TD, UA/GOVCOPP, 36mo, €200k, mixed-methods, SDGs 8/9/12)

The example_idea.yaml demonstrates the full format for files placed in drafts/.

Commit: "feat: evaluation rules, schema, example draft"
```

---

## Phase 8 — Documentation

### Prompt 8.1 — README.md

```
Rewrite README.md centred on config.yaml and the drafts/ workflow.

Key changes from the existing README:
- Quick Start clones from https://github.com/dpolonia/202602-fct-proposal-engine
- Explain the drafts/ folder: "Place your preliminary research ideas in drafts/ as YAML files"
- Show the workflow: "1. Write idea in drafts/my_project.yaml → 2. Run pipeline → 3. Get proposal in output/"
- Provider table with current models: claude-opus-4-6, gpt-5.2-2025-12-11, gemini-3.1-pro-preview
- Reviewer IDs: claude_rigor, openai_innovation, gemini_feasibility, llama_domain
- Architecture diagram with updated reviewer names
- Project structure tree showing drafts/ with README.md and example_idea.yaml

Commit: "docs: README (updated repo URL, drafts/ workflow, current models)"
```

### Prompt 8.2 — CLAUDE.md

```
Rewrite CLAUDE.md for Claude Code context.

Include:
- Project purpose, repo URL (https://github.com/dpolonia/202602-fct-proposal-engine)
- Two-file config architecture (config.yaml vs .env)
- Drafts folder: "User-provided research ideas go in drafts/ as YAML files. The pipeline reads from here."
- cfg.* and secrets.* usage patterns (with current model names)
- Source map, FCT rules, adding reviewers, adding providers
- Code style: Python 3.11+, async, Pydantic v2, ruff (100 chars)

Commit: "docs: CLAUDE.md (updated)"
```

### Prompt 8.3 — Configuration reference

```
Write docs/CONFIGURATION.md — exhaustive reference for config.yaml.

Tables for all 8 sections. Include the drafts/ folder convention:
- Drafts placed in drafts/*.yaml are the pipeline input
- config.yaml project defaults are applied when a draft doesn't specify its own values

Commit: "docs: CONFIGURATION.md"
```

---

## Phase 9 — Infrastructure

### Prompt 9.1 — pyproject.toml

```
Rewrite pyproject.toml:
- name = "fct-proposal-engine"
- All dependencies (anthropic, openai, google-genai, huggingface-hub, fastapi, pydantic, pydantic-settings, httpx, pyyaml, click, rich, tenacity, etc.)
- Dev dependencies (pytest, ruff, mypy, pre-commit)
- Entry point: fct-engine = "src.cli:main"
- Ruff line-length=100, target py311

Commit: "chore: pyproject.toml"
```

### Prompt 9.2 — Docker + Compose

```
Write Dockerfile (copies config.yaml + src + data + drafts) and docker-compose.yml (api + redis, volume-mounts drafts/ and output/).

The drafts/ folder is mounted as a volume so users can add new idea files without rebuilding the image.

Commit: "chore: Docker + Compose"
```

### Prompt 9.3 — Terraform + deploy script

```
Write infra/terraform/main.tf (GCP Cloud Run, Artifact Registry, Secret Manager, GCS bucket) and scripts/deploy.sh (--init and deploy modes).

Commit: "infra: Terraform + deploy"
```

### Prompt 9.4 — GitHub Actions

```
Write .github/workflows/ci.yml:
- On push/PR to main
- test job: ruff, mypy, pytest
- deploy job (main only): GCP Workload Identity → docker build → Cloud Run deploy

Commit: "ci: GitHub Actions"
```

### Prompt 9.5 — Makefile

```
Write Makefile with targets: install, dev, test, lint, format, serve, config, generate, review, pipeline (using drafts/example_idea.yaml), docker-build, docker-run, docker-stop, deploy-init, deploy, deploy-infra, clean.

Commit: "chore: Makefile"
```

---

## Phase 10 — Verify & Tag

### Prompt 10.1 — Consistency pass

```
Run these checks and fix any issues:

1. grep -rn for hard-coded old model names in src/ (e.g., "claude-sonnet-4-5-20250929", "gpt-4o", "gemini-2.5-pro") — should be NONE. Only "claude-opus-4-6" as default in settings.py.
2. grep for "from src.config.settings import settings" — should be "cfg, secrets" everywhere.
3. grep for "gpt4o_innovation" — should be "openai_innovation".
4. Verify drafts/README.md exists and describes the folder.
5. Verify drafts/example_idea.yaml exists and loads.
6. Remove any remaining Zone.Identifier files: find . -name "*:Zone.Identifier" -delete
7. Run: pip install -e ".[dev]" && pytest tests/ -v
8. Run: ruff check src/ tests/
9. Run: fct-engine config --show

Commit fixes: "fix: consistency pass"
```

### Prompt 10.2 — Integration test

```
Write tests/test_integration.py:
- Mock all LLM clients and ScopusScraper
- Load drafts/example_idea.yaml
- Run Pipeline().run(draft, iterations=1)
- Assert: non-empty sections, char limits respected, ≥1 review, score 1-10, output exists

Commit: "test: integration test (mocked)"
```

### Prompt 10.3 — Push and tag

```
1. git status — should be clean
2. make test && make lint
3. git tag -a v0.1.0 -m "Initial release: FCT Proposal Engine"
4. git push origin main --tags
5. Print file listing and line counts
```

---

## Prompt Index

| #    | Phase     | Key File(s)                          | Depends on |
|------|-----------|--------------------------------------|------------|
| 0.1  | Clone     | clone repo, drafts/README.md         | —          |
| 1.1  | Config    | src/config/settings.py               | 0.1        |
| 1.2  | Config    | src/config/fct_constants.py          | 0.1        |
| 1.3  | Config    | .env.example                         | 0.1        |
| 2.1  | LLM       | src/utils/llm_client.py              | 1.1        |
| 2.2  | Scopus    | src/scrapers/scopus_client.py        | 1.1, 1.2   |
| 3.1  | Models    | src/generators/models.py             | 1.2        |
| 4.1  | Generator | src/generators/proposal_generator.py | 2.1, 2.2, 3.1 |
| 5.1  | Reviewer  | src/reviewers/panel_reviewer.py      | 2.1, 3.1   |
| 6.1  | Pipeline  | src/generators/pipeline.py           | 4.1, 5.1   |
| 6.2  | CLI       | src/cli.py                           | 6.1        |
| 6.3  | API       | src/api/app.py                       | 4.1, 5.1, 6.1 |
| 7.1  | Tests     | tests/test_core.py                   | 1.1, 1.2, 3.1 |
| 7.2  | Data      | data/*, drafts/example_idea.yaml     | 1.2        |
| 8.1  | Docs      | README.md                            | all        |
| 8.2  | Docs      | CLAUDE.md                            | all        |
| 8.3  | Docs      | docs/CONFIGURATION.md                | 1.1        |
| 9.1  | Infra     | pyproject.toml                       | —          |
| 9.2  | Infra     | Dockerfile, docker-compose.yml       | 9.1        |
| 9.3  | Infra     | infra/terraform/*, scripts/*         | —          |
| 9.4  | Infra     | .github/workflows/ci.yml             | 9.1        |
| 9.5  | Infra     | Makefile                             | 9.1        |
| 10.1 | Polish    | (fixes + Zone.Identifier cleanup)    | all        |
| 10.2 | Polish    | tests/test_integration.py            | all        |
| 10.3 | Polish    | git tag v0.1.0 + push                | 10.1, 10.2 |
