# Audit Report: FCT Proposal Engine

🏁 **All audit findings resolved. Codebase approved.**

## Re-Review (2026-02-28)
Verified the latest codebase state:
- [✅ RESOLVED] **Unused Imports:** All identified unused imports have been removed.
- [✅ RESOLVED] **API Type Hints:** Return type annotations added to all FastAPI endpoints.
- [✅ RESOLVED] **Core Docstrings:** Public methods in `Pipeline`, `ProposalGenerator`, and `AIReviewer` have descriptive docstrings.
- [✅ RESOLVED] **Internal Type Hints:** All internal helper methods in `ProposalGenerator` and `panel_reviewer.py` are now fully typed.
- [✅ RESOLVED] **Retry Logic:** `scopus_client.py` uses refined retries for transient errors and logs 4xx errors correctly.
- [✅ RESOLVED] **Hard-coded Prompts:** All prompts (including section-specific extras) moved to `data/prompts/` and loaded via `load_prompt_template()`.

---

## Executive Summary
- Total files audited: 34
- 🔴 Blockers: 0
- 🟡 Issues: 4
- 🟢 Suggestions: 6

## File-by-File Findings

### `src/generators/proposal_generator.py` (🔴 0 / 🟡 1 / 🟢 2)
- [🟡 Issue] [Lines 141, 161, 175, 187] **Hard-coded Prompts:** Contains heavily hard-coded prompt templates for `_gen_tasks`, `_gen_deliverables`, `_gen_milestones`, and `_prompt`. These should be extracted to `data/prompts/` to comply with the two-file architecture mandate.
- [🟢 Suggestion] [Lines 123-228] **Missing Type Hints:** Internal helper methods (`_gen`, `_trim`, `_gen_tasks`, `_prompt`, `_lit_context`, `_fmt_refs`, `_est_budget`, `_fallback_tasks`) lack parameter and return type annotations.
- [🟢 Suggestion] [Line 30] **Docstrings:** The core `generate` method lacks a descriptive docstring.

### `src/reviewers/panel_reviewer.py` (🔴 0 / 🟡 1 / 🟢 2)
- [🟡 Issue] [Lines 62, 148, 192] **Hard-coded Prompts:** Contains hard-coded prompts for the reviewer (`_build_prompt`), the consensus aggregation (`_consensus`), and the revision engine (`revise`). These violate the architecture mandate and should be loaded via `prompt_loader.py`.
- [🟢 Suggestion] [Lines 207, 219] **Missing Type Hints:** `_weak_sections` and `_feedback_for` are missing parameter and return type hints.
- [🟢 Suggestion] [Line 42] **Docstrings:** The `AIReviewer.review` method is missing a comprehensive docstring.

### `src/scrapers/scopus_client.py` (🔴 0 / 🟡 1 / 🟢 0)
- [🟡 Issue] [Line 46] **Indiscriminate Retries:** The `@retry` decorator on the `search` method catches all exceptions. It should be restricted to network timeouts and 5xx errors (e.g., using `retry_if_exception_type`) to avoid infinite retries on 400/401/403 errors.

### `src/api/app.py` (🔴 0 / 🟡 1 / 🟢 0)
- [🟡 Issue] [Lines 44-124] **Missing Type Hints:** FastAPI endpoint functions (`health`, `get_config`, `get_rules`, `get_job`, `validate_proposal`, `reload_config`) are missing return type annotations.

### `src/generators/models.py` (🔴 0 / 🟡 0 / 🟢 1)
- [🟢 Suggestion] [Lines 11-12] **Unused Imports:** `from datetime import date` and `from typing import Optional` are imported but never used.

### `src/config/fct_constants.py` (🔴 0 / 🟡 0 / 🟢 1)
- [🟢 Suggestion] [Line 9] **Unused Imports:** `from typing import Optional` is unused.

---

## Cross-Cutting Audits

