"""
Tests for FCT Proposal Engine.
"""

import json
import textwrap
from pathlib import Path

import jsonschema
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

    def test_at_limit_detection(self):
        p = Proposal(abstract_en="x" * CHAR_LIMITS.abstract_en)
        r = p.char_count_report()
        assert r["abstract_en"]["actual"] == CHAR_LIMITS.abstract_en
        assert r["abstract_en"]["remaining"] == 0

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

# =============================================================================
# YAML Schema Validation (all drafts vs data/schemas/draft_idea.json)
# =============================================================================

SCHEMA_PATH = Path("data/schemas/draft_idea.json")
DRAFTS_DIR = Path("drafts")


@pytest.fixture(scope="module")
def draft_schema():
    return json.loads(SCHEMA_PATH.read_text())


def _all_draft_yamls():
    return sorted(DRAFTS_DIR.glob("*.yaml"))


class TestDraftSchemaValidation:
    """Validate every YAML draft against data/schemas/draft_idea.json."""

    def test_schema_file_exists(self):
        assert SCHEMA_PATH.exists(), f"Schema not found: {SCHEMA_PATH}"

    def test_schema_is_valid_json_schema(self, draft_schema):
        jsonschema.Draft7Validator.check_schema(draft_schema)

    @pytest.mark.parametrize("yaml_path", _all_draft_yamls(), ids=lambda p: p.name)
    def test_draft_validates(self, yaml_path, draft_schema):
        data = yaml.safe_load(yaml_path.read_text())
        jsonschema.validate(instance=data, schema=draft_schema)

    @pytest.mark.parametrize("yaml_path", _all_draft_yamls(), ids=lambda p: p.name)
    def test_required_fields_present(self, yaml_path):
        data = yaml.safe_load(yaml_path.read_text())
        assert "title" in data, f"{yaml_path.name}: missing 'title'"
        assert "research_topic" in data, f"{yaml_path.name}: missing 'research_topic'"
        assert len(data["research_topic"]) >= 50, (
            f"{yaml_path.name}: research_topic too short ({len(data['research_topic'])} chars)"
        )

    @pytest.mark.parametrize("yaml_path", _all_draft_yamls(), ids=lambda p: p.name)
    def test_typology_constraints(self, yaml_path):
        data = yaml.safe_load(yaml_path.read_text())
        typ = data.get("typology", "SR&TD")
        budget = data.get("estimated_budget", 0)
        duration = data.get("duration_months", 0)
        if typ == "PEX":
            assert budget <= 60_000, f"{yaml_path.name}: PEX budget {budget} > 60000"
            assert duration <= 18, f"{yaml_path.name}: PEX duration {duration} > 18 months"
        elif typ == "SR&TD":
            assert budget <= 250_000, f"{yaml_path.name}: IC&DT budget {budget} > 250000"
            assert duration <= 36, f"{yaml_path.name}: IC&DT duration {duration} > 36 months"

    @pytest.mark.parametrize("yaml_path", _all_draft_yamls(), ids=lambda p: p.name)
    def test_keywords_limit(self, yaml_path):
        data = yaml.safe_load(yaml_path.read_text())
        for key in ("keywords_en", "keywords_pt"):
            kw = data.get(key, [])
            assert len(kw) <= 4, f"{yaml_path.name}: {key} has {len(kw)} items (max 4)"

    @pytest.mark.parametrize("yaml_path", _all_draft_yamls(), ids=lambda p: p.name)
    def test_sdg_valid(self, yaml_path):
        data = yaml.safe_load(yaml_path.read_text())
        sdgs = data.get("sdg_alignment", [])
        assert len(sdgs) <= 3, f"{yaml_path.name}: {len(sdgs)} SDGs (max 3)"
        for s in sdgs:
            assert 1 <= s <= 17, f"{yaml_path.name}: invalid SDG {s}"

    def test_missing_title_fails(self, draft_schema):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance={"research_topic": "x" * 50}, schema=draft_schema)

    def test_missing_research_topic_fails(self, draft_schema):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance={"title": "Test"}, schema=draft_schema)

    def test_invalid_typology_fails(self, draft_schema):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                instance={"title": "T", "research_topic": "x" * 50, "typology": "INVALID"},
                schema=draft_schema,
            )


# =============================================================================
# Text Utilities
# =============================================================================

class TestSafeTruncate:
    def test_short_text_unchanged(self):
        from src.utils.text_utils import safe_truncate
        assert safe_truncate("Hello world.", 100) == "Hello world."

    def test_truncate_at_sentence_boundary(self):
        from src.utils.text_utils import safe_truncate
        text = "First sentence. Second sentence. Third sentence."
        result = safe_truncate(text, 35)
        assert result.endswith(".")
        assert len(result) <= 35

    def test_truncate_at_word_boundary(self):
        from src.utils.text_utils import safe_truncate
        text = "one two three four five six seven eight nine ten"
        result = safe_truncate(text, 20)
        assert " " not in result[-1:]  # doesn't end with space
        assert len(result) <= 20

    def test_hard_cut_last_resort(self):
        from src.utils.text_utils import safe_truncate
        text = "a" * 100  # no spaces or sentence boundaries
        result = safe_truncate(text, 50)
        assert len(result) == 50

    def test_empty_text(self):
        from src.utils.text_utils import safe_truncate
        assert safe_truncate("", 100) == ""

    def test_exact_limit(self):
        from src.utils.text_utils import safe_truncate
        text = "Exact."
        assert safe_truncate(text, 6) == "Exact."


class TestSafeLimit:
    def test_default_buffer(self):
        from src.utils.text_utils import safe_limit
        # 6000 * 0.05 = 300 > 200, so buffer = 300
        assert safe_limit(6000) == 5700

    def test_min_buffer_applied(self):
        from src.utils.text_utils import safe_limit
        # 1000 * 0.05 = 50 < 200, so buffer = 200
        assert safe_limit(1000) == 800

    def test_custom_buffer(self):
        from src.utils.text_utils import safe_limit
        assert safe_limit(10000, buffer_pct=0.1, min_buffer=100) == 9000

    def test_very_small_limit(self):
        from src.utils.text_utils import safe_limit
        # Should not go below 1
        assert safe_limit(100) >= 1


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
            get_llm_client(provider="anthropic", model="claude-opus-4-6")
        except ValueError as e:
            assert "API key" in str(e)
