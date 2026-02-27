# FCT Proposal Engine 🇵🇹🔬

AI-powered proposal generator and multi-model peer reviewer for **FCT PTDC 2025** R&D project grants (*Projetos I&D em Todos os Domínios Científicos*).

Takes a draft research idea → produces a submission-ready proposal → runs it through a panel of AI reviewers simulating international peer review → iteratively revises until the panel is satisfied.

---

## Quick Start

```bash
git clone https://github.com/YOUR_ORG/fct-proposal-engine.git
cd fct-proposal-engine

# 1. Install
pip install -e ".[dev]"

# 2. Secrets (API keys only)
cp .env.example .env          # fill in your keys

# 3. Configure everything else
nano config.yaml              # providers, models, typology, panel, output…

# 4. Run
fct-engine pipeline -i drafts/example_idea.yaml
```

---

## Configuration

The engine uses a **two-file** configuration model:

| File | Purpose | Git-tracked? |
|------|---------|:------------:|
| **`config.yaml`** | All user preferences (models, typology, panel, output) | ✅ Yes |
| **`.env`** | API keys / secrets only | ❌ No |

### `config.yaml` — what you can control

```yaml
# Project defaults applied when the draft doesn't specify them
project:
  typology: "SR&TD"           # or "PEX"
  principal_contractor: "Universidade de Aveiro"
  default_research_units: ["GOVCOPP"]

# Choose which LLM writes each part of the pipeline
llm:
  generator:   { provider: anthropic, model: claude-sonnet-4-5-20250929 }
  consensus:   { provider: anthropic, model: claude-sonnet-4-5-20250929 }
  revision:    { provider: anthropic, model: claude-sonnet-4-5-20250929 }

# Define your AI peer-review panel (add, remove, or disable reviewers)
review_panel:
  - id: claude_rigor
    provider: anthropic
    model: claude-sonnet-4-5-20250929
    perspective: scientific_rigor
    focus_criteria: [A1, B1]
    persona: "Senior methodologist, 15 years on FCT panels…"
  - id: gpt4o_innovation
    provider: openai
    model: gpt-4o
    perspective: innovation
    focus_criteria: [A2, A1]
    # …

# Pipeline behaviour
pipeline:
  iterations: 2
  stop_on_accept: true

# Scopus literature search
scopus:
  enabled: true
  max_results: 40
  year_from: 2019

# Output formats
output:
  dir: "output"
  formats: { json: true, markdown: true, docx: false, char_report: true }
```

**Supported LLM providers:**

| Provider | config.yaml value | Model examples | `.env` key needed |
|----------|-------------------|----------------|-------------------|
| Anthropic | `anthropic` | `claude-sonnet-4-5-20250929`, `claude-opus-4-5-20250918` | `ANTHROPIC_API_KEY` |
| OpenAI | `openai` | `gpt-4o`, `gpt-4o-mini` | `OPENAI_API_KEY` |
| Google | `google` | `gemini-2.5-flash`, `gemini-2.5-pro` | `GOOGLE_API_KEY` |
| HuggingFace | `huggingface` | `meta-llama/Llama-3.1-70B-Instruct` | `HUGGINGFACE_API_KEY` |

You only need API keys for the providers you actually enable.

### Inspect resolved config

```bash
fct-engine config --show
```

---

## Architecture

```
┌───────────────────────────────────────────────────────┐
│  config.yaml   .env                                   │
│       │          │                                     │
│       ▼          ▼                                     │
│   UserConfig   Secrets                                 │
│       │                                                │
│       ├──▶ ProposalGenerator (cfg.generator LLM)       │
│       │         ├─ ScopusScraper (cfg.scopus_*)        │
│       │         └─ Section-by-section generation       │
│       │                     │                          │
│       │                     ▼                          │
│       ├──▶ ReviewPanel (cfg.review_panel[])            │
│       │         ├─ claude_rigor   (Anthropic)          │
│       │         ├─ gpt4o_innovation (OpenAI)           │
│       │         ├─ gemini_feasibility (Google)         │
│       │         └─ llama_domain   (HuggingFace)        │
│       │                     │                          │
│       │                     ▼                          │
│       ├──▶ Consensus (cfg.consensus LLM)               │
│       │                     │                          │
│       │                     ▼                          │
│       └──▶ RevisionEngine (cfg.revision LLM)           │
│                             │                          │
│                             ▼                          │
│            Final Proposal + Review Report               │
│            (.json, .md, .docx per cfg.output)           │
└───────────────────────────────────────────────────────┘
```

---

## Commands

```bash
# Generate a proposal from a draft
fct-engine generate -i drafts/my_idea.yaml -o proposals/

# Peer-review an existing proposal
fct-engine review -i proposals/proposal.json -o reviews/

# Full pipeline (generate → review → revise, N iterations)
fct-engine pipeline -i drafts/my_idea.yaml -n 3

# Show resolved configuration
fct-engine config --show

# Use a different config file
fct-engine -c my_other_config.yaml pipeline -i draft.yaml

# Verbose logging
fct-engine -v pipeline -i draft.yaml
```

---

## Project Structure

```
fct-proposal-engine/
├── config.yaml               ← USER SETTINGS (models, typology, panel…)
├── .env                      ← SECRETS (API keys only)
├── drafts/
│   └── example_idea.yaml     ← sample input
├── src/
│   ├── config/
│   │   ├── settings.py       ← loads config.yaml + .env
│   │   └── fct_constants.py  ← FCT rules, char limits, eval criteria
│   ├── generators/
│   │   ├── models.py         ← DraftIdea, Proposal, Review data models
│   │   ├── proposal_generator.py
│   │   └── pipeline.py       ← orchestrator
│   ├── reviewers/
│   │   └── panel_reviewer.py ← multi-model review + revision
│   ├── scrapers/
│   │   └── scopus_client.py
│   ├── utils/
│   │   └── llm_client.py     ← unified LLM factory
│   ├── api/app.py            ← FastAPI (includes /config endpoint)
│   └── cli.py                ← Click CLI
├── data/
│   ├── rules/                ← FCT eval criteria (JSON)
│   └── schemas/              ← validation schemas
├── tests/
├── infra/terraform/          ← GCP Cloud Run IaC
├── scripts/deploy.sh
├── Dockerfile
├── docker-compose.yml
└── CLAUDE.md                 ← instructions for Claude Code
```

---

## IC&DT vs PEX at a glance

Set `project.typology` in `config.yaml`:

| | **SR&TD (IC&DT)** | **PEX (Exploratory)** |
|---|---|---|
| Duration | 36 months (+12 extension) | 18 months (+6 extension) |
| Max funding | €250,000 | €60,000 |
| Initial advance | 30% | 75% |
| Intermediate payments | Yes | No |
| Participating institutions | Allowed | Not allowed |
| Call budget | €80 M (~320 projects) | €24 M (~400 projects) |

---

## GCP Deployment

```bash
# First-time infrastructure setup
./scripts/deploy.sh --init

# Build & deploy to Cloud Run
./scripts/deploy.sh

# Or via Terraform
cd infra/terraform && terraform init && terraform apply
```

---

## License

MIT
