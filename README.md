# FCT Proposal Engine

AI-powered proposal generator, multi-model peer reviewer, and compliance validator for **FCT PTDC 2025** R&D project grants (*Projetos de I&D em Todos os Domínios Científicos* / *Projetos Exploratórios*).

Takes a structured draft research idea (YAML) and produces a submission-ready proposal through an automated pipeline: literature-backed generation, configurable multi-model blind peer review, iterative revision with structured critique atomization, and regulatory compliance validation against ~90 rules derived from FCT Regulation 5/2024 and the RD2025 Application Guide.

---

## Table of Contents

- [What It Does](#what-it-does)
- [What It Does Not Do](#what-it-does-not-do)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Pipeline Overview](#pipeline-overview)
- [Input: Draft Idea Format](#input-draft-idea-format)
- [Output: Proposal Structure](#output-proposal-structure)
- [Review System](#review-system)
- [Review-Iterate System](#review-iterate-system)
- [Compliance Validation](#compliance-validation)
- [Cost Tracking](#cost-tracking)
- [CLI Commands](#cli-commands)
- [REST API](#rest-api)
- [FCT Regulatory Constants](#fct-regulatory-constants)
- [Security](#security)
- [Project Structure](#project-structure)
- [Deployment](#deployment)
- [Testing](#testing)
- [License](#license)

---

## What It Does

1. **Generates complete FCT PTDC proposals** from a short research idea description (~200 words minimum), producing all required sections: abstracts (EN/PT), state of the art, research plan, tasks, deliverables, milestones, budget, team CVs, ethics justification, and management structure — each respecting FCT character limits.

2. **Searches Scopus** for relevant literature (when a Scopus API key is provided) and integrates citations into the state-of-the-art and methodology sections with APA-formatted references.

3. **Runs blind peer review** through a configurable panel of AI reviewers (each can use a different LLM provider/model/persona), scoring against the three FCT evaluation criteria (A: Scientific Merit 40%, B: PI and Team 30%, C: Feasibility 30%) and producing structured feedback with per-criterion scores, strengths, weaknesses, and revision recommendations.

4. **Iteratively revises** the proposal based on reviewer feedback using a structured 6-step process: critique atomization, grading, priority ranking, section-by-section revision, consistency checking, and improvement reporting — with full traceability of what changed and why.

5. **Validates regulatory compliance** against ~90 rules across 7 categories (character limits, eligibility, work plan structure, budget arithmetic, UA internal rules, ethics, and evaluation alignment), producing a color-coded Compliance Fulfilment Annex.

6. **Tracks LLM costs** per API call, per step, and per model, generating cost reports for each review-iterate cycle.

7. **Exports** to JSON, Markdown, DOCX, and plain text, organized in timestamped output directories.

## What It Does Not Do

- **Does not submit proposals to FCT.** It generates files you review, edit, and submit manually through the FCT portal.
- **Does not replace human judgment.** The generated text is a starting point. All content should be reviewed and refined by the research team before submission.
- **Does not guarantee funding.** AI-generated proposals are tools to accelerate writing, not substitutes for genuine research ideas and track records.
- **Does not verify eligibility conditions that require external data** (e.g., PI participation limits, sanctions, duplicate funding checks, institutional contracts). These are flagged as warnings requiring manual verification.
- **Does not access the FCT submission portal**, MyFCT, CIENCIAVITAE, or any Portuguese government systems.
- **Does not store or transmit personal data externally.** PII is scrubbed before sending to LLMs, and all outputs remain local.
- **Does not handle the Commitment Declaration** (*Declaração de Compromisso*) or institutional approval workflows — those are administrative processes external to proposal content.

---

## Quick Start

```bash
git clone https://github.com/dpolonia/202602-fct-proposal-engine.git
cd fct-proposal-engine

# 1. Install
pip install -e ".[dev]"

# 2. Secrets (API keys only)
cp .env.example .env          # fill in your keys

# 3. Configure everything else
nano config.yaml              # providers, models, typology, panel, output...

# 4. Run
fct-engine pipeline -i drafts/example_idea.yaml
```

You only need API keys for the LLM providers you enable in `config.yaml`. At minimum, one provider key is required.

---

## Configuration

The engine uses a **two-file** configuration model:

| File | Purpose | Git-tracked? |
|------|---------|:------------:|
| **`config.yaml`** | All user preferences: LLM providers/models, typology, review panel, Scopus settings, pipeline behavior, output formats, compliance config | Yes |
| **`.env`** | API keys and secrets only | No |

### `config.yaml` — what you can control

```yaml
# Project defaults (applied when the draft doesn't specify them)
project:
  typology: "SR&TD"                    # or "PEX"
  principal_contractor: "Universidade de Aveiro"
  default_research_units: ["GOVCOPP"]

# LLM assignment per pipeline role (each can use a different provider/model)
llm:
  generator:   { provider: anthropic, model: claude-opus-4-6, temperature: 0.7 }
  consensus:   { provider: anthropic, model: claude-opus-4-6, temperature: 0.3 }
  revision:    { provider: anthropic, model: claude-opus-4-6, temperature: 0.3 }

# AI peer-review panel (add, remove, or disable reviewers freely)
review_panel:
  - id: claude_rigor
    enabled: true
    provider: anthropic
    model: claude-opus-4-6
    perspective: scientific_rigor
    focus_criteria: [A1, B1]
    persona: "Senior methodologist, sceptical examiner..."
  - id: openai_innovation
    enabled: true
    provider: openai
    model: gpt-5.2-2025-12-11
    perspective: innovation
    focus_criteria: [A2, A1]

# Pipeline behavior
pipeline:
  iterations: 3                        # max generate-review-revise cycles
  stop_on_accept: true                 # stop early if panel accepts
  save_intermediates: true             # save v1, v2... alongside final
  review_iterate_enabled: true         # use structured 6-step revision (vs. simple)
  review_iterate_top_n: 5             # top-N suggestions applied per iteration
  review_iterate_max_suggestions: 20  # max suggestions extracted per cycle
  review_iterate_include_trivial: true # also apply trivial (F0) fixes

# Scopus literature search
scopus:
  enabled: true
  max_results: 100
  year_from: 2019

# Compliance validation
compliance:
  enabled: true
  run_before_review: true
  run_after_revision: true
  feed_to_review_iterate: true        # inject compliance failures as priority suggestions
  disabled_rules: []                   # e.g., ["UA01", "UA02"]
  disabled_categories: []              # e.g., ["UA"]

# Output formats
output:
  dir: "output"
  formats: { json: true, markdown: true, docx: false, txt: true, char_report: true }
```

### Supported LLM providers

| Provider | `config.yaml` value | Model examples | `.env` key |
|----------|---------------------|----------------|------------|
| Anthropic | `anthropic` | `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001` | `ANTHROPIC_API_KEY` |
| OpenAI | `openai` | `gpt-5.2-2025-12-11`, `gpt-5.2-pro-2025-12-11`, `gpt-5-mini-2025-08-07` | `OPENAI_API_KEY` |
| Google | `google` | `gemini-3.1-pro-preview`, `gemini-2.5-flash`, `gemini-3-flash-preview` | `GOOGLE_API_KEY` |
| HuggingFace | `huggingface` | `meta-llama/Llama-3.1-70B-Instruct` | `HUGGINGFACE_API_KEY` |

All LLM calls use async clients with exponential backoff retries (3-4 attempts, 2-60s) for transient errors (429, 5xx, timeouts). Secrets are never logged — all error messages pass through `redact_secrets()`.

### Adding a new reviewer

Edit `config.yaml` and add an entry under `review_panel:`. No code changes needed — the panel auto-discovers from config.

### Adding a new LLM provider

1. Extend `BaseLLMClient` in `src/utils/llm_client.py`
2. Register it in the `_CLIENTS` dict
3. Add the provider name to `LLMProvider` enum in `src/config/settings.py`

### Inspect resolved configuration

```bash
fct-engine config --show
```

---

## Pipeline Overview

The `Pipeline.run()` method orchestrates the full proposal lifecycle:

```
Draft Idea (YAML)
      │
      ▼
┌─ 1. GENERATE ───────────────────────────────────────────┐
│  ProposalGenerator + Scopus literature search            │
│  → v1 Proposal (all sections, tasks, budget)            │
└──────────────────────────────────────────────────────────┘
      │
      ▼
┌─ 2. COMPLIANCE CHECK (optional) ────────────────────────┐
│  ~90 rules: char limits, eligibility, budget, ethics...  │
│  → ComplianceReport with PASS/FAIL/WARN per rule        │
└──────────────────────────────────────────────────────────┘
      │
      ▼
┌─ 3. REVIEW-REVISE LOOP (N iterations) ──────────────────┐
│                                                          │
│  3a. Blind peer review (multi-model panel)               │
│      → ConsensusReport with scores + feedback            │
│                                                          │
│  3b. Early stop? (if panel accepts and stop_on_accept)   │
│                                                          │
│  3c. Draft update (evolve the original idea)             │
│                                                          │
│  3d. Structured revision (6-step review-iterate)         │
│      → Revised proposal + ImprovementReport              │
│                                                          │
│  3e. Compliance re-check (delta vs. previous)            │
│                                                          │
└──────────────────────────────────────────────────────────┘
      │
      ▼
┌─ 4. FINAL OUTPUTS ──────────────────────────────────────┐
│  JSON, Markdown, DOCX, TXT, char report,                │
│  compliance annex, cost reports                          │
└──────────────────────────────────────────────────────────┘
```

### Output directory structure

Each pipeline run creates a timestamped directory:

```
output/YYYYMMDD_HHMMSS/
├── proposals/
│   ├── v1_proposal.json          # intermediate versions (if save_intermediates)
│   ├── v1_proposal.txt
│   ├── v2_proposal.json
│   ├── final_proposal.json       # final version
│   ├── final_proposal.txt
│   └── final_proposal.docx
├── reviews/
│   ├── v1_review.json            # per-iteration review reports
│   ├── v1_review.txt
│   └── final_review.docx
├── improvements/
│   ├── application_v2.md         # full proposal as markdown (per revision)
│   ├── improvement_report_v2.md  # what changed and why
│   ├── improvement_report_v2.json
│   ├── llm_cost_report_v2.json   # token counts and costs
│   └── llm_cost_report_v2.md
├── compliance/
│   ├── v1_compliance.json        # per-version compliance results
│   ├── v2_compliance.json
│   ├── compliance_annex.docx     # color-coded final annex
│   ├── compliance_report.md
│   └── compliance_improvements.json
├── drafts/
│   ├── original_draft.yaml       # input backup
│   ├── draft_pre_v2.yaml         # draft before each revision
│   ├── draft_diff_v2.txt         # what changed in the draft
│   └── draft_changes_v2.json
└── summary/
    ├── proposal_summary.md
    ├── proposal_summary.docx
    ├── char_report.json           # character counts vs. limits
    └── char_report.txt
```

---

## Input: Draft Idea Format

The input is a YAML file. Only two fields are required:

```yaml
# Required
title: "Digital Twins for Portuguese Public Service Delivery"
research_topic: |
  This project investigates the application of digital twin technology
  to model and optimize public service delivery in Portuguese municipalities...

# Optional — everything below has sensible defaults
title_pt: "Gémeos Digitais para a Prestação de Serviços Públicos Portugueses"
acronym: "DigiTwinGov"
typology: "SR&TD"                    # or "PEX"
duration_months: 36                  # 0 = use max for typology
estimated_budget: 240000

research_questions:
  - "How can digital twins model citizen service journeys?"
  - "What efficiency gains are achievable in Portuguese municipalities?"

keywords_en: [digital twins, public administration, service delivery, Portugal]
keywords_pt: [gémeos digitais, administração pública, prestação de serviços, Portugal]

scientific_domain: "Social Sciences"
scientific_area: "Political Science and Public Administration"
scientific_subarea: "Public Administration"

pi:
  name: "João Silva"
  email: "joao.silva@ua.pt"
  institution: "Universidade de Aveiro"
  role: pi
  expertise: "e-Government, digital transformation"
  orcid: "0000-0001-8194-4713"

team_members:
  - name: "Ana Costa"
    institution: "Universidade de Aveiro"
    role: co_pi
    expertise: "Public policy, service design"

research_units: ["GOVCOPP"]
principal_contractor: "Universidade de Aveiro"

pi_career_summary: |
  Prof. Silva has 15 years of experience in e-Government research...

methodology_notes: |
  Mixed-methods: agent-based simulation + qualitative case studies...

ethical_considerations: |
  The project involves surveys with municipal employees (informed consent)...

sdg_alignment: [9, 11, 16]          # max 3 SDGs
```

See `drafts/example_idea.yaml` for a complete annotated template, and `data/schemas/draft_idea.json` for the JSON schema.

---

## Output: Proposal Structure

The generated `Proposal` contains all fields required by the FCT PTDC submission form:

| Section | Field | Max chars |
|---------|-------|-----------|
| **General** | `title_en`, `title_pt` | 255 |
| | `acronym` | 15 |
| | `keywords_en`, `keywords_pt` | 4 each |
| **Abstracts** | `abstract_en`, `abstract_pt` | 5,000 |
| **Scientific Merit** | `state_of_art_objectives` | 6,000 |
| | `research_plan_methods` | 10,000 |
| | `bibliographic_references` | 10,000 |
| **PI CV** | `career_profile` | 4,000 |
| | `contributions_new_ideas` | 5,000 |
| | `contributions_teams` | 3,000 |
| | `contributions_society` | 3,000 |
| | `further_details` | 5,000 |
| | `why_timely_pex` (PEX only) | 3,000 |
| **Team** | `team_cv_synopsis` | 10,000 |
| **Work Plan** | `tasks[]` (each: denomination, description, person-months, timeline, budget) | 150 / 4,000 / 2,500 |
| | `deliverables[]` (code, title, description, due month) | 800 |
| | `milestones[]` (code, denomination, description, due month) | 300 |
| **Management** | `management_structure` | 3,000 |
| | `institution_description` | 1,500 |
| **Ethics** | `ethics_justification` | 3,000 |
| **Budget** | `total_budget`, per-task breakdown with 7 cost categories | — |

Budget breakdown per task includes: human resources, missions/travel, equipment, consumables, services, registrations/publications, and other costs. Indirect costs (25% of direct) are computed automatically.

---

## Review System

The review panel simulates international peer review following FCT evaluation criteria:

### Panel composition

Each reviewer in `config.yaml` defines:
- **Provider and model** — can mix Anthropic, OpenAI, Google, HuggingFace
- **Perspective** — e.g., `scientific_rigor`, `innovation`, `feasibility`, `domain_expert`
- **Focus criteria** — which FCT criteria to emphasize (A1, A2, B1, B2, C)
- **Persona** — custom system prompt describing the reviewer's expertise

### Blind review

Before sending the proposal to reviewers, the engine:
1. Replaces the PI's name with "the Principal Investigator"
2. Replaces each team member's name with "Team Member N"
3. Removes email addresses, phone numbers, and tax IDs
4. Preserves ORCID, institutions, and research metrics

This mirrors real FCT peer review where evaluator identity is hidden.

### Scoring

Each reviewer produces scores on a 1-10 scale for:
- **A1** — Scientific merit (originality, theoretical contribution)
- **A2** — Innovative nature (novelty, risk-reward)
- **B1** — PI track record (publications, leadership, h-index)
- **B2** — Team composition (complementarity, expertise)
- **C** — Feasibility (methodology, timeline, budget, management)

The consensus engine aggregates scores using FCT weights:
```
Final Score = A×0.4 + B×0.3 + C×0.3
where A = A1×0.5 + A2×0.5
      B = B1×0.6 + B2×0.4
```

Panel decision thresholds: accept (score >= 8.0 and all reviewers accept/minor), minor revision (>= 6.5), major revision (>= 5.0), reject (< 5.0).

---

## Review-Iterate System

When `review_iterate_enabled: true` (default), the engine uses a structured 6-step revision process instead of simple text rewriting:

### Step 1-3: Atomize, Grade, and Rank (1 LLM call)

Reviewer feedback is decomposed into individual `SuggestionRecord` objects, each graded on 7 dimensions:

| Dimension | Levels | Purpose |
|-----------|--------|---------|
| **Severity** | S3 (fatal), S2 (major), S1 (moderate), S0 (minor) | Priority ordering |
| **Evidence** | E2 (direct quote), E1 (implicit), E0 (speculative) | Credibility filtering |
| **Confidence** | C2 (high), C1 (medium), C0 (low) | Reliability weighting |
| **Effort** | F3 (redesign), F2 (rewrite), F1 (small edit), F0 (trivial) | Cost estimation |
| **Impact** | I3 (large uplift), I2 (noticeable), I1 (minor), I0 (negligible) | Benefit estimation |
| **Dependency** | D2 (unlocks many), D1 (unlocks one), D0 (independent) | Ordering |
| **Actionability** | A2 (fully actionable), A1 (partial), A0 (vague) | Feasibility |

Suggestions are ranked by severity (desc) > impact (desc) > dependency (desc) > effort (asc), and the top-N are selected for application. Previously addressed suggestions (from prior iterations) are filtered out.

If compliance validation is enabled, compliance failures are injected as high-priority suggestions (BLOCKER maps to S3, CRITICAL to S2, etc.).

### Step 4: Apply fixes (1 LLM call per affected section)

Suggestions are batched by target section. Each section gets one LLM call with the current text, all applicable suggestions, and their acceptance tests. The revised text is truncated to respect FCT character limits.

### Step 5: Build improvement report (1 LLM call)

Generates a structured narrative covering: executive summary, science/methodology changes, feasibility/budget changes, ethics/compliance changes, and a risk register.

### Step 6: Consistency checks (1 structural + 1 LLM call)

- **Budget totals reconcile** — tasks sum within 5% of `total_budget`
- **Timeline-ethics gate** — if tasks mention human subjects, ethics must address timing
- **Country set consistent** — abstracts and plan reference the same countries
- **Hypotheses traceability** — research questions map to tasks and deliverables
- **Ethics-human subjects consistency** — work plan and ethics section agree
- **Benchmarks independence** — minimum viable analysis package

### Readiness index and stoplight

Each iteration produces a **readiness index** (0-100) penalized by unresolved suggestions and a **stoplight table** (green/amber/red per criterion) for quick assessment.

---

## Compliance Validation

The compliance validator checks the proposal against ~90 rules across 7 categories, using pure Python (no LLM calls):

| Category | Rules | Examples |
|----------|-------|---------|
| **CL** (Character Limits) | CL01-CL28 | Title <= 255 chars, abstract <= 5000, task description <= 4000, 95% safety margin warning |
| **E** (Eligibility) | E01-E11 | Valid typology, duration within limits, budget within cap, keyword count, SDG count <= 3 |
| **WP** (Work Plan) | WP01-WP14 | At least 1 task, tasks cover duration, deliverables reference valid tasks, non-empty sections |
| **BG** (Budget) | BG01-BG10 | Budget <= typology max, indirect = 25% of direct, task budgets sum correctly, no negatives |
| **UA** (UA Internal) | UA01-UA13 | Minimum budget >= 15k, project start >= 2027, internal approvals (manual verification) |
| **ET** (Ethics) | ET01-ET08 | If work plan mentions human subjects/personal data/health data, ethics section must acknowledge |
| **EV** (Evaluation) | EV01-EV09 | SOA mentions innovation, plan describes methodology, career profile mentions publications |

### Severity levels

- **BLOCKER** — Disqualifying if not fixed (e.g., title exceeds 255 chars, budget exceeds typology cap)
- **CRITICAL** — Must fix before submission (e.g., empty required sections)
- **MAJOR** — Should fix to improve evaluation (e.g., no methodology keywords in research plan)
- **MINOR** — Nice to fix (e.g., field at >95% of character limit)

Rules that cannot be auto-checked (e.g., "PI must have a valid employment contract") produce **WARN** status with advisory notes for manual verification.

### Output formats

- **Color-coded DOCX** — Compliance Fulfilment Annex with green/red/amber/yellow cell shading
- **Markdown report** — Findings grouped by category with summary statistics
- **JSON improvements** — FAIL findings only, sorted by severity, for programmatic consumption
- **SuggestionRecord conversion** — Feeds directly into the review-iterate pipeline as priority suggestions

### Delta tracking

When run after revision, the validator computes a delta vs. the previous report: which rules were resolved, which persist, which are new failures, and which are regressions (was PASS, now FAIL).

---

## Cost Tracking

When `review_iterate_enabled: true`, every LLM call is tracked:

- **Per-call**: model, provider, input/output tokens, cost in USD, timestamp
- **Per-step**: atomize, revise_{section}, consistency_llm, narrative
- **Per-model**: aggregate costs across all calls

Pricing covers all supported models (Claude Opus/Sonnet/Haiku, GPT-4o/4o-mini/4-turbo, o3-mini, Gemini Pro/Flash, Llama). Unrecognized models use a conservative default ($5/$15 per 1M tokens).

Cost reports are saved as both JSON and Markdown per iteration in `improvements/`.

---

## CLI Commands

```bash
# Full pipeline: generate -> review -> revise (N iterations)
fct-engine pipeline -i drafts/my_idea.yaml [-o output/] [-n 3]

# Generate a proposal without review
fct-engine generate -i drafts/my_idea.yaml [-o output/]

# Peer-review an existing proposal JSON
fct-engine review -i proposals/proposal.json [-o output/]

# Show resolved configuration and API key status
fct-engine config --show

# Use a different config file
fct-engine -c my_config.yaml pipeline -i draft.yaml

# Verbose logging
fct-engine -v pipeline -i draft.yaml
```

---

## REST API

The engine also exposes a FastAPI server for programmatic access:

```bash
# Start the server
uvicorn src.api.app:app --host 0.0.0.0 --port 8080
```

### Endpoints

| Method | Path | Auth | Description |
|--------|------|:----:|-------------|
| `GET` | `/health` | No | Health check: `{"status": "ok", "ts": "..."}` |
| `GET` | `/config` | Yes | Resolved configuration (no secrets) |
| `GET` | `/rules` | Yes | FCT constants: typology rules, char limits, eval criteria |
| `POST` | `/generate` | Yes | Submit a `DraftIdea`, returns job ID for async tracking |
| `POST` | `/review` | Yes | Submit a `Proposal`, returns job ID |
| `POST` | `/pipeline` | Yes | Submit `{draft, iterations}`, returns job ID |
| `GET` | `/jobs/{job_id}` | Yes | Poll job status and retrieve results |
| `POST` | `/validate` | Yes | Character count validation against FCT limits |
| `POST` | `/config/reload` | Yes | Hot-reload `config.yaml` |

**Authentication**: Set `FCT_API_KEY` in `.env`. All endpoints except `/health` require the `X-API-Key` header. When unset, the server runs in unauthenticated dev mode with a logged warning.

**Limits**: Max 1000 concurrent jobs, max 10 iterations per pipeline run, 24-hour job TTL.

---

## FCT Regulatory Constants

All FCT rules are codified in `src/config/fct_constants.py` as frozen dataclasses. These are not configurable — they reflect the official regulation.

### IC&DT vs PEX at a glance

Set `project.typology` in `config.yaml`:

| | **SR&TD (IC&DT)** | **PEX (Exploratory)** |
|---|---|---|
| Duration | 36 months (+12 extension) | 18 months (+6 extension) |
| Max funding | 250,000 EUR | 60,000 EUR |
| Initial advance | 30% | 75% |
| Intermediate payments | Yes | No |
| Participating institutions | Allowed | Not allowed |
| Call budget | 80M EUR (~320 projects) | 24M EUR (~400 projects) |

### Evaluation criteria weights

| Criterion | Weight | Sub-criteria |
|-----------|--------|--------------|
| **A** — Scientific merit and innovative nature | 40% | A1 Scientific merit (50%), A2 Innovative nature (50%) |
| **B** — PI merit and research team | 30% | B1 PI merit (60%), B2 Team merit (40%) |
| **C** — Feasibility and management | 30% | — |

Minimum merit threshold: **7.0** on a 1-10 scale.

### Participation limits

- Max 1 application as PI (regardless of typology)
- If PI in one project, max 1 team membership in another
- If not PI, max 2 team memberships
- Max 3 research units per institution
- Max 3 SDG alignments

### Key dates (RD2025)

| Event | Date |
|-------|------|
| Call opens | 2025-11-27 |
| UA internal deadline | 2026-03-06 |
| FCT submission deadline | 2026-03-11 17:00 UTC |
| Commitment declaration | 2026-03-25 17:00 UTC |
| Results notification | ~October 2026 |

---

## Security

### PII protection

Two-tier scrubbing before any text is sent to LLMs:

| Context | Function | Removes | Preserves |
|---------|----------|---------|-----------|
| **Generator** (writes proposal) | `scrub_pii_for_llm()` | Emails, phones (international), NIF, CC/BI | Names, ORCID, institutions |
| **Reviewers** (evaluate blind) | `scrub_identity_for_review()` | All above + PI and team member names | ORCID, institutions, metrics |

**Rationale**: The generator needs names to write natural prose ("Prof. Silva has led..."). Reviewers evaluate blind, mirroring real FCT peer review.

### API security

- **Timing-safe authentication**: API key comparison uses `hmac.compare_digest` to prevent timing attacks
- **Security headers**: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`
- **CORS**: Restricted to configurable origins (default localhost only), credentials disabled
- **Docs disabled in production**: `/docs` and `/redoc` are hidden when `FCT_API_KEY` is set
- **Secret redaction**: All error messages pass through `redact_secrets()` covering 10 API key patterns (Anthropic, OpenAI, Google, HuggingFace, GitHub, Slack, AWS)
- **Path validation**: `validate_path()` prevents directory traversal on all user-supplied file paths

### Pre-commit security gate

A 7-category automated security scanner runs before every commit:

1. **Secrets & Credentials** — API keys in source, `.env` staged, hardcoded passwords
2. **Secrets in Logs** — Secrets in log/print/f-string statements
3. **Architecture** — Direct LLM instantiation (must use factory), hardcoded model names
4. **Input Validation** — Unsafe `yaml.load`, `eval`/`exec`, `shell=True`
5. **Dependencies** — Unpinned versions
6. **Output & Data** — PII in committed files, output dirs in gitignore
7. **Network & API** — TLS verification bypass, plain HTTP, missing timeouts

```bash
# Enable automatic pre-commit hook
git config core.hooksPath .githooks

# Manual full audit
bash scripts/security_check.sh --all
```

### Personal content policy

Personal proposal content (drafts, outputs, API keys) is local-only and never committed to Git. Only `drafts/example_idea.yaml` (the template) is tracked.

---

## Project Structure

```
fct-proposal-engine/
├── config.yaml                        # User settings (models, typology, panel, output)
├── .env                               # Secrets (API keys only, git-ignored)
├── pyproject.toml                     # Dependencies, build config
│
├── src/
│   ├── config/
│   │   ├── settings.py                # UserConfig (config.yaml) + Secrets (.env)
│   │   ├── fct_constants.py           # FCT rules, char limits, eval criteria, typology rules
│   │   └── llm_pricing.py            # Token pricing table for cost tracking
│   │
│   ├── generators/
│   │   ├── models.py                  # DraftIdea, Proposal, ReviewReport, ConsensusReport, etc.
│   │   ├── proposal_generator.py      # DraftIdea -> Proposal (section-by-section LLM generation)
│   │   ├── draft_updater.py           # Evolves draft idea based on review feedback
│   │   ├── pipeline.py                # Orchestrator: generate -> review -> revise loop
│   │   ├── docx_exporter.py           # DOCX export for proposals, reviews, summaries
│   │   └── txt_formatter.py           # Plain text and markdown formatters
│   │
│   ├── reviewers/
│   │   ├── panel_reviewer.py          # Multi-model blind review panel + consensus + revision
│   │   └── review_iterate.py          # 6-step structured revision: atomize, grade, rank, apply, check
│   │
│   ├── compliance/
│   │   ├── models.py                  # ComplianceFinding, ComplianceReport, enums
│   │   ├── registry.py                # Decorator-based rule registration
│   │   ├── validator.py               # Orchestrator: runs all rules, builds report
│   │   ├── rules_char_limits.py       # CL01-CL28 (character limit checks)
│   │   ├── rules_eligibility.py       # E01-E11 (metadata and eligibility)
│   │   ├── rules_work_plan.py         # WP01-WP14 (task/deliverable/milestone cross-references)
│   │   ├── rules_budget.py            # BG01-BG10 (financial arithmetic)
│   │   ├── rules_ua_internal.py       # UA01-UA13 (Universidade de Aveiro internal)
│   │   ├── rules_ethics.py            # ET01-ET08 (keyword-based ethics scanning)
│   │   ├── rules_evaluation.py        # EV01-EV09 (evaluation alignment heuristics)
│   │   ├── docx_exporter.py           # Color-coded Compliance Fulfilment Annex
│   │   └── formatters.py              # Markdown, JSON, SuggestionRecord converters
│   │
│   ├── scrapers/
│   │   └── scopus_client.py           # Scopus API: search, abstract retrieval, APA formatting
│   │
│   ├── utils/
│   │   ├── llm_client.py             # Unified async LLM factory (4 providers)
│   │   ├── sanitize.py               # Secret redaction, PII scrubbing, path validation
│   │   ├── json_utils.py             # Robust JSON extraction from LLM responses
│   │   ├── prompt_loader.py           # Template loading from data/prompts/
│   │   └── text_utils.py             # safe_truncate, safe_limit (sentence-aware truncation)
│   │
│   ├── api/app.py                     # FastAPI REST API
│   └── cli.py                         # Click CLI
│
├── data/
│   ├── prompts/                       # LLM prompt templates (system, section, review, revision)
│   ├── rules/                         # FCT evaluation criteria (JSON)
│   └── schemas/                       # JSON schema for draft idea validation
│
├── drafts/
│   └── example_idea.yaml              # Annotated template (only tracked file)
│
├── tests/
│   ├── test_core.py                   # Constants, config, models, schema validation
│   ├── test_security.py               # PII scrubbing, secret redaction, path traversal, API auth
│   ├── test_compliance.py             # All compliance rules, validator, exporters, formatters
│   ├── test_review_iterate.py         # Atomizer, grading, ranking, consistency, cost tracking
│   ├── test_integration.py            # Full pipeline with mocked LLMs
│   ├── test_draft_updater.py          # Draft evolution and JSON repair
│   └── test_json_utils.py            # JSON extraction edge cases
│
├── scripts/
│   ├── security_check.sh             # 7-category pre-commit security scanner
│   ├── gemini_review.sh              # Gemini-based code audit
│   ├── full_gate.sh                  # Pre-push: security + Gemini audit
│   ├── deploy.sh                     # GCP Cloud Run deployment
│   └── check_api_keys.sh            # API key diagnostic tool
│
├── .githooks/pre-commit              # Automatic security gate
├── Dockerfile                        # Python 3.12 slim, non-root user, port 8080
├── docker-compose.yml                # API + Redis services
├── infra/terraform/                  # GCP Cloud Run IaC
├── CLAUDE.md                         # Instructions for Claude Code (AI assistant)
└── GEMINI.md                         # Instructions for Gemini audit
```

---

## Deployment

### Docker

```bash
# Build and run locally
docker compose up --build

# API available at http://localhost:8080
```

The Docker image runs as a non-root user (`appuser`) with `uvicorn` (2 workers).

### GCP Cloud Run

```bash
# First-time setup (enables APIs, creates secrets in Secret Manager)
./scripts/deploy.sh --init

# Build and deploy
./scripts/deploy.sh
```

Deploys to `europe-west1` with 2 GiB RAM, 2 CPU, 300s timeout, 0-3 auto-scaling instances, authentication required.

### Terraform

```bash
cd infra/terraform
terraform init
terraform apply
```

---

## Testing

```bash
# Run all tests (no API keys needed — all LLM calls are mocked)
pytest tests/ -v

# Run a specific test file
pytest tests/test_compliance.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing
```

257 tests across 7 test files covering:

| Test file | What it covers |
|-----------|---------------|
| `test_core.py` | FCT constants, config loading, Pydantic models, JSON schema validation, text utilities |
| `test_security.py` | 10 API key patterns, PII scrubbing (email, phone, NIF, CC/BI), blind review anonymization, path traversal, API auth structure |
| `test_compliance.py` | All compliance rule categories, validator orchestration, delta tracking, DOCX export, formatters, pipeline integration |
| `test_review_iterate.py` | Suggestion grading, ranking, deduplication, readiness index, stoplight, consistency checks, cost tracking, full revision cycle |
| `test_integration.py` | End-to-end pipeline with mocked LLMs, output file structure, character limit enforcement, PEX typology constraints |
| `test_draft_updater.py` | Draft field updates, malformed JSON recovery, field filtering |
| `test_json_utils.py` | JSON extraction from markdown fences, surrounding text, nested structures, edge cases |

---

## License

MIT
