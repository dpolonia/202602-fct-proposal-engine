# CLAUDE.md — Instructions for Claude Code

## What this project does

**FCT Proposal Engine** generates and peer-reviews research proposals for the Portuguese FCT PTDC 2025 call. It transforms a draft idea (YAML) into a submission-ready proposal, then runs it through a configurable panel of AI reviewers that simulate international peer review, and iteratively revises until quality thresholds are met.

## Configuration Architecture (IMPORTANT)

The project uses a **two-file** config model:

| File | What it holds | Loaded by |
|------|---------------|-----------|
| **`config.yaml`** | All user preferences: LLM providers/models, project typology (IC&DT or PEX), review panel composition, Scopus settings, pipeline behaviour, output formats | `src/config/settings.py → UserConfig` |
| **`.env`** | API keys/secrets only | `src/config/settings.py → Secrets` |

**Never hard-code providers, models, or user preferences in source code.** Always read from `cfg` or `secrets`:

```python
from src.config.settings import cfg, secrets

# LLM settings
cfg.generator.provider   # "anthropic"
cfg.generator.model      # "claude-sonnet-4-5-20250929"
cfg.consensus.provider   # can differ from generator
cfg.revision.temperature # 0.3

# Project defaults
cfg.typology             # "SR&TD" or "PEX"
cfg.principal_contractor # "Universidade de Aveiro"
cfg.default_research_units  # ["GOVCOPP"]

# Panel (list of ReviewerDef)
cfg.enabled_reviewers    # only those with enabled: true

# Pipeline
cfg.iterations           # 2
cfg.stop_on_accept       # true

# Scopus
cfg.scopus_enabled       # true/false
cfg.scopus_max_results   # 40

# Output
cfg.output_dir           # "output"
cfg.out_json             # true
cfg.out_markdown         # true

# Secrets
secrets.anthropic_api_key
secrets.has_key("openai")  # bool
```

## Key Commands

```bash
pip install -e ".[dev]"                    # install
make test                                  # pytest
make lint                                  # ruff + mypy
make serve                                 # FastAPI dev server on :8080
fct-engine config --show                   # print resolved settings
fct-engine pipeline -i drafts/example_idea.yaml  # full run
fct-engine -c alt.yaml pipeline -i draft.yaml    # custom config
```

## Source Map

```
src/config/settings.py          → UserConfig (config.yaml) + Secrets (.env)
src/config/fct_constants.py     → char limits, eval criteria, budget rules, typology rules
src/utils/llm_client.py         → factory: get_llm_client(provider, model) / get_llm_for_role(role)
src/scrapers/scopus_client.py   → reads cfg.scopus_* + secrets.scopus_api_key
src/generators/models.py        → DraftIdea → Proposal → ReviewReport → ConsensusReport
src/generators/proposal_generator.py → uses cfg.generator LLM + cfg.scopus settings
src/generators/pipeline.py      → orchestrator; reads cfg.iterations, cfg.stop_on_accept, cfg.out_*
src/reviewers/panel_reviewer.py → builds panel from cfg.enabled_reviewers; consensus via cfg.consensus LLM
src/api/app.py                  → FastAPI; /config returns resolved settings; /config/reload hot-reloads
src/cli.py                      → Click CLI; -c flag overrides config.yaml path
config.yaml                     → THE user config file (edit this, not source code)
```

## FCT Rules Always Enforced

- Character limits: STRICT — see `fct_constants.py`
- Evaluation: A (40%), B (30%), C (30%) — weights in `EVAL_CRITERIA`
- Typology rules: IC&DT max €250k/36mo; PEX max €60k/18mo — in `TYPOLOGY_RULES`
- Lump sum: payments tied to deliverables; no timeline gaps
- Indirect costs: 25% of eligible direct (automatic)
- All proposal text: English (except `abstract_pt`)
- Budget justification: per task (max 2500 chars)

## Adding a New Reviewer

Edit `config.yaml`, add an entry under `review_panel:`:

```yaml
  - id: "my_custom_reviewer"
    enabled: true
    provider: "openai"
    model: "gpt-4o-mini"
    perspective: "sustainability"
    focus_criteria: ["A2", "C"]
    persona: "Expert in sustainable development and ESG impact assessment."
```

No code changes needed — the panel auto-discovers from config.

## Adding a New LLM Provider

1. Add a new client class in `src/utils/llm_client.py` extending `BaseLLMClient`
2. Register it in the `_CLIENTS` dict
3. Add the provider name to `LLMProvider` enum in `settings.py`
4. Users can then set `provider: "new_provider"` in config.yaml

## Testing

```bash
pytest tests/ -v                     # unit tests (no API keys)
pytest tests/ -v -k "not skipif"     # integration (needs keys)
```

## Code Style

- Python 3.11+, async/await throughout
- Pydantic v2 for all data models
- Type hints everywhere
- Ruff (line-length=100)
- config.yaml for preferences, .env for secrets — never the reverse
