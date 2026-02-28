"""
Two-tier configuration:
  .env         → secrets (API keys)  — never committed
  config.yaml  → user preferences    — committed, easy to edit

Usage anywhere in the codebase:
    from src.config.settings import cfg, secrets
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


# =============================================================================
# 1. Secrets (.env)
# =============================================================================

class Secrets(BaseSettings):
    """API keys and credentials — loaded exclusively from .env"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore",
    )

    # LLM providers
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    huggingface_api_key: str = ""

    # Research APIs
    scopus_api_key: str = ""
    scopus_inst_token: str = ""

    # Social
    x_api_key: str = ""
    x_api_secret: str = ""

    # Database (optional)
    database_url: str = "sqlite:///./data/proposals.db"
    redis_url: Optional[str] = None

    def has_key(self, provider: str) -> bool:
        """Check whether a usable key exists for a given provider."""
        mapping = {
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
            "google": self.google_api_key,
            "huggingface": self.huggingface_api_key,
        }
        return bool(mapping.get(provider, ""))


# =============================================================================
# 2. User Config (config.yaml)
# =============================================================================

class LLMProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    HUGGINGFACE = "huggingface"


_CONFIG_PATH = Path(os.environ.get("FCT_CONFIG", "config.yaml"))


def _load_yaml(path: Path) -> dict[str, Any]:
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


class LLMRole:
    """Settings for a single LLM role (generator, consensus, revision)."""

    def __init__(self, data: dict | None = None):
        data = data or {}
        self.provider: LLMProvider = LLMProvider(data.get("provider", "anthropic"))
        self.model: str = data.get("model", "claude-opus-4-6")
        self.temperature: float = data.get("temperature", 0.3)


class ReviewerDef:
    """One entry from the review_panel list in config.yaml."""

    def __init__(self, data: dict):
        self.id: str = data.get("id", "unnamed")
        self.enabled: bool = data.get("enabled", True)
        self.provider: LLMProvider = LLMProvider(data.get("provider", "anthropic"))
        self.model: str = data.get("model", "claude-opus-4-6")
        self.perspective: str = data.get("perspective", "general")
        self.focus_criteria: list[str] = data.get("focus_criteria", [])
        self.persona: str = data.get("persona", "").strip()


class UserConfig:
    """
    All user-facing preferences, loaded from config.yaml.
    Accessible via  cfg.<section>.<key> .
    """

    def __init__(self, path: Path | None = None):
        raw = _load_yaml(path or _CONFIG_PATH)

        # --- Project defaults ---
        proj = raw.get("project", {})
        self.typology: str = proj.get("typology", "SR&TD")
        self.principal_contractor: str = proj.get("principal_contractor", "Universidade de Aveiro")
        self.default_research_units: list[str] = proj.get("default_research_units", [])
        self.language: str = proj.get("language", "en")
        self.target_start_date: str = proj.get("target_start_date", "2027-01-01")

        # --- LLM roles ---
        llm = raw.get("llm", {})
        self.generator = LLMRole(llm.get("generator"))
        self.consensus = LLMRole(llm.get("consensus"))
        self.revision = LLMRole(llm.get("revision"))

        # --- Review panel ---
        panel_raw = raw.get("review_panel", [])
        self.review_panel: list[ReviewerDef] = [ReviewerDef(r) for r in panel_raw]

        # --- Pipeline ---
        pipe = raw.get("pipeline", {})
        self.iterations: int = pipe.get("iterations", 2)
        self.stop_on_accept: bool = pipe.get("stop_on_accept", True)
        self.max_concurrent_reviews: int = pipe.get("max_concurrent_reviews", 4)
        self.save_intermediates: bool = pipe.get("save_intermediates", True)

        # --- Scopus ---
        sc = raw.get("scopus", {})
        self.scopus_enabled: bool = sc.get("enabled", True)
        self.scopus_max_results: int = sc.get("max_results", 40)
        self.scopus_year_from: int = sc.get("year_from", 2019)
        self.scopus_enrich_abstracts: bool = sc.get("enrich_abstracts", True)
        self.scopus_top_abstracts: int = sc.get("top_abstracts", 15)

        # --- Output ---
        out = raw.get("output", {})
        self.output_dir: str = out.get("dir", "output")
        fmts = out.get("formats", {})
        self.out_json: bool = fmts.get("json", True)
        self.out_markdown: bool = fmts.get("markdown", True)
        self.out_docx: bool = fmts.get("docx", False)
        self.out_char_report: bool = fmts.get("char_report", True)
        self.include_review_narrative: bool = out.get("include_review_narrative", True)

        # --- Logging ---
        log = raw.get("logging", {})
        self.log_level: str = log.get("level", "INFO")
        self.rich_console: bool = log.get("rich_console", True)

        # --- GCP ---
        gcp = raw.get("gcp", {})
        self.gcp_project_id: str = gcp.get("project_id", "fct-proposal-engine")
        self.gcp_region: str = gcp.get("region", "europe-west1")
        self.gcs_bucket: str = gcp.get("bucket", "fct-proposals-store")
        self.cloud_run_service: str = gcp.get("cloud_run_service", "fct-engine-api")

        # --- Derived paths ---
        self.project_root: Path = Path(__file__).resolve().parent.parent.parent
        self.data_dir: Path = self.project_root / "data"
        self.prompts_dir: Path = self.data_dir / "prompts"
        self.rules_dir: Path = self.data_dir / "rules"

    @property
    def enabled_reviewers(self) -> list[ReviewerDef]:
        return [r for r in self.review_panel if r.enabled]

    def reload(self, path: Path | None = None):
        """Hot-reload config from disk."""
        new = UserConfig(path or _CONFIG_PATH)
        self.__dict__.update(new.__dict__)


# =============================================================================
# Singletons — import these everywhere
# =============================================================================

secrets = Secrets()
cfg = UserConfig()
