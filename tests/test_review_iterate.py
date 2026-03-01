"""
Tests for FCT-REVIEW-ITERATE v1: suggestion models, grading, ranking,
readiness computation, stoplight logic, consistency checks, and full engine flow.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.generators.models import (
    Actionability,
    Confidence,
    ConsensusReport,
    ConsistencyCheck,
    CostSummary,
    CriterionScore,
    Dependency,
    DraftIdea,
    Effort,
    EvidenceStatus,
    Impact,
    ImprovementReport,
    LLMCallRecord,
    Proposal,
    ReviewReport,
    Severity,
    StoplightEntry,
    SuggestionAction,
    SuggestionRecord,
    SEVERITY_PENALTY,
)
from src.utils.llm_client import LLMResponse, LLMProvider


# =============================================================================
# Fixtures
# =============================================================================

def _make_suggestion(
    id: str = "SUG-001",
    severity: Severity = Severity.S1,
    impact: Impact = Impact.I1,
    dependency: Dependency = Dependency.D0,
    effort: Effort = Effort.F1,
    actionability: Actionability = Actionability.A1,
    criterion_tags: list[str] | None = None,
    target_sections: list[str] | None = None,
) -> SuggestionRecord:
    return SuggestionRecord(
        id=id,
        source_reviewer="test_reviewer",
        source_text="Original critique text.",
        issue=f"Issue for {id}",
        recommended_fix="Fix this by doing X.",
        criterion_tags=criterion_tags or ["A1"],
        target_sections=target_sections or ["state_of_art_objectives"],
        severity=severity,
        evidence_status=EvidenceStatus.E1,
        confidence=Confidence.C1,
        effort=effort,
        impact=impact,
        dependency=dependency,
        actionability=actionability,
        acceptance_test="Check that X is addressed.",
    )


def _make_action(
    suggestion_id: str = "SUG-001",
    action: str = "adopted",
    section: str = "state_of_art_objectives",
) -> SuggestionAction:
    return SuggestionAction(
        suggestion_id=suggestion_id,
        action=action,
        edit_summary="Revised section.",
        section_modified=section,
        before_text_snippet="Before text...",
        after_text_snippet="After text...",
        acceptance_test_result="Pass" if action == "adopted" else "Deferred",
    )


def _make_consensus(score: float = 6.0, decision: str = "major_revision") -> ConsensusReport:
    review = ReviewReport(
        reviewer_id="mock_reviewer",
        reviewer_model="mock-model",
        reviewer_provider="anthropic",
        perspective="general",
        overall_score=score,
        criterion_scores=[
            CriterionScore(
                criterion="A", sub_criterion="A1", score=score,
                justification="Needs improvement.",
                strengths=["Good structure"],
                weaknesses=["Lacks rigour in methodology"],
                suggestions=["Add formal hypothesis testing framework"],
            ),
            CriterionScore(
                criterion="A", sub_criterion="A2", score=score + 0.5,
                justification="Somewhat novel.",
                strengths=["Novel approach"],
                weaknesses=["Prior art coverage insufficient"],
                suggestions=["Expand literature review"],
            ),
            CriterionScore(
                criterion="C", sub_criterion="C", score=score - 0.5,
                justification="Feasibility concerns.",
                strengths=["Clear timeline"],
                weaknesses=["Budget mismatch with tasks"],
                suggestions=["Reconcile task budgets with total"],
            ),
        ],
        general_comments="Proposal has potential but needs revision.",
        major_revisions=["Strengthen methodology section", "Fix budget consistency"],
        minor_revisions=["Improve abstract clarity"],
        decision=decision,
    )
    return ConsensusReport(
        individual_reviews=[review],
        consensus_score=score,
        weighted_scores={"A": score, "B": score, "C": score - 0.5},
        key_strengths=["Novel approach", "Clear timeline"],
        key_weaknesses=["Methodology gaps", "Budget issues"],
        priority_revisions=["Fix methodology", "Reconcile budget"],
        panel_decision=decision,
        panel_narrative="Panel recommends major revisions.",
    )


def _make_proposal() -> Proposal:
    from src.generators.models import ProposalTask, TaskBudget, Deliverable, Milestone
    from src.config.fct_constants import DeliverableType

    return Proposal(
        title_en="Test Proposal",
        acronym="TEST",
        duration_months=36,
        total_budget=200000,
        abstract_en="This is a test abstract for the proposal." * 20,
        abstract_pt="Este e um resumo de teste para a proposta." * 20,
        state_of_art_objectives="State of art text with objectives." * 50,
        research_plan_methods="Research plan with methods and approach." * 80,
        bibliographic_references="[1] Reference one. [2] Reference two." * 30,
        management_structure="Management structure with clear roles." * 20,
        career_profile="PI career profile with track record." * 20,
        contributions_new_ideas="Novel contributions in the field." * 20,
        contributions_teams="Team building and mentoring." * 15,
        contributions_society="Societal impact description." * 15,
        further_details="Additional details." * 20,
        team_cv_synopsis="Team CV synopsis." * 30,
        ethics_justification="Ethics considerations including informed consent timeline and approval before month 3." * 10,
        tasks=[
            ProposalTask(
                number=1, denomination="Literature Review",
                description="Conduct systematic literature review with participant interviews.",
                person_months=4.0, start_month=1, duration_months=8,
                budget=TaskBudget(human_resources=30000, missions_travel=5000),
            ),
            ProposalTask(
                number=2, denomination="Data Collection",
                description="Primary data collection and analysis.",
                person_months=8.0, start_month=5, duration_months=12,
                budget=TaskBudget(human_resources=50000, equipment=10000),
            ),
            ProposalTask(
                number=3, denomination="Dissemination",
                description="Results dissemination and publications.",
                person_months=4.0, start_month=15, duration_months=6,
                budget=TaskBudget(human_resources=15000, registrations_publications=5000),
            ),
        ],
        deliverables=[
            Deliverable(code="D1.1", title="SLR Report", type=DeliverableType.REPORT,
                        related_tasks=[1], due_month=6),
            Deliverable(code="D2.1", title="Dataset", type=DeliverableType.DATASET,
                        related_tasks=[2], due_month=14),
        ],
        milestones=[
            Milestone(code="M1", denomination="Framework Complete",
                      related_tasks=[1], due_month=8),
            Milestone(code="M2", denomination="Data Collected",
                      related_tasks=[2], due_month=16),
        ],
    )


def _make_draft() -> DraftIdea:
    return DraftIdea(
        title="Test Research Idea",
        research_topic="A comprehensive study of testing methodologies in software engineering " * 5,
        research_questions=["RQ1: How effective are current testing methods?"],
    )


def _mock_llm_response(text: str) -> LLMResponse:
    return LLMResponse(
        text=text, model="mock-model", provider=LLMProvider.ANTHROPIC,
        input_tokens=100, output_tokens=len(text), finish_reason="stop",
    )


# =============================================================================
# Unit Tests: Models
# =============================================================================

class TestSuggestionModels:

    def test_suggestion_record_creation(self):
        sug = _make_suggestion()
        assert sug.id == "SUG-001"
        assert sug.severity == Severity.S1
        assert sug.impact == Impact.I1

    def test_suggestion_record_json_roundtrip(self):
        sug = _make_suggestion()
        json_str = sug.model_dump_json()
        restored = SuggestionRecord.model_validate_json(json_str)
        assert restored.id == sug.id
        assert restored.severity == sug.severity
        assert restored.criterion_tags == sug.criterion_tags

    def test_suggestion_record_defaults(self):
        sug = SuggestionRecord()
        assert sug.severity == Severity.S1
        assert sug.effort == Effort.F1
        assert sug.dependency == Dependency.D0
        assert sug.target_sections == []
        assert sug.depends_on == []

    def test_severity_enum_values(self):
        assert Severity.S3.value == "S3"
        assert Severity.S0.value == "S0"

    def test_severity_penalty_mapping(self):
        assert SEVERITY_PENALTY[Severity.S3] == 15
        assert SEVERITY_PENALTY[Severity.S2] == 8
        assert SEVERITY_PENALTY[Severity.S1] == 3
        assert SEVERITY_PENALTY[Severity.S0] == 1

    def test_suggestion_action_creation(self):
        action = _make_action()
        assert action.suggestion_id == "SUG-001"
        assert action.action == "adopted"

    def test_consistency_check_creation(self):
        check = ConsistencyCheck(
            check_name="budget_totals_reconcile", passed=True, details="OK.",
        )
        assert check.passed is True
        assert check.auto_fixed is False

    def test_stoplight_entry_creation(self):
        entry = StoplightEntry(
            criterion="A", color="green", s3_count=0, s2_count=0,
            rationale="No issues.",
        )
        assert entry.color == "green"

    def test_improvement_report_creation(self):
        report = ImprovementReport(
            version=1, timestamp="2026-03-01T00:00:00Z",
            readiness_index=75.0,
        )
        assert report.version == 1
        assert report.all_suggestions == []
        assert report.actions == []


# =============================================================================
# Unit Tests: Readiness Computation
# =============================================================================

class TestReadinessComputation:

    def test_perfect_readiness_no_suggestions(self):
        from src.reviewers.review_iterate import ReviewIterateEngine
        score = ReviewIterateEngine._compute_readiness([], [])
        assert score == 100.0

    def test_s3_penalty(self):
        from src.reviewers.review_iterate import ReviewIterateEngine
        suggestions = [_make_suggestion(severity=Severity.S3)]
        actions = [_make_action(action="deferred")]
        score = ReviewIterateEngine._compute_readiness(suggestions, actions)
        assert score == 100.0 - 15  # S3 = -15

    def test_s2_penalty(self):
        from src.reviewers.review_iterate import ReviewIterateEngine
        suggestions = [_make_suggestion(severity=Severity.S2)]
        actions = [_make_action(action="deferred")]
        score = ReviewIterateEngine._compute_readiness(suggestions, actions)
        assert score == 100.0 - 8  # S2 = -8

    def test_s1_penalty(self):
        from src.reviewers.review_iterate import ReviewIterateEngine
        suggestions = [_make_suggestion(severity=Severity.S1)]
        actions = [_make_action(action="deferred")]
        score = ReviewIterateEngine._compute_readiness(suggestions, actions)
        assert score == 100.0 - 3  # S1 = -3

    def test_s0_penalty(self):
        from src.reviewers.review_iterate import ReviewIterateEngine
        suggestions = [_make_suggestion(severity=Severity.S0)]
        actions = [_make_action(action="deferred")]
        score = ReviewIterateEngine._compute_readiness(suggestions, actions)
        assert score == 100.0 - 1  # S0 = -1

    def test_adopted_no_penalty(self):
        from src.reviewers.review_iterate import ReviewIterateEngine
        suggestions = [_make_suggestion(severity=Severity.S3)]
        actions = [_make_action(action="adopted")]
        score = ReviewIterateEngine._compute_readiness(suggestions, actions)
        assert score == 100.0  # adopted = no penalty

    def test_partially_adopted_half_penalty(self):
        from src.reviewers.review_iterate import ReviewIterateEngine
        suggestions = [_make_suggestion(severity=Severity.S2)]
        actions = [_make_action(action="partially_adopted")]
        score = ReviewIterateEngine._compute_readiness(suggestions, actions)
        assert score == 100.0 - (8 * 0.5)  # S2 half penalty = -4

    def test_a2_bonus_capped_at_10(self):
        from src.reviewers.review_iterate import ReviewIterateEngine
        suggestions = [
            _make_suggestion(id=f"SUG-{i:03d}", actionability=Actionability.A2)
            for i in range(1, 8)
        ]
        actions = [_make_action(suggestion_id=f"SUG-{i:03d}") for i in range(1, 8)]
        score = ReviewIterateEngine._compute_readiness(suggestions, actions)
        # 7 A2 adopted * 2 = 14 bonus, capped at +10. No penalties (all adopted).
        # 100 + 10 = 110, clamped to 100.
        assert score == 100.0

    def test_readiness_clamped_to_zero(self):
        from src.reviewers.review_iterate import ReviewIterateEngine
        suggestions = [
            _make_suggestion(id=f"SUG-{i:03d}", severity=Severity.S3)
            for i in range(1, 10)
        ]
        actions = [
            _make_action(suggestion_id=f"SUG-{i:03d}", action="deferred")
            for i in range(1, 10)
        ]
        score = ReviewIterateEngine._compute_readiness(suggestions, actions)
        assert score == 0.0  # 9 * -15 = -135, clamped to 0

    def test_multiple_severities_combined(self):
        from src.reviewers.review_iterate import ReviewIterateEngine
        suggestions = [
            _make_suggestion(id="SUG-001", severity=Severity.S3),
            _make_suggestion(id="SUG-002", severity=Severity.S1),
            _make_suggestion(id="SUG-003", severity=Severity.S0),
        ]
        actions = [
            _make_action(suggestion_id="SUG-001", action="adopted"),
            _make_action(suggestion_id="SUG-002", action="deferred"),
            _make_action(suggestion_id="SUG-003", action="deferred"),
        ]
        score = ReviewIterateEngine._compute_readiness(suggestions, actions)
        # SUG-001 adopted (no penalty), SUG-002 deferred (-3), SUG-003 deferred (-1)
        assert score == 100.0 - 3 - 1  # = 96.0


# =============================================================================
# Unit Tests: Stoplight Computation
# =============================================================================

class TestStoplightComputation:

    def test_green_no_issues(self):
        from src.reviewers.review_iterate import ReviewIterateEngine
        entries = ReviewIterateEngine._compute_stoplight([])
        for entry in entries:
            assert entry.color == "green"

    def test_green_with_minor_only(self):
        from src.reviewers.review_iterate import ReviewIterateEngine
        suggestions = [
            _make_suggestion(severity=Severity.S0, criterion_tags=["A1"]),
            _make_suggestion(id="SUG-002", severity=Severity.S1, criterion_tags=["A2"]),
        ]
        entries = ReviewIterateEngine._compute_stoplight(suggestions)
        a_entry = next(e for e in entries if e.criterion == "A")
        assert a_entry.color == "green"

    def test_green_with_one_s2(self):
        from src.reviewers.review_iterate import ReviewIterateEngine
        suggestions = [
            _make_suggestion(severity=Severity.S2, criterion_tags=["A1"]),
        ]
        entries = ReviewIterateEngine._compute_stoplight(suggestions)
        a_entry = next(e for e in entries if e.criterion == "A")
        assert a_entry.color == "green"
        assert a_entry.s2_count == 1

    def test_amber_with_two_s2(self):
        from src.reviewers.review_iterate import ReviewIterateEngine
        suggestions = [
            _make_suggestion(id="SUG-001", severity=Severity.S2, criterion_tags=["A1"]),
            _make_suggestion(id="SUG-002", severity=Severity.S2, criterion_tags=["A2"]),
        ]
        entries = ReviewIterateEngine._compute_stoplight(suggestions)
        a_entry = next(e for e in entries if e.criterion == "A")
        assert a_entry.color == "amber"
        assert a_entry.s2_count == 2

    def test_red_with_s3(self):
        from src.reviewers.review_iterate import ReviewIterateEngine
        suggestions = [
            _make_suggestion(severity=Severity.S3, criterion_tags=["C"]),
        ]
        entries = ReviewIterateEngine._compute_stoplight(suggestions)
        c_entry = next(e for e in entries if e.criterion == "C")
        assert c_entry.color == "red"
        assert c_entry.s3_count == 1

    def test_red_with_four_s2(self):
        from src.reviewers.review_iterate import ReviewIterateEngine
        suggestions = [
            _make_suggestion(id=f"SUG-{i:03d}", severity=Severity.S2, criterion_tags=["B1"])
            for i in range(1, 5)
        ]
        entries = ReviewIterateEngine._compute_stoplight(suggestions)
        b_entry = next(e for e in entries if e.criterion == "B")
        assert b_entry.color == "red"
        assert b_entry.s2_count == 4


# =============================================================================
# Unit Tests: Ranking
# =============================================================================

class TestRanking:

    def test_severity_desc_sort(self):
        from src.reviewers.review_iterate import CritiqueAtomizer
        suggestions = [
            _make_suggestion(id="SUG-001", severity=Severity.S0),
            _make_suggestion(id="SUG-002", severity=Severity.S3),
            _make_suggestion(id="SUG-003", severity=Severity.S1),
        ]
        ranked = CritiqueAtomizer.rank(suggestions)
        assert ranked[0].id == "SUG-002"  # S3 first
        assert ranked[1].id == "SUG-003"  # S1 second
        assert ranked[2].id == "SUG-001"  # S0 last

    def test_impact_desc_tiebreak(self):
        from src.reviewers.review_iterate import CritiqueAtomizer
        suggestions = [
            _make_suggestion(id="SUG-001", severity=Severity.S2, impact=Impact.I0),
            _make_suggestion(id="SUG-002", severity=Severity.S2, impact=Impact.I3),
        ]
        ranked = CritiqueAtomizer.rank(suggestions)
        assert ranked[0].id == "SUG-002"  # I3 first
        assert ranked[1].id == "SUG-001"  # I0 second

    def test_dependency_desc_tiebreak(self):
        from src.reviewers.review_iterate import CritiqueAtomizer
        suggestions = [
            _make_suggestion(
                id="SUG-001", severity=Severity.S2, impact=Impact.I2,
                dependency=Dependency.D0,
            ),
            _make_suggestion(
                id="SUG-002", severity=Severity.S2, impact=Impact.I2,
                dependency=Dependency.D2,
            ),
        ]
        ranked = CritiqueAtomizer.rank(suggestions)
        assert ranked[0].id == "SUG-002"  # D2 first
        assert ranked[1].id == "SUG-001"  # D0 second

    def test_effort_asc_tiebreak(self):
        from src.reviewers.review_iterate import CritiqueAtomizer
        suggestions = [
            _make_suggestion(
                id="SUG-001", severity=Severity.S1, impact=Impact.I1,
                dependency=Dependency.D0, effort=Effort.F3,
            ),
            _make_suggestion(
                id="SUG-002", severity=Severity.S1, impact=Impact.I1,
                dependency=Dependency.D0, effort=Effort.F0,
            ),
        ]
        ranked = CritiqueAtomizer.rank(suggestions)
        assert ranked[0].id == "SUG-002"  # F0 first (less effort)
        assert ranked[1].id == "SUG-001"  # F3 second

    def test_top_n(self):
        from src.reviewers.review_iterate import CritiqueAtomizer
        suggestions = [_make_suggestion(id=f"SUG-{i:03d}") for i in range(1, 11)]
        top = CritiqueAtomizer.top_n(suggestions, n=3)
        assert len(top) == 3
        assert top[0].id == "SUG-001"


# =============================================================================
# Unit Tests: Budget & Timeline Checks
# =============================================================================

class TestBudgetTotalsCheck:

    def test_pass_within_tolerance(self):
        from src.reviewers.review_iterate import ConsistencyChecker
        proposal = _make_proposal()
        # Task budgets: T1=43750, T2=75000, T3=25000 = 143750 total
        # Total budget: 200000 — well within 5%? Actually diff=56250, threshold=10000
        # Let's set total to match task totals
        proposal.total_budget = 145000.0
        check = ConsistencyChecker._check_budget_totals(proposal)
        assert check.check_name == "budget_totals_reconcile"
        # Task totals: T1: (30000+5000)*1.25=43750, T2: (50000+10000)*1.25=75000,
        # T3: (15000+5000)*1.25=25000 = 143750
        # diff = |143750 - 145000| = 1250, threshold = 7250 → passes
        assert check.passed is True

    def test_fail_over_tolerance(self):
        from src.reviewers.review_iterate import ConsistencyChecker
        proposal = _make_proposal()
        proposal.total_budget = 100000.0  # Way off from task totals
        check = ConsistencyChecker._check_budget_totals(proposal)
        assert check.passed is False
        assert "MISMATCH" in check.details

    def test_skip_when_no_tasks(self):
        from src.reviewers.review_iterate import ConsistencyChecker
        proposal = _make_proposal()
        proposal.tasks = []
        check = ConsistencyChecker._check_budget_totals(proposal)
        assert check.passed is True
        assert "skipped" in check.details.lower()


class TestTimelineCheck:

    def test_pass_no_human_subjects(self):
        from src.reviewers.review_iterate import ConsistencyChecker
        proposal = _make_proposal()
        # Remove human-subject keywords from tasks
        for task in proposal.tasks:
            task.description = "Pure computational analysis."
            task.denomination = "Computation"
        check = ConsistencyChecker._check_timeline_ethics(proposal)
        assert check.passed is True

    def test_pass_with_timing_in_ethics(self):
        from src.reviewers.review_iterate import ConsistencyChecker
        proposal = _make_proposal()
        # Task 1 mentions interviews, ethics mentions month
        check = ConsistencyChecker._check_timeline_ethics(proposal)
        assert check.passed is True  # Default proposal has timing keywords in ethics

    def test_fail_without_timing_in_ethics(self):
        from src.reviewers.review_iterate import ConsistencyChecker
        proposal = _make_proposal()
        proposal.ethics_justification = "No ethical concerns anticipated."
        check = ConsistencyChecker._check_timeline_ethics(proposal)
        assert check.passed is False  # Task 1 has "interviews" but ethics has no timing


# =============================================================================
# Async Tests: CritiqueAtomizer
# =============================================================================

class TestCritiqueAtomizer:

    @pytest.mark.asyncio
    async def test_atomize_returns_valid_suggestions(self):
        from src.reviewers.review_iterate import CritiqueAtomizer

        mock_suggestions = json.dumps([
            {
                "id": "SUG-001", "source_reviewer": "mock_reviewer",
                "source_text": "Methodology is weak.",
                "issue": "Methodology lacks formal framework",
                "recommended_fix": "Add hypothesis testing framework",
                "criterion_tags": ["A1"],
                "target_sections": ["research_plan_methods"],
                "severity": "S2", "evidence_status": "E2",
                "confidence": "C2", "effort": "F2",
                "impact": "I3", "dependency": "D0",
                "actionability": "A2",
                "acceptance_test": "Verify hypothesis testing framework present",
                "depends_on": [], "blocks": [],
            },
        ])

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=_mock_llm_response(mock_suggestions))

        atomizer = CritiqueAtomizer(mock_llm)
        consensus = _make_consensus()
        proposal = _make_proposal()

        suggestions = await atomizer.atomize_and_grade(consensus, proposal)
        assert len(suggestions) == 1
        assert suggestions[0].id == "SUG-001"
        assert suggestions[0].severity == Severity.S2
        assert suggestions[0].impact == Impact.I3

    @pytest.mark.asyncio
    async def test_atomize_deduplication(self):
        from src.reviewers.review_iterate import CritiqueAtomizer

        mock_suggestions = json.dumps([
            {
                "id": "SUG-001", "source_reviewer": "reviewer_a",
                "issue": "methodology is weak and lacks framework",
                "severity": "S1", "target_sections": ["research_plan_methods"],
                "criterion_tags": ["A1"], "recommended_fix": "Add framework",
                "evidence_status": "E1", "confidence": "C1", "effort": "F1",
                "impact": "I1", "dependency": "D0", "actionability": "A1",
                "acceptance_test": "Check", "depends_on": [], "blocks": [],
                "source_text": "Weak methodology.",
            },
            {
                "id": "SUG-002", "source_reviewer": "reviewer_b",
                "issue": "methodology is weak and lacks framework",
                "severity": "S2", "target_sections": ["research_plan_methods"],
                "criterion_tags": ["A1"], "recommended_fix": "Add formal testing",
                "evidence_status": "E1", "confidence": "C1", "effort": "F1",
                "impact": "I1", "dependency": "D0", "actionability": "A1",
                "acceptance_test": "Check", "depends_on": [], "blocks": [],
                "source_text": "Weak methodology.",
            },
        ])

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=_mock_llm_response(mock_suggestions))

        atomizer = CritiqueAtomizer(mock_llm)
        consensus = _make_consensus()
        proposal = _make_proposal()

        suggestions = await atomizer.atomize_and_grade(consensus, proposal)
        # Should deduplicate to 1, keeping higher severity (S2)
        assert len(suggestions) == 1
        assert suggestions[0].severity == Severity.S2
        assert "reviewer_b" in suggestions[0].source_reviewer

    @pytest.mark.asyncio
    async def test_atomize_handles_malformed_json(self):
        from src.reviewers.review_iterate import CritiqueAtomizer

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(
            return_value=_mock_llm_response("This is not valid JSON at all.")
        )

        atomizer = CritiqueAtomizer(mock_llm)
        consensus = _make_consensus()
        proposal = _make_proposal()

        suggestions = await atomizer.atomize_and_grade(consensus, proposal)
        assert suggestions == []


# =============================================================================
# Async Tests: ConsistencyChecker
# =============================================================================

class TestConsistencyCheckerAsync:

    @pytest.mark.asyncio
    async def test_llm_checks_parse_correctly(self):
        from src.reviewers.review_iterate import ConsistencyChecker

        mock_results = json.dumps([
            {"check_name": "country_set_consistent", "passed": True,
             "details": "Countries consistent."},
            {"check_name": "hypotheses_traceability", "passed": False,
             "details": "RQ3 has no task."},
            {"check_name": "ethics_human_subjects_consistency", "passed": True,
             "details": "Ethics covers all."},
            {"check_name": "benchmarks_independence_min_package", "passed": True,
             "details": "Independent benchmarks."},
        ])

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=_mock_llm_response(mock_results))

        checker = ConsistencyChecker(mock_llm)
        proposal = _make_proposal()
        draft = _make_draft()

        checks = await checker.run_checks(
            proposal, draft,
            enabled_checks=[
                "country_set_consistent", "hypotheses_traceability",
                "ethics_human_subjects_consistency",
                "benchmarks_independence_min_package",
                "budget_totals_reconcile", "timeline_ethics_gate",
            ],
        )

        # Should have 6 checks (2 structural + 4 LLM)
        assert len(checks) == 6
        check_names = [c.check_name for c in checks]
        assert "budget_totals_reconcile" in check_names
        assert "timeline_ethics_gate" in check_names
        assert "hypotheses_traceability" in check_names

    @pytest.mark.asyncio
    async def test_structural_checks_only(self):
        from src.reviewers.review_iterate import ConsistencyChecker

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock()  # Should NOT be called

        checker = ConsistencyChecker(mock_llm)
        proposal = _make_proposal()
        draft = _make_draft()

        checks = await checker.run_checks(
            proposal, draft,
            enabled_checks=["budget_totals_reconcile", "timeline_ethics_gate"],
        )

        assert len(checks) == 2
        mock_llm.generate.assert_not_called()


# =============================================================================
# Async Tests: Full ReviewIterateEngine
# =============================================================================

class TestReviewIterateEngine:

    @pytest.mark.asyncio
    async def test_full_revise_produces_output(self):
        from src.reviewers.review_iterate import ReviewIterateEngine

        mock_suggestions = json.dumps([{
            "id": "SUG-001", "source_reviewer": "mock",
            "source_text": "Weak.", "issue": "Methodology gaps",
            "recommended_fix": "Add framework",
            "criterion_tags": ["A1"],
            "target_sections": ["state_of_art_objectives"],
            "severity": "S2", "evidence_status": "E1",
            "confidence": "C1", "effort": "F1",
            "impact": "I2", "dependency": "D0",
            "actionability": "A2",
            "acceptance_test": "Framework present",
            "depends_on": [], "blocks": [],
        }])

        mock_consistency = json.dumps([
            {"check_name": "country_set_consistent", "passed": True, "details": "OK"},
            {"check_name": "hypotheses_traceability", "passed": True, "details": "OK"},
            {"check_name": "ethics_human_subjects_consistency", "passed": True, "details": "OK"},
            {"check_name": "benchmarks_independence_min_package", "passed": True, "details": "OK"},
        ])

        mock_narrative = json.dumps({
            "executive_summary": "Readiness improved.",
            "science_method_changes": "Added framework.",
            "feasibility_budget_changes": "Budget reconciled.",
            "ethics_compliance_changes": "No changes needed.",
            "risk_register": "| # | Risk | Severity | Mitigation | Owner |\n|---|------|----------|------------|-------|\n| 1 | Timeline | S1 | Buffer | PI |",
        })

        call_count = 0

        async def _side_effect(prompt="", system="", max_tokens=4096, temperature=0.3):
            nonlocal call_count
            call_count += 1
            text = prompt.lower()
            if "extract" in text or "atomize" in text or "grading rubric" in text:
                return _mock_llm_response(mock_suggestions)
            if "consistency" in text and "check" in text:
                return _mock_llm_response(mock_consistency)
            if "narrative" in text or "executive" in text or "improvement report" in text:
                return _mock_llm_response(mock_narrative)
            # Default: section revision
            return _mock_llm_response("Revised section text with improvements." * 50)

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(side_effect=_side_effect)

        with patch("src.reviewers.review_iterate.cfg") as mock_cfg:
            mock_cfg.review_iterate_top_n = 5
            mock_cfg.review_iterate_max_suggestions = 20
            mock_cfg.review_iterate_include_trivial = True
            mock_cfg.review_iterate_consistency_checks = [
                "budget_totals_reconcile", "timeline_ethics_gate",
                "country_set_consistent", "hypotheses_traceability",
                "ethics_human_subjects_consistency",
                "benchmarks_independence_min_package",
            ]
            mock_cfg.revision.temperature = 0.3

            engine = ReviewIterateEngine(llm=mock_llm)
            proposal = _make_proposal()
            consensus = _make_consensus()
            draft = _make_draft()

            revised, report = await engine.revise(
                proposal, consensus, version=1,
                draft=draft, output_dir=None,
            )

        assert isinstance(revised, Proposal)
        assert isinstance(report, ImprovementReport)
        assert report.version == 1
        assert 0 <= report.readiness_index <= 100
        assert len(report.stoplight) == 4
        assert len(report.all_suggestions) >= 1
        assert len(report.actions) >= 1


# =============================================================================
# Tests: Improvement Report Markdown Structure
# =============================================================================

class TestImprovementReportStructure:

    def test_all_12_sections_present(self):
        from src.utils.txt_formatter import improvement_report_to_md

        report = ImprovementReport(
            version=1,
            timestamp="2026-03-01T00:00:00Z",
            readiness_index=75.0,
            stoplight=[
                StoplightEntry(criterion="A", color="green", s3_count=0, s2_count=1,
                               rationale="Minor issues"),
                StoplightEntry(criterion="B", color="amber", s3_count=0, s2_count=2,
                               rationale="Team gaps"),
                StoplightEntry(criterion="C", color="red", s3_count=1, s2_count=0,
                               rationale="Budget fatal"),
                StoplightEntry(criterion="E", color="green", s3_count=0, s2_count=0,
                               rationale="No issues"),
            ],
            all_suggestions=[
                _make_suggestion(id="SUG-001", severity=Severity.S3, criterion_tags=["C"]),
                _make_suggestion(id="SUG-002", severity=Severity.S2, criterion_tags=["A1"]),
            ],
            actions=[
                _make_action(suggestion_id="SUG-001", action="adopted"),
                _make_action(suggestion_id="SUG-002", action="deferred"),
            ],
            consistency_checks=[
                ConsistencyCheck(check_name="budget_totals_reconcile", passed=False,
                                 details="Mismatch."),
                ConsistencyCheck(check_name="timeline_ethics_gate", passed=True,
                                 details="OK."),
            ],
            top5_ids=["SUG-001", "SUG-002"],
            executive_summary="Good progress but budget needs fixing.",
            science_method_changes="Added hypothesis framework.",
            feasibility_budget_changes="Budget partially reconciled.",
            ethics_compliance_changes="No changes.",
            risk_register="| # | Risk | Severity | Mitigation | Owner |\n|---|------|----------|------------|-------|\n| 1 | Budget | S3 | Rebalance | PI |",
        )

        md = improvement_report_to_md(report, version=1)

        # All 12 section headers present
        assert "## 1. Executive Summary" in md
        assert "## 2. Version Metadata" in md
        assert "## 3. Actions Summary" in md
        assert "## 4. Edits Executed" in md
        assert "## 5. Non-adoptions & Deferrals" in md
        assert "## 6. Change Log" in md
        assert "## 7. Traceability Matrix" in md
        assert "## 8. Science & Method Changes" in md
        assert "## 9. Feasibility & Budget Changes" in md
        assert "## 10. Ethics & Compliance Changes" in md
        assert "## 11. Consistency Check Results" in md
        assert "## 12. Post-revision Risk Register" in md

        # Key data present
        assert "75.0/100" in md
        assert "SUG-001" in md
        assert "SUG-002" in md
        assert "budget_totals_reconcile" in md
        assert "FAIL" in md


# =============================================================================
# Tests: Application Markdown
# =============================================================================

class TestApplicationMarkdown:

    def test_proposal_to_application_md(self):
        from src.utils.txt_formatter import proposal_to_application_md

        proposal = _make_proposal()
        md = proposal_to_application_md(proposal)

        assert "# Test Proposal" in md
        assert "## Abstract (EN)" in md
        assert "## Tasks" in md
        assert "| # | Task |" in md  # Task table header
        assert "## Deliverables" in md
        assert "## Milestones" in md
        assert "## Management Structure" in md


# =============================================================================
# Integration: Pipeline with ReviewIterate
# =============================================================================

class TestPipelineWithReviewIterate:

    @pytest.mark.asyncio
    async def test_pipeline_uses_review_iterate_when_enabled(self, tmp_path):
        from src.generators.pipeline import Pipeline
        from src.generators.proposal_generator import ProposalGenerator
        from src.reviewers.panel_reviewer import ReviewPanel, RevisionEngine, AIReviewer
        from src.config.settings import ReviewerDef
        from src.reviewers.review_iterate import ReviewIterateEngine

        mock_suggestions = json.dumps([{
            "id": "SUG-001", "source_reviewer": "mock",
            "source_text": "Weak.", "issue": "Methodology gaps",
            "recommended_fix": "Add framework",
            "criterion_tags": ["A1"],
            "target_sections": ["state_of_art_objectives"],
            "severity": "S1", "evidence_status": "E1",
            "confidence": "C1", "effort": "F1",
            "impact": "I1", "dependency": "D0",
            "actionability": "A1",
            "acceptance_test": "Check",
            "depends_on": [], "blocks": [],
        }])

        mock_consistency = json.dumps([
            {"check_name": "country_set_consistent", "passed": True, "details": "OK"},
        ])

        mock_narrative = json.dumps({
            "executive_summary": "Summary.",
            "science_method_changes": "Changes.",
            "feasibility_budget_changes": "Budget.",
            "ethics_compliance_changes": "Ethics.",
            "risk_register": "| # | Risk |\n|---|------|\n| 1 | None |",
        })

        from src.config.fct_constants import CHAR_LIMITS

        def _build_section_text(section: str, limit: int) -> str:
            base = f"This is the generated {section} section. "
            return (base * (limit // len(base) + 1))[:limit - 100]

        def _build_tasks_json():
            return json.dumps([{
                "number": 1, "denomination": "Task One",
                "description": "Description.", "person_months": 4.0,
                "start_month": 1, "duration_months": 8,
            }])

        def _build_review_json(score=6.0):
            return json.dumps({
                "overall_score": score,
                "criterion_scores": [
                    {"criterion": "A", "sub_criterion": "A1", "score": score,
                     "strengths": ["Good"], "weaknesses": ["Needs more detail"],
                     "suggestions": ["Add detail"]},
                    {"criterion": "A", "sub_criterion": "A2", "score": score,
                     "strengths": ["Novel"], "weaknesses": [], "suggestions": []},
                    {"criterion": "B", "sub_criterion": "B1", "score": score,
                     "strengths": ["Strong"], "weaknesses": [], "suggestions": []},
                    {"criterion": "B", "sub_criterion": "B2", "score": score,
                     "strengths": ["Team"], "weaknesses": [], "suggestions": []},
                    {"criterion": "C", "sub_criterion": "C", "score": score,
                     "strengths": ["Feasible"], "weaknesses": [], "suggestions": []},
                ],
                "general_comments": "Needs revision.", "major_revisions": ["Fix methodology"],
                "minor_revisions": [], "decision": "major_revision",
            })

        async def _side_effect(prompt="", system="", max_tokens=4096, temperature=0.3):
            text = prompt.lower()
            if "evaluate" in text and "fct" in text:
                return _mock_llm_response(_build_review_json())
            if "synthesise" in text or "consensus" in text:
                return _mock_llm_response("Panel consensus.")
            # Draft updater prompt
            if "improve the draft idea" in text or "draft fields" in text:
                return _mock_llm_response(json.dumps({
                    "updated_fields": {},
                    "changes_log": [{"field": "none", "change": "no change"}],
                }))
            if "grading rubric" in text or "atomize" in text:
                return _mock_llm_response(mock_suggestions)
            if "consistency" in text and "auditor" in text:
                return _mock_llm_response(mock_consistency)
            if "improvement report" in text or "narrative" in text:
                return _mock_llm_response(mock_narrative)
            if "task" in text and "json" in text:
                return _mock_llm_response(_build_tasks_json())
            if "deliverables" in text:
                return _mock_llm_response("[]")
            if "milestones" in text:
                return _mock_llm_response("[]")
            for section, limit in [
                ("abstract", CHAR_LIMITS.abstract_en),
                ("state_of_art", CHAR_LIMITS.state_of_art_objectives),
                ("research_plan", CHAR_LIMITS.research_plan_methods),
            ]:
                if section in text:
                    return _mock_llm_response(_build_section_text(section, limit))
            return _mock_llm_response("Generated content." * 20)

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(side_effect=_side_effect)
        mock_llm.generate_json = AsyncMock(side_effect=_side_effect)

        from src.generators.models import DraftIdea
        from unittest.mock import MagicMock
        import yaml

        draft_path = Path("drafts/example_idea.yaml")
        data = yaml.safe_load(draft_path.read_text())
        draft = DraftIdea(**data)

        mock_scopus = MagicMock()
        mock_scopus.is_available = False
        generator = ProposalGenerator(llm=mock_llm, scopus=mock_scopus)
        panel = ReviewPanel.__new__(ReviewPanel)
        panel.consensus_llm = mock_llm
        mock_reviewer_def = ReviewerDef({
            "id": "mock_reviewer", "enabled": True, "provider": "anthropic",
            "model": "mock", "perspective": "general",
            "focus_criteria": ["A1", "A2", "B1", "B2", "C"],
        })
        reviewer = AIReviewer.__new__(AIReviewer)
        reviewer.defn = mock_reviewer_def
        reviewer.llm = mock_llm
        panel.reviewers = [reviewer]

        reviser = RevisionEngine(llm=mock_llm)
        ri_engine = ReviewIterateEngine(llm=mock_llm)

        pipeline = Pipeline(
            generator=generator, panel=panel, reviser=reviser,
            review_iterate_engine=ri_engine,
        )

        with patch("src.generators.pipeline.cfg") as mock_cfg, \
             patch("src.generators.draft_updater.get_llm_for_role", return_value=mock_llm):
            mock_cfg.iterations = 2
            mock_cfg.stop_on_accept = False
            mock_cfg.save_intermediates = True
            mock_cfg.out_json = True
            mock_cfg.out_markdown = True
            mock_cfg.out_char_report = False
            mock_cfg.out_docx = False
            mock_cfg.include_review_narrative = True
            mock_cfg.output_dir = str(tmp_path)
            mock_cfg.review_iterate_enabled = True

            with patch("src.reviewers.review_iterate.cfg") as ri_cfg:
                ri_cfg.review_iterate_top_n = 5
                ri_cfg.review_iterate_max_suggestions = 20
                ri_cfg.review_iterate_include_trivial = True
                ri_cfg.review_iterate_consistency_checks = [
                    "budget_totals_reconcile", "timeline_ethics_gate",
                ]
                ri_cfg.revision.temperature = 0.3

                result = await pipeline.run(draft, iterations=2, output_dir=tmp_path)

        assert "improvement_reports" in result
        assert len(result["improvement_reports"]) >= 1
        assert (tmp_path / "improvements").exists()


class TestPipelineBackwardCompat:

    @pytest.mark.asyncio
    async def test_pipeline_unchanged_when_disabled(self, tmp_path):
        from src.generators.pipeline import Pipeline
        from src.generators.proposal_generator import ProposalGenerator
        from src.reviewers.panel_reviewer import ReviewPanel, RevisionEngine

        from src.config.fct_constants import CHAR_LIMITS

        def _build_section_text(section, limit):
            base = f"This is the generated {section} section. "
            return (base * (limit // len(base) + 1))[:limit - 100]

        async def _side_effect(prompt="", system="", max_tokens=4096, temperature=0.3):
            text = prompt.lower()
            if "evaluate" in text and "fct" in text:
                return _mock_llm_response(json.dumps({
                    "overall_score": 8.0, "decision": "accept",
                    "criterion_scores": [
                        {"criterion": "A", "sub_criterion": "A1", "score": 8.0,
                         "strengths": ["Good"], "weaknesses": [], "suggestions": []},
                    ],
                    "general_comments": "Good.", "major_revisions": [], "minor_revisions": [],
                }))
            if "synthesise" in text or "consensus" in text:
                return _mock_llm_response("Consensus.")
            if "task" in text and "json" in text:
                return _mock_llm_response(json.dumps([{
                    "number": 1, "denomination": "Task",
                    "description": "Desc.", "person_months": 4.0,
                    "start_month": 1, "duration_months": 8,
                }]))
            for section, limit in [
                ("abstract", CHAR_LIMITS.abstract_en),
                ("state_of_art", CHAR_LIMITS.state_of_art_objectives),
                ("research_plan", CHAR_LIMITS.research_plan_methods),
            ]:
                if section in text:
                    return _mock_llm_response(_build_section_text(section, limit))
            return _mock_llm_response("Content." * 20)

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(side_effect=_side_effect)
        mock_llm.generate_json = AsyncMock(side_effect=_side_effect)

        from src.generators.models import DraftIdea
        from unittest.mock import MagicMock
        import yaml

        draft_path = Path("drafts/example_idea.yaml")
        data = yaml.safe_load(draft_path.read_text())
        draft = DraftIdea(**data)

        mock_scopus = MagicMock()
        mock_scopus.is_available = False
        generator = ProposalGenerator(llm=mock_llm, scopus=mock_scopus)
        panel = ReviewPanel.__new__(ReviewPanel)
        panel.consensus_llm = mock_llm
        panel.reviewers = []
        reviser = RevisionEngine(llm=mock_llm)

        pipeline = Pipeline(generator=generator, panel=panel, reviser=reviser)

        with patch("src.generators.pipeline.cfg") as mock_cfg:
            mock_cfg.iterations = 1
            mock_cfg.stop_on_accept = True
            mock_cfg.save_intermediates = False
            mock_cfg.out_json = False
            mock_cfg.out_markdown = False
            mock_cfg.out_char_report = False
            mock_cfg.out_docx = False
            mock_cfg.output_dir = str(tmp_path)
            mock_cfg.review_iterate_enabled = False

            result = await pipeline.run(draft, iterations=1, output_dir=tmp_path)

        assert "improvement_reports" in result
        assert result["improvement_reports"] == []
        assert pipeline.review_iterate is None


# =============================================================================
# Tests: LLM Pricing
# =============================================================================

class TestLLMPricing:

    def test_known_model_pricing(self):
        from src.config.llm_pricing import get_pricing
        # Full model ID should match by prefix
        inp, out = get_pricing("claude-opus-4-20250514")
        assert inp == 15.0
        assert out == 75.0

    def test_unknown_model_fallback(self):
        from src.config.llm_pricing import get_pricing, DEFAULT_PRICING
        result = get_pricing("some-unknown-model-xyz")
        assert result == DEFAULT_PRICING

    def test_estimate_cost_basic(self):
        from src.config.llm_pricing import estimate_cost
        # 1000 input + 500 output at claude-opus-4 prices (15/75 per 1M)
        cost = estimate_cost("claude-opus-4-20250514", 1000, 500)
        expected = (1000 * 15.0 + 500 * 75.0) / 1_000_000
        assert abs(cost - expected) < 1e-10

    def test_longest_prefix_wins(self):
        from src.config.llm_pricing import get_pricing
        # "gpt-4o-mini" should match "gpt-4o-mini" (0.15/0.60), not "gpt-4o" (2.50/10.0)
        inp, out = get_pricing("gpt-4o-mini-2024-07-18")
        assert inp == 0.15
        assert out == 0.60

    def test_estimate_cost_zero_tokens(self):
        from src.config.llm_pricing import estimate_cost
        cost = estimate_cost("claude-opus-4", 0, 0)
        assert cost == 0.0


# =============================================================================
# Tests: CostTracker
# =============================================================================

class TestCostTracker:

    def test_record_and_summarize(self):
        from src.reviewers.review_iterate import CostTracker

        tracker = CostTracker()

        # Simulate 3 LLM responses
        resp1 = LLMResponse(
            text="atomized", model="claude-opus-4-20250514",
            provider=LLMProvider.ANTHROPIC, input_tokens=5000, output_tokens=1000,
        )
        resp2 = LLMResponse(
            text="revised", model="claude-opus-4-20250514",
            provider=LLMProvider.ANTHROPIC, input_tokens=8000, output_tokens=2000,
        )
        resp3 = LLMResponse(
            text="narrative", model="gpt-4o-mini-2024",
            provider=LLMProvider.OPENAI, input_tokens=3000, output_tokens=500,
        )

        tracker.record(resp1, call_id="atomize", step="atomize")
        tracker.record(resp2, call_id="revise_state_of_art", step="revise")
        tracker.record(resp3, call_id="narrative", step="narrative")

        summary = tracker.summarize()

        assert summary.total_input_tokens == 16000
        assert summary.total_output_tokens == 3500
        assert summary.total_tokens == 19500
        assert len(summary.calls) == 3
        assert summary.total_cost_usd > 0

        # by_step has 3 entries
        assert "atomize" in summary.by_step
        assert "revise" in summary.by_step
        assert "narrative" in summary.by_step

        # by_model has 2 entries (two different models)
        assert "claude-opus-4-20250514" in summary.by_model
        assert "gpt-4o-mini-2024" in summary.by_model

    def test_empty_tracker(self):
        from src.reviewers.review_iterate import CostTracker

        tracker = CostTracker()
        summary = tracker.summarize()

        assert summary.total_input_tokens == 0
        assert summary.total_output_tokens == 0
        assert summary.total_tokens == 0
        assert summary.total_cost_usd == 0.0
        assert summary.calls == []
        assert summary.by_step == {}
        assert summary.by_model == {}


# =============================================================================
# Tests: Cost Report Markdown
# =============================================================================

class TestCostReportMarkdown:

    def test_cost_report_has_all_sections(self):
        from src.utils.txt_formatter import cost_report_to_md

        summary = CostSummary(
            total_input_tokens=10000,
            total_output_tokens=2000,
            total_tokens=12000,
            total_cost_usd=0.225,
            calls=[
                LLMCallRecord(
                    call_id="atomize", step="atomize",
                    model="claude-opus-4-20250514", provider="anthropic",
                    input_tokens=5000, output_tokens=1000, total_tokens=6000,
                    cost_usd=0.15, timestamp="2026-03-01T00:00:00Z",
                ),
                LLMCallRecord(
                    call_id="revise_abstract_en", step="revise",
                    model="claude-opus-4-20250514", provider="anthropic",
                    input_tokens=5000, output_tokens=1000, total_tokens=6000,
                    cost_usd=0.075, timestamp="2026-03-01T00:01:00Z",
                ),
            ],
            by_step={"atomize": 0.15, "revise": 0.075},
            by_model={"claude-opus-4-20250514": 0.225},
        )

        md = cost_report_to_md(summary, version=1)

        assert "# LLM Traffic & Cost Report" in md
        assert "## Summary" in md
        assert "## Per-Call Detail" in md
        assert "## Aggregation by Step" in md
        assert "## Aggregation by Model" in md
        assert "## Pricing Table Used" in md
        assert "atomize" in md
        assert "claude-opus-4-20250514" in md
        assert "$0.2250" in md


# =============================================================================
# Tests: Improvement Report Section 13
# =============================================================================

class TestImprovementReportCostSection:

    def test_section_13_appears_in_md(self):
        from src.utils.txt_formatter import improvement_report_to_md

        report = ImprovementReport(
            version=1,
            timestamp="2026-03-01T00:00:00Z",
            readiness_index=80.0,
            stoplight=[
                StoplightEntry(criterion="A", color="green"),
                StoplightEntry(criterion="B", color="green"),
                StoplightEntry(criterion="C", color="green"),
                StoplightEntry(criterion="E", color="green"),
            ],
            cost_summary=CostSummary(
                total_input_tokens=10000,
                total_output_tokens=2000,
                total_tokens=12000,
                total_cost_usd=0.225,
                by_step={"atomize": 0.15, "revise": 0.075},
                by_model={"claude-opus-4": 0.225},
            ),
        )

        md = improvement_report_to_md(report, version=1)

        assert "## 13. LLM Usage & Cost Summary" in md
        assert "12,000" in md  # total tokens formatted
        assert "$0.2250" in md
        assert "| atomize |" in md
        assert "| revise |" in md
        assert "| claude-opus-4 |" in md

    def test_section_13_absent_when_no_cost_summary(self):
        from src.utils.txt_formatter import improvement_report_to_md

        report = ImprovementReport(
            version=1,
            timestamp="2026-03-01T00:00:00Z",
            readiness_index=80.0,
        )

        md = improvement_report_to_md(report, version=1)
        assert "## 13." not in md

    @pytest.mark.asyncio
    async def test_cost_files_saved_by_save_artifacts(self, tmp_path):
        from src.reviewers.review_iterate import ReviewIterateEngine

        mock_suggestions = json.dumps([{
            "id": "SUG-001", "source_reviewer": "mock",
            "source_text": "Weak.", "issue": "Methodology gaps",
            "recommended_fix": "Add framework",
            "criterion_tags": ["A1"],
            "target_sections": ["state_of_art_objectives"],
            "severity": "S2", "evidence_status": "E1",
            "confidence": "C1", "effort": "F1",
            "impact": "I2", "dependency": "D0",
            "actionability": "A2",
            "acceptance_test": "Framework present",
            "depends_on": [], "blocks": [],
        }])

        mock_consistency = json.dumps([
            {"check_name": "country_set_consistent", "passed": True, "details": "OK"},
        ])

        mock_narrative = json.dumps({
            "executive_summary": "Summary.",
            "science_method_changes": "Changes.",
            "feasibility_budget_changes": "Budget.",
            "ethics_compliance_changes": "Ethics.",
            "risk_register": "| # | Risk |\n|---|------|\n| 1 | None |",
        })

        async def _side_effect(prompt="", system="", max_tokens=4096, temperature=0.3):
            text = prompt.lower()
            if "grading rubric" in text or "atomize" in text:
                return LLMResponse(
                    text=mock_suggestions, model="claude-opus-4-20250514",
                    provider=LLMProvider.ANTHROPIC,
                    input_tokens=5000, output_tokens=1000,
                )
            if "consistency" in text and "auditor" in text:
                return LLMResponse(
                    text=mock_consistency, model="claude-opus-4-20250514",
                    provider=LLMProvider.ANTHROPIC,
                    input_tokens=4000, output_tokens=800,
                )
            if "improvement report" in text or "narrative" in text:
                return LLMResponse(
                    text=mock_narrative, model="claude-opus-4-20250514",
                    provider=LLMProvider.ANTHROPIC,
                    input_tokens=3000, output_tokens=600,
                )
            return LLMResponse(
                text="Revised section text with improvements." * 50,
                model="claude-opus-4-20250514",
                provider=LLMProvider.ANTHROPIC,
                input_tokens=6000, output_tokens=1500,
            )

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(side_effect=_side_effect)

        with patch("src.reviewers.review_iterate.cfg") as mock_cfg:
            mock_cfg.review_iterate_top_n = 5
            mock_cfg.review_iterate_max_suggestions = 20
            mock_cfg.review_iterate_include_trivial = True
            mock_cfg.review_iterate_consistency_checks = [
                "budget_totals_reconcile", "timeline_ethics_gate",
            ]
            mock_cfg.revision.temperature = 0.3

            engine = ReviewIterateEngine(llm=mock_llm)
            proposal = _make_proposal()
            consensus = _make_consensus()
            draft = _make_draft()

            revised, report = await engine.revise(
                proposal, consensus, version=1,
                draft=draft, output_dir=tmp_path,
            )

        # Verify cost summary is populated
        assert report.cost_summary is not None
        assert report.cost_summary.total_tokens > 0
        assert report.cost_summary.total_cost_usd > 0
        assert len(report.llm_call_log) > 0

        # Verify cost report files were written
        assert (tmp_path / "llm_cost_report_v1.json").exists()
        assert (tmp_path / "llm_cost_report_v1.md").exists()

        # Verify JSON content is valid
        cost_json = json.loads((tmp_path / "llm_cost_report_v1.json").read_text())
        assert "total_cost_usd" in cost_json
        assert cost_json["total_tokens"] > 0

        # Verify MD has expected sections
        cost_md = (tmp_path / "llm_cost_report_v1.md").read_text()
        assert "## Summary" in cost_md
        assert "## Per-Call Detail" in cost_md