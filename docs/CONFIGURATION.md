# Configuration Reference

This document explains every setting available in `config.yaml`.

---

## 1. `project` — Proposal Defaults

These values are applied when the draft idea YAML does not specify its own.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `typology` | `"SR&TD"` or `"PEX"` | `"SR&TD"` | **IC&DT** (max €250k, 36 mo) or **PEX** (max €60k, 18 mo). Can be overridden per draft. |
| `principal_contractor` | string | `"Universidade de Aveiro"` | Lead institution. |
| `default_research_units` | list of strings | `["GOVCOPP"]` | Research units (max 3 per institution). |
| `language` | string | `"en"` | Proposal language (FCT requires English). |
| `target_start_date` | string (YYYY-MM-DD) | `"2027-01-01"` | Expected project start. |

### Typology comparison

| | SR&TD (IC&DT) | PEX |
|---|---|---|
| Max duration | 36 months (+12 ext.) | 18 months (+6 ext.) |
| Max funding | €250,000 | €60,000 |
| Initial advance | 30% | 75% |
| Intermediate payments | Yes | No |
| Participating institutions with budget | Yes | No |
| PI narrative: "Why timely" section | No | Yes (3000 chars) |
| Team hiring (PEX constraint) | — | Max 12 months contract |

---

## 2. `llm` — AI Model Selection

Three independent roles, each configurable with its own provider and model:

| Role | What it does | When it runs |
|------|-------------|-------------|
| `generator` | Writes all proposal sections | `fct-engine generate` / pipeline step 1 |
| `consensus` | Synthesises panel reviews into a single narrative | After all reviewers finish |
| `revision` | Applies review feedback to improve weak sections | Pipeline revision step |

Each role accepts:

```yaml
llm:
  generator:
    provider: "anthropic"                    # anthropic | openai | google | huggingface
    model: "claude-opus-4-6"                 # any model string valid for that provider
    temperature: 0.3                         # 0.0–1.0
```

**You only need API keys (in `.env`) for the providers you actually use.** If you set all three roles to `anthropic`, only `ANTHROPIC_API_KEY` is required.

---

## 3. `review_panel` — AI Peer Reviewers

A list of reviewer definitions. The engine creates one AI reviewer per entry and runs them in parallel. You can add, remove, reorder, or disable entries freely.

```yaml
review_panel:
  - id: "my_reviewer"         # unique identifier (used in logs & output)
    enabled: true              # set false to skip without deleting
    provider: "openai"         # LLM provider
    model: "gpt-5.2-2025-12-11"  # model string
    perspective: "innovation"  # label for the review focus
    focus_criteria: ["A2"]     # which FCT criteria this reviewer emphasises
    persona: >                 # system prompt persona (optional)
      Dr. Chen, innovation scholar, evaluates novelty and ambition.
```

**`focus_criteria`** maps to FCT evaluation sub-criteria:

| Code | Criterion | Weight |
|------|-----------|--------|
| `A1` | Scientific merit | 20% (50% of A's 40%) |
| `A2` | Innovative nature | 20% (50% of A's 40%) |
| `B1` | PI merit | 18% (60% of B's 30%) |
| `B2` | Team merit | 12% (40% of B's 30%) |
| `C` | Feasibility & budget | 30% |

**Tip:** For a quick single-model review, disable all but one reviewer.

---

## 4. `pipeline` — Execution Behaviour

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `iterations` | int | `3` | Number of generate → review → revise cycles. |
| `stop_on_accept` | bool | `true` | Stop early if the panel decision is `"accept"`. |
| `max_concurrent_reviews` | int | `4` | Max parallel reviewer calls (limited by rate limits). |
| `save_intermediates` | bool | `true` | Keep `v0_proposal.json`, `v0_review.json`, etc. |

---

## 5. `scopus` — Literature Search

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Set `false` to skip Scopus entirely (useful offline or without a key). |
| `max_results` | int | `100` | Total articles to retrieve across all queries. |
| `year_from` | int | `2019` | Oldest publication year to include. |
| `enrich_abstracts` | bool | `true` | Fetch full abstracts for top-cited articles. |
| `top_abstracts` | int | `30` | How many top articles to enrich with abstracts. |

Requires `SCOPUS_API_KEY` in `.env`. If the key is missing and `enabled: true`, the scraper silently skips.

---

## 6. `output` — What Gets Written

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `dir` | string | `"output"` | Base output directory. A timestamped subfolder is created per run. |
| `formats.json` | bool | `true` | Machine-readable proposal (for API / re-import). |
| `formats.markdown` | bool | `true` | Human-readable summary with review narrative. |
| `formats.docx` | bool | `false` | Word document (requires `python-docx`). |
| `formats.char_report` | bool | `true` | JSON showing char counts vs. FCT limits per section. |
| `include_review_narrative` | bool | `true` | Append panel narrative to markdown output. |

---

## 7. `logging`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `level` | string | `"INFO"` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `rich_console` | bool | `true` | Coloured terminal output via Rich. |

---

## 8. `gcp` — Cloud Deployment

Only needed if you deploy to Google Cloud Run.

| Key | Default | Description |
|-----|---------|-------------|
| `project_id` | `"fct-proposal-engine"` | GCP project. |
| `region` | `"europe-west1"` | Deployment region. |
| `bucket` | `"fct-proposals-store"` | GCS bucket for outputs. |
| `cloud_run_service` | `"fct-engine-api"` | Cloud Run service name. |

---

## Environment Variables (`.env`)

`.env` holds secrets only. Example:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
HUGGINGFACE_API_KEY=hf_...
SCOPUS_API_KEY=...
SCOPUS_INST_TOKEN=...
X_API_KEY=...
X_API_SECRET=...
```

You can also override the config path via the environment:

```bash
FCT_CONFIG=my_custom_config.yaml fct-engine pipeline -i draft.yaml
```

Or with the CLI flag:

```bash
fct-engine -c my_custom_config.yaml pipeline -i draft.yaml
```