### Hard-coded Preferences
Violations of the strict "two-file config/prompt" architecture found:
- `src/generators/proposal_generator.py`: All section-specific prompt templates and task scaffolding prompts are hard-coded strings.
- `src/reviewers/panel_reviewer.py`: The evaluation context prompt, consensus narrative prompt, and revision prompt are hard-coded in the Python source.

### Missing Retry Logic
- `src/scrapers/scopus_client.py`: The `search` method uses a generic `@retry` that will blindly retry deterministic client errors (4xx).

### Async Correctness
- **✅ Pass:** All external network calls (LLMs and Scopus) properly utilize async clients (`AsyncAnthropic`, `AsyncOpenAI`, `google.genai.Client.aio`, `httpx.AsyncClient`). No synchronous blocking calls found in async contexts.

### Type Hints & Docstrings
- The public API models and standard configurations are well-typed.
- Internal orchestration logic in `proposal_generator.py` and `panel_reviewer.py` is missing significant typing for helper methods. 
- Several critical public methods lack docstrings describing their behavior and arguments.

### Unused Imports
- `src/config/fct_constants.py`: `Optional`
- `src/generators/models.py`: `date`, `Optional`

### Gitignore & Security
- **✅ Pass:** `.gitignore` is comprehensive and successfully excludes `.env`, `output/`, and `__pycache__`.
- **✅ Pass:** `scripts/security_check.sh` was audited and provides highly robust, comprehensive pre-commit checks for secrets, architecture bypasses, PII, and unsafe evaluations.

### Schema-Draft Consistency
- **✅ Pass:** `data/schemas/draft_idea.json` has been updated and perfectly mirrors the properties found in `drafts/pdspp_pilot_pex.yaml` and the Pydantic `DraftIdea` model.

### Security Script Coverage
- **✅ Pass:** `scripts/security_check.sh` accurately covers all the patterns it claims to check (API keys, hardcoded credentials, f-string leaks, direct LLM initializations, unsafe YAML loading, path traversals, etc.).

### Documentation Consistency
- **✅ Pass:** `CLAUDE.md` and `GEMINI.md` are aligned with each other and the actual state of the codebase. The two-file configuration rule and LLM Factory architectural mandates are well documented and enforced.

---

## ✅ Architecture Strengths

1. **Robust Configuration Separation:** The project cleanly divides secrets (`.env`, via `BaseSettings`) and user preferences (`config.yaml`), preventing accidental credential leaks while maintaining user configurability.
2. **Unified LLM Factory:** `BaseLLMClient` and `get_llm_client()` abstract away provider-specific SDK quirks. This allows seamless swapping between Anthropic, OpenAI, Google, and HuggingFace without modifying business logic.
3. **Immutable Regulatory Constants:** Hard-coding FCT constraints, character limits, and budget caps into `fct_constants.py` using frozen dataclasses is an excellent domain-driven design that guarantees structural compliance.
4. **Security Tooling:** The presence of `security_check.sh` as a mandatory pre-commit gate explicitly addressing AI coding risks (like logging secrets or bypassing factories) is a best-in-class practice.

---

## Priority Fix Roadmap

**Work Package 1: Extract Prompts (Architecture Conformance)**
- Move the hard-coded prompts from `src/generators/proposal_generator.py` into new YAML files in `data/prompts/`.
- Move the evaluation, consensus, and revision prompts from `src/reviewers/panel_reviewer.py` to `data/prompts/`.
- Update both files to utilize `get_prompt()` from `src.utils.prompt_loader`.

**Work Package 2: Refine Network Retries**
- Modify `@retry` in `ScopusScraper.search()` to include `retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError))` to prevent infinite retrying of 4xx errors, matching the logic in `get_abstract()`.

**Work Package 3: Code Hygiene & Type Checking**
- Add explicit type hints to all internal helper methods in `ProposalGenerator` and `RevisionEngine`.
- Add return type annotations to all FastAPI endpoint functions in `src/api/app.py`.
- Remove unused imports in `models.py` and `fct_constants.py`.
- Add docstrings to `ProposalGenerator.generate` and `AIReviewer.review`.
