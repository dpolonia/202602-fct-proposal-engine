"""
Integration test: loads a draft, runs the full pipeline with mocked LLMs,
and verifies the output proposal is structurally sound.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from src.config.fct_constants import CHAR_LIMITS, TYPOLOGY_RULES, ProjectType
from src.generators.models import DraftIdea
from src.generators.pipeline import Pipeline
from src.generators.proposal_generator import ProposalGenerator
from src.reviewers.panel_reviewer import ReviewPanel, RevisionEngine
from src.utils.llm_client import LLMResponse, LLMProvider


# =============================================================================
# Fixtures
# =============================================================================

DRAFTS_DIR = Path("drafts")


def _mock_llm_response(text: str, model: str = "mock-model") -> LLMResponse:
    return LLMResponse(
        text=text, model=model, provider=LLMProvider.ANTHROPIC,
        input_tokens=100, output_tokens=len(text), finish_reason="stop",
    )


def _build_section_text(section: str, limit: int) -> str:
    """Generate plausible filler text within the char limit."""
    base = f"This is the generated {section} section for the proposal. "
    return (base * (limit // len(base) + 1))[:limit - 100]


def _build_tasks_json() -> str:
    return json.dumps([
        {
            "number": 1, "denomination": "Literature Review & Framework",
            "description": "Systematic literature review and conceptual framework development.",
            "expected_results": "Framework document", "person_months": 4.0,
            "start_month": 1, "duration_months": 8,
            "cost_justification": "PI time (2PM) + research fellow (2PM).",
        },
        {
            "number": 2, "denomination": "Data Collection & Development",
            "description": "Primary data collection and prototype development.",
            "expected_results": "Dataset and prototype", "person_months": 8.0,
            "start_month": 5, "duration_months": 10,
            "cost_justification": "Research fellow (6PM) + cloud infra.",
        },
        {
            "number": 3, "denomination": "Validation & Dissemination",
            "description": "Validation with stakeholders and dissemination of results.",
            "expected_results": "Validation report and publications", "person_months": 4.0,
            "start_month": 12, "duration_months": 7,
            "cost_justification": "Travel + publication fees.",
        },
    ])


def _build_deliverables_json() -> str:
    return json.dumps([
        {"code": "D1.1", "title": "SLR Report", "type": "Report",
         "description": "Systematic literature review.", "related_tasks": [1], "due_month": 6},
        {"code": "D2.1", "title": "Prototype v1", "type": "Demonstrator",
         "description": "Working prototype.", "related_tasks": [2], "due_month": 14},
        {"code": "D3.1", "title": "Final Report", "type": "Report",
         "description": "Final project report.", "related_tasks": [3], "due_month": 18},
    ])


def _build_milestones_json() -> str:
    return json.dumps([
        {"code": "M1", "denomination": "Framework Complete", "description": "Approved.",
         "related_tasks": [1], "due_month": 6},
        {"code": "M2", "denomination": "Prototype Ready", "description": "Deployed.",
         "related_tasks": [2], "due_month": 14},
        {"code": "M3", "denomination": "Project Close", "description": "All deliverables done.",
         "related_tasks": [3], "due_month": 18},
    ])


def _build_review_json(score: float = 8.0, decision: str = "accept") -> str:
    return json.dumps({
        "overall_score": score,
        "criterion_scores": [
            {"criterion": "A", "sub_criterion": "A1", "score": score,
             "justification": "Good.", "strengths": ["Clear objectives"],
             "weaknesses": [], "suggestions": []},
            {"criterion": "A", "sub_criterion": "A2", "score": score,
             "justification": "Novel.", "strengths": ["Original approach"],
             "weaknesses": [], "suggestions": []},
            {"criterion": "B", "sub_criterion": "B1", "score": score,
             "justification": "Strong PI.", "strengths": ["Track record"],
             "weaknesses": [], "suggestions": []},
            {"criterion": "B", "sub_criterion": "B2", "score": score,
             "justification": "Good team.", "strengths": ["Complementary"],
             "weaknesses": [], "suggestions": []},
            {"criterion": "C", "sub_criterion": "C", "score": score,
             "justification": "Feasible.", "strengths": ["Realistic plan"],
             "weaknesses": [], "suggestions": []},
        ],
        "general_comments": "Well-structured proposal with clear objectives.",
        "major_revisions": [],
        "minor_revisions": ["Add more detail to task 2."],
        "decision": decision,
    })


def _mock_generate_side_effect():
    """Return a side_effect function that produces contextual mock responses."""
    call_count = 0

    async def _side_effect(prompt: str = "", system: str = "", max_tokens: int = 4096,
                           temperature: float = 0.3) -> LLMResponse:
        nonlocal call_count
        call_count += 1
        text = prompt.lower()

        # Review responses (check BEFORE tasks — review prompts also mention "task")
        if "evaluate" in text and "fct" in text:
            return _mock_llm_response(_build_review_json())
        # Consensus narrative
        if "synthesise" in text or "consensus" in text:
            return _mock_llm_response("Panel consensus: strong proposal with minor suggestions.")
        # Tasks, deliverables, milestones return JSON
        if "generate tasks" in text or ("task" in text and "json" in text):
            return _mock_llm_response(_build_tasks_json())
        if "deliverables" in text and "json" in text:
            return _mock_llm_response(_build_deliverables_json())
        if "milestones" in text and "json" in text:
            return _mock_llm_response(_build_milestones_json())
        # Section generation — determine limit from prompt
        for section, limit in [
            ("abstract_en", CHAR_LIMITS.abstract_en),
            ("abstract_pt", CHAR_LIMITS.abstract_pt),
            ("state_of_art", CHAR_LIMITS.state_of_art_objectives),
            ("research_plan", CHAR_LIMITS.research_plan_methods),
            ("institution", CHAR_LIMITS.institution_description),
            ("management", CHAR_LIMITS.management_structure),
            ("ethics", CHAR_LIMITS.ethics_justification),
            ("career_profile", CHAR_LIMITS.career_profile),
            ("contributions_new_ideas", CHAR_LIMITS.contributions_new_ideas),
            ("contributions_teams", CHAR_LIMITS.contributions_teams),
            ("contributions_society", CHAR_LIMITS.contributions_society),
            ("team_cv", CHAR_LIMITS.team_cv_synopsis),
        ]:
            if section in text:
                return _mock_llm_response(_build_section_text(section, limit))

        # Default fallback
        return _mock_llm_response(f"Generated content for call {call_count}.")

    return _side_effect


@pytest.fixture
def mock_llm():
    """Create a mock LLM client with contextual responses."""
    llm = AsyncMock()
    llm.generate = AsyncMock(side_effect=_mock_generate_side_effect())
    llm.generate_json = AsyncMock(side_effect=_mock_generate_side_effect())
    return llm


@pytest.fixture
def mock_scopus():
    """Create a mock Scopus scraper that returns no results."""
    scopus = MagicMock()
    scopus.is_available = False
    return scopus


@pytest.fixture
def draft_pex():
    """Load the PDSPP-Pilot PEX draft."""
    path = DRAFTS_DIR / "pdspp_pilot_pex.yaml"
    if not path.exists():
        pytest.skip(f"Personal draft not available: {path.name}")
    data = yaml.safe_load(path.read_text())
    return DraftIdea(**data)


@pytest.fixture
def draft_example():
    """Load the example SR&TD draft."""
    path = DRAFTS_DIR / "example_idea.yaml"
    data = yaml.safe_load(path.read_text())
    return DraftIdea(**data)


# =============================================================================
# Integration Tests
# =============================================================================

class TestPipelineIntegration:
    """Full pipeline run with mocked LLMs."""

    @pytest.mark.asyncio
    async def test_pipeline_produces_proposal(self, mock_llm, mock_scopus, draft_example, tmp_path):
        generator = ProposalGenerator(llm=mock_llm, scopus=mock_scopus)
        panel = ReviewPanel.__new__(ReviewPanel)
        panel.reviewers = []
        panel.consensus_llm = mock_llm

        # Manually set up a minimal panel with mocked reviewers
        from src.reviewers.panel_reviewer import AIReviewer
        from src.config.settings import ReviewerDef

        mock_reviewer_def = ReviewerDef({
            "id": "mock_reviewer", "enabled": True, "provider": "anthropic",
            "model": "mock", "perspective": "general", "focus_criteria": ["A1", "A2", "B1", "B2", "C"],
        })
        reviewer = AIReviewer.__new__(AIReviewer)
        reviewer.defn = mock_reviewer_def
        reviewer.llm = mock_llm
        panel.reviewers = [reviewer]

        reviser = RevisionEngine(llm=mock_llm)
        pipeline = Pipeline(generator=generator, panel=panel, reviser=reviser)

        result = await pipeline.run(draft_example, iterations=1, output_dir=tmp_path)

        # Verify structure
        assert "proposal" in result
        assert "final_review" in result
        assert "history" in result
        assert "output_dir" in result

        proposal = result["proposal"]

        # Non-empty core sections
        assert len(proposal.title_en) > 0
        assert len(proposal.abstract_en) > 0
        assert len(proposal.state_of_art_objectives) > 0
        assert len(proposal.research_plan_methods) > 0
        assert len(proposal.management_structure) > 0

        # Character limits respected
        report = proposal.char_count_report()
        for section, info in report.items():
            assert info["remaining"] >= 0, (
                f"{section}: {info['actual']} chars exceeds limit {info['limit']}"
            )

        # Tasks generated
        assert len(proposal.tasks) >= 1
        for task in proposal.tasks:
            assert task.number >= 1
            assert len(task.denomination) > 0

        # Deliverables and milestones generated
        assert len(proposal.deliverables) >= 1
        assert len(proposal.milestones) >= 1

        # Review completed
        consensus = result["final_review"]
        assert consensus is not None
        assert 1.0 <= consensus.consensus_score <= 10.0
        assert consensus.panel_decision in ("accept", "minor_revision", "major_revision", "reject")

        # History tracked
        assert len(result["history"]) == 1
        assert "score" in result["history"][0]
        assert "decision" in result["history"][0]

    @pytest.mark.asyncio
    async def test_pipeline_pex_draft(self, mock_llm, mock_scopus, draft_pex, tmp_path):
        generator = ProposalGenerator(llm=mock_llm, scopus=mock_scopus)
        panel = ReviewPanel.__new__(ReviewPanel)
        panel.reviewers = []
        panel.consensus_llm = mock_llm
        reviser = RevisionEngine(llm=mock_llm)

        pipeline = Pipeline(generator=generator, panel=panel, reviser=reviser)
        result = await pipeline.run(draft_pex, iterations=1, output_dir=tmp_path)

        proposal = result["proposal"]
        assert proposal.typology == ProjectType.PEX
        assert proposal.duration_months <= 18

    @pytest.mark.asyncio
    async def test_pipeline_output_files(self, mock_llm, mock_scopus, draft_example, tmp_path):
        generator = ProposalGenerator(llm=mock_llm, scopus=mock_scopus)
        panel = ReviewPanel.__new__(ReviewPanel)
        panel.reviewers = []
        panel.consensus_llm = mock_llm
        reviser = RevisionEngine(llm=mock_llm)

        pipeline = Pipeline(generator=generator, panel=panel, reviser=reviser)

        with patch("src.generators.pipeline.cfg") as mock_cfg:
            mock_cfg.iterations = 1
            mock_cfg.stop_on_accept = True
            mock_cfg.save_intermediates = True
            mock_cfg.out_json = True
            mock_cfg.out_markdown = True
            mock_cfg.out_char_report = True
            mock_cfg.out_docx = False
            mock_cfg.include_review_narrative = True
            mock_cfg.output_dir = str(tmp_path)

            result = await pipeline.run(draft_example, iterations=1, output_dir=tmp_path)

        # Check output files were created (now in subdirectories)
        assert (tmp_path / "proposals" / "final_proposal.json").exists()
        assert (tmp_path / "proposals" / "final_proposal.txt").exists()
        assert (tmp_path / "summary" / "proposal_summary.md").exists()
        assert (tmp_path / "summary" / "char_report.json").exists()
        assert (tmp_path / "summary" / "char_report.txt").exists()

        # Validate JSON output is parseable
        proposal_json = json.loads(
            (tmp_path / "proposals" / "final_proposal.json").read_text())
        assert "title_en" in proposal_json
        assert "tasks" in proposal_json

        # Validate char report
        char_report = json.loads(
            (tmp_path / "summary" / "char_report.json").read_text())
        assert "abstract_en" in char_report
        assert "state_of_art_objectives" in char_report


class TestDraftLoading:
    """Verify all drafts load into DraftIdea models."""

    @pytest.mark.parametrize("yaml_path", sorted(DRAFTS_DIR.glob("*.yaml")),
                             ids=lambda p: p.name)
    def test_draft_loads_as_model(self, yaml_path):
        data = yaml.safe_load(yaml_path.read_text())
        draft = DraftIdea(**data)
        assert draft.title
        assert len(draft.research_topic) >= 50
        assert draft.typology in (ProjectType.ICDT, ProjectType.PEX)

    @pytest.mark.parametrize("yaml_path", sorted(DRAFTS_DIR.glob("*.yaml")),
                             ids=lambda p: p.name)
    def test_draft_respects_typology_limits(self, yaml_path):
        data = yaml.safe_load(yaml_path.read_text())
        draft = DraftIdea(**data)
        rules = TYPOLOGY_RULES[draft.typology]
        if draft.estimated_budget > 0:
            assert draft.estimated_budget <= rules.max_funding_eur, (
                f"{yaml_path.name}: budget {draft.estimated_budget} > {rules.max_funding_eur}"
            )
        if draft.duration_months > 0:
            assert draft.duration_months <= rules.max_duration_months, (
                f"{yaml_path.name}: duration {draft.duration_months} > {rules.max_duration_months}"
            )
