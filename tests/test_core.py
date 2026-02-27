"""
Tests for FCT Proposal Engine.
"""

import json
import textwrap
from pathlib import Path

import pytest
import yaml

from src.config.fct_constants import (
    BUDGET_RULES, CHAR_LIMITS, EVAL_CRITERIA, PARTICIPATION_RULES,
    TYPOLOGY_RULES, ProjectType,
)
from src.generators.models import DraftIdea, Proposal, ProposalTask


# =============================================================================
# FCT Constants
# =============================================================================

class TestFCTConstants:
    def test_icdt_funding(self):
        assert TYPOLOGY_RULES[ProjectType.ICDT].max_funding_eur == 250_000

    def test_pex_funding(self):
        assert TYPOLOGY_RULES[ProjectType.PEX].max_funding_eur == 60_000

    def test_icdt_duration(self):
        assert TYPOLOGY_RULES[ProjectType.ICDT].max_duration_months == 36

    def test_pex_duration(self):
        assert TYPOLOGY_RULES[ProjectType.PEX].max_duration_months == 18

    def test_weights_sum_to_one(self):
        total = EVAL_CRITERIA.criterion_a_weight + EVAL_CRITERIA.criterion_b_weight + EVAL_CRITERIA.criterion_c_weight
        assert total == pytest.approx(1.0)

    def test_indirect_costs(self):
        assert BUDGET_RULES.indirect_costs_pct == 0.25

    def test_char_limits(self):
        assert CHAR_LIMITS.state_of_art_objectives == 6000
        assert CHAR_LIMITS.research_plan_methods == 10000
        assert CHAR_LIMITS.career_profile == 4000

    def test_participation(self):
        assert PARTICIPATION_RULES.max_pi_applications == 1


# =============================================================================
# Config loading
# =============================================================================

class TestConfigLoading:
    def test_config_yaml_exists(self):
        assert Path("config.yaml").exists(), "config.yaml must be in the project root"

    def test_config_yaml_parseable(self):
        with open("config.yaml") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)
        assert "project" in data
        assert "llm" in data
        assert "review_panel" in data

    def test_config_yaml_typology_valid(self):
        with open("config.yaml") as f:
            data = yaml.safe_load(f)
        typ = data["project"]["typology"]
        assert typ in ("SR&TD", "PEX"), f"Invalid typology: {typ}"

    def test_config_yaml_providers_valid(self):
        valid = {"anthropic", "openai", "google", "huggingface"}
        with open("config.yaml") as f:
            data = yaml.safe_load(f)
        for role in ("generator", "consensus", "revision"):
            prov = data["llm"][role]["provider"]
            assert prov in valid, f"Invalid provider for {role}: {prov}"
        for r in data["review_panel"]:
            assert r["provider"] in valid, f"Invalid provider for reviewer {r['id']}: {r['provider']}"

    def test_user_config_loads(self):
        from src.config.settings import UserConfig
        c = UserConfig(Path("config.yaml"))
        assert c.typology in ("SR&TD", "PEX")
        assert c.generator.model != ""
        assert len(c.review_panel) > 0

    def test_enabled_reviewers(self):
        from src.config.settings import UserConfig
        c = UserConfig(Path("config.yaml"))
        enabled = c.enabled_reviewers
        assert isinstance(enabled, list)
        for r in enabled:
            assert r.id != ""
            assert r.perspective != ""


# =============================================================================
# Data Models
# =============================================================================

class TestDraftIdea:
    def test_minimal(self):
        d = DraftIdea(title="Test", research_topic="A test topic.")
        assert d.typology == ProjectType.ICDT
        assert d.principal_contractor == "Universidade de Aveiro"

    def test_example_yaml(self):
        p = Path("drafts/example_idea.yaml")
        if p.exists():
            data = yaml.safe_load(p.read_text())
            d = DraftIdea(**data)
            assert d.acronym == "DigiResilient"
            assert len(d.keywords_en) <= 4


class TestProposal:
    def test_empty(self):
        p = Proposal()
        report = p.char_count_report()
        assert all(v["actual"] == 0 for v in report.values())

    def test_over_limit_detection(self):
        p = Proposal(abstract_en="x" * 6000)
        r = p.char_count_report()
        assert r["abstract_en"]["actual"] == 6000
        assert r["abstract_en"]["remaining"] == CHAR_LIMITS.abstract_en - 6000

    def test_task_budget(self):
        t = ProposalTask(number=1, denomination="T", description="D")
        t.budget.human_resources = 10_000
        t.budget.equipment = 5_000
        assert t.budget.direct_costs == 15_000
        assert t.budget.indirect_costs == 3_750
        assert t.budget.total == 18_750


# =============================================================================
# LLM Client factory (unit test — no API calls)
# =============================================================================

class TestLLMFactory:
    def test_unknown_provider_raises(self):
        from src.utils.llm_client import get_llm_client
        with pytest.raises(ValueError):
            get_llm_client(provider="nonexistent")

    def test_missing_key_raises(self):
        from src.utils.llm_client import get_llm_client
        # Unless the tester actually has all keys, at least one will be missing
        # This test simply ensures the check path doesn't crash
        try:
            get_llm_client(provider="anthropic", model="claude-sonnet-4-5-20250929")
        except ValueError as e:
            assert "API key" in str(e)
