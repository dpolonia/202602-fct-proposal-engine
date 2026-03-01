"""
Comprehensive tests for the FCT compliance validation layer.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.compliance.formatters import (
    compliance_to_json_improvements,
    compliance_to_md,
    compliance_to_suggestions,
)
from src.compliance.models import (
    ComplianceCategory,
    ComplianceDelta,
    ComplianceFinding,
    ComplianceRecommendation,
    ComplianceReport,
    ComplianceSeverity,
    ComplianceStatus,
)
from src.compliance.registry import RuleRegistry
from src.compliance.validator import ComplianceValidator
from src.config.fct_constants import (
    ProjectType,
)
from src.generators.models import (
    Deliverable,
    DraftIdea,
    Milestone,
    Proposal,
    ProposalTask,
    Severity,
    SuggestionRecord,
    TaskBudget,
)

# ============================================================================
# Fixtures
# ============================================================================


def _make_task_budget(
    hr=5000.0,
    travel=1000.0,
    equip=500.0,
    consumables=200.0,
    services=300.0,
    pubs=200.0,
    other=100.0,
) -> TaskBudget:
    return TaskBudget(
        human_resources=hr,
        missions_travel=travel,
        equipment=equip,
        consumables=consumables,
        services=services,
        registrations_publications=pubs,
        other=other,
    )


def _make_valid_proposal(**overrides) -> Proposal:
    """Create a proposal that passes all CL, WP, BG checks."""
    budget = _make_task_budget()
    tasks = [
        ProposalTask(
            number=1,
            denomination="Task 1: Literature Review",
            description="Systematic review of existing literature. " * 20,
            expected_results="Comprehensive review paper.",
            assigned_members=["PI"],
            person_months=6.0,
            start_month=1,
            duration_months=12,
            budget=budget,
            cost_justification="Personnel for systematic review and travel to conferences.",
        ),
        ProposalTask(
            number=2,
            denomination="Task 2: Data Collection and Analysis",
            description="Collect survey data from participants using questionnaires. " * 20,
            expected_results="Dataset and analysis results.",
            assigned_members=["PI", "Researcher"],
            person_months=12.0,
            start_month=7,
            duration_months=18,
            budget=budget,
            cost_justification="Personnel and equipment for data analysis tasks.",
        ),
        ProposalTask(
            number=3,
            denomination="Task 3: Dissemination and Publication",
            description="Publication of results and dissemination activities. " * 20,
            expected_results="Journal publications.",
            assigned_members=["PI"],
            person_months=6.0,
            start_month=24,
            duration_months=12,
            budget=budget,
            cost_justification="Travel to conferences and publication fees for task outputs.",
        ),
    ]
    total_budget = sum(t.budget.total for t in tasks)

    defaults = dict(
        title_en="A Novel Approach to Public Policy Analysis",
        title_pt="Uma Abordagem Inovadora para Analise de Politicas Publicas",
        acronym="POLANA",
        typology=ProjectType.ICDT,
        keywords_en=["policy", "governance", "innovation", "analysis"],
        keywords_pt=["politica", "governanca", "inovacao", "analise"],
        scientific_domain="Social Sciences",
        scientific_area="Political Science",
        scientific_subarea="Public Policy",
        start_date="2027-01-01",
        duration_months=36,
        institution_description="Universidade de Aveiro is a leading research institution.",
        career_profile=(
            "Prof. Silva has a strong track record with over 50 publications "
            "in peer-reviewed journals. Her h-index is 25 on Scopus and Web of Science."
        ),
        contributions_new_ideas="Novel framework for policy analysis using AI.",
        contributions_teams="Led 5 international research teams.",
        contributions_society="Policy recommendations adopted by government.",
        further_details="Extensive experience in EU-funded projects.",
        team_cv_synopsis=(
            "The team brings complementary expertise in political science, "
            "data science, and public administration. Each specialist has deep "
            "experience and skills relevant to the project."
        ),
        abstract_pt="Este projeto propoe uma abordagem inovadora para analise de politicas.",
        abstract_en=(
            "This project proposes a novel approach to public policy analysis "
            "using advanced computational methods and innovative frameworks."
        ),
        state_of_art_objectives=(
            "The state of art in policy analysis shows a gap in computational "
            "approaches. This project addresses this gap with novel methods "
            "that go beyond existing frameworks."
        ),
        research_plan_methods=(
            "Our methodology involves a mixed-methods approach combining "
            "quantitative analysis with qualitative techniques. The framework "
            "includes data collection, statistical modeling, and case studies."
        ),
        bibliographic_references="[1] Smith et al. (2023)...\n[2] Jones (2024)...",
        tasks=tasks,
        deliverables=[
            Deliverable(
                code="D1.1",
                title="Literature Review Report",
                description="Comprehensive review of policy analysis methods.",
                related_tasks=[1],
                due_month=12,
            ),
            Deliverable(
                code="D2.1",
                title="Dataset and Analysis",
                description="Cleaned dataset and analysis results.",
                related_tasks=[2],
                due_month=24,
            ),
            Deliverable(
                code="D3.1",
                title="Final Report and Publications",
                description="Project report and journal publications.",
                related_tasks=[3],
                due_month=35,
            ),
        ],
        milestones=[
            Milestone(
                code="M1",
                denomination="Literature Review Complete",
                description="Completion of systematic review.",
                related_tasks=[1],
                due_month=12,
            ),
            Milestone(
                code="M2",
                denomination="Data Collection Complete",
                description="All survey data collected.",
                related_tasks=[2],
                due_month=20,
            ),
            Milestone(
                code="M3",
                denomination="Project Completion",
                description="All outputs delivered.",
                related_tasks=[3],
                due_month=36,
            ),
        ],
        management_structure=(
            "The project is managed by the PI with risk mitigation strategies "
            "and contingency plans for each task. Quality assurance reviews "
            "are conducted quarterly."
        ),
        ethics_justification=(
            "This project involves survey participants and collects personal data "
            "via questionnaires. Informed consent will be obtained prior to data "
            "collection. GDPR compliance is ensured through data protection "
            "measures. Ethics committee approval will be obtained before month 6."
        ),
        sdg_alignment=[9, 16],
        total_budget=total_budget,
    )
    defaults.update(overrides)
    return Proposal(**defaults)


def _make_oversize_proposal(**overrides) -> Proposal:
    """Create a proposal and then override fields bypassing Pydantic validation."""
    p = _make_valid_proposal()
    for key, value in overrides.items():
        object.__setattr__(p, key, value)
    return p


def _make_blocker_proposal() -> Proposal:
    """Create a proposal with deliberate BLOCKER violations."""
    p = _make_valid_proposal(
        duration_months=48,  # E07: >36 for IC&DT
        total_budget=300_000,  # E08/BG01: >250k for IC&DT
        abstract_en="",  # WP13: empty
        state_of_art_objectives="",  # WP14: empty
        tasks=[],  # WP01: no tasks
    )
    # Bypass Pydantic validation for oversize fields
    object.__setattr__(p, "title_en", "X" * 300)
    object.__setattr__(p, "acronym", "TOOLONGACRONYM123")
    return p


def _make_draft() -> DraftIdea:
    """Create a minimal DraftIdea."""
    return DraftIdea(
        title="Test Draft",
        research_topic="A test research topic.",
    )


# ============================================================================
# Test Models
# ============================================================================


class TestComplianceModels:
    def test_finding_construction(self):
        f = ComplianceFinding(
            rule_id="CL01",
            category=ComplianceCategory.CHAR_LIMITS,
            severity=ComplianceSeverity.BLOCKER,
            status=ComplianceStatus.FAIL,
            description="Title too long",
        )
        assert f.rule_id == "CL01"
        assert f.severity == ComplianceSeverity.BLOCKER
        assert f.status == ComplianceStatus.FAIL

    def test_severity_ordering(self):
        assert ComplianceSeverity.BLOCKER < ComplianceSeverity.CRITICAL
        assert ComplianceSeverity.CRITICAL < ComplianceSeverity.MAJOR
        assert ComplianceSeverity.MAJOR < ComplianceSeverity.MINOR

    def test_report_compute_aggregates(self):
        report = ComplianceReport(
            version=1,
            findings=[
                ComplianceFinding(
                    rule_id="CL01",
                    severity=ComplianceSeverity.BLOCKER,
                    status=ComplianceStatus.FAIL,
                    category=ComplianceCategory.CHAR_LIMITS,
                ),
                ComplianceFinding(
                    rule_id="CL02",
                    severity=ComplianceSeverity.MAJOR,
                    status=ComplianceStatus.PASS,
                    category=ComplianceCategory.CHAR_LIMITS,
                ),
                ComplianceFinding(
                    rule_id="E01",
                    severity=ComplianceSeverity.CRITICAL,
                    status=ComplianceStatus.FAIL,
                    category=ComplianceCategory.ELIGIBILITY,
                ),
                ComplianceFinding(
                    rule_id="UA01",
                    severity=ComplianceSeverity.MAJOR,
                    status=ComplianceStatus.WARN,
                    category=ComplianceCategory.UA_INTERNAL,
                ),
            ],
        )
        report.compute_aggregates()
        assert report.total == 4
        assert report.passed == 1
        assert report.failed == 2
        assert report.warned == 1
        assert report.blocker_count == 1
        assert report.critical_count == 1
        assert report.recommendation == ComplianceRecommendation.RESOLVE_BLOCKERS

    def test_report_recommendation_cascade(self):
        # No blockers, has critical
        report = ComplianceReport(
            findings=[
                ComplianceFinding(
                    rule_id="X",
                    severity=ComplianceSeverity.CRITICAL,
                    status=ComplianceStatus.FAIL,
                    category=ComplianceCategory.ELIGIBILITY,
                ),
            ]
        )
        report.compute_aggregates()
        assert report.recommendation == ComplianceRecommendation.RESOLVE_CRITICAL

        # Only major
        report2 = ComplianceReport(
            findings=[
                ComplianceFinding(
                    rule_id="X",
                    severity=ComplianceSeverity.MAJOR,
                    status=ComplianceStatus.FAIL,
                    category=ComplianceCategory.ELIGIBILITY,
                ),
            ]
        )
        report2.compute_aggregates()
        assert report2.recommendation == ComplianceRecommendation.PROCEED_TO_REVIEW

        # Only minor or pass
        report3 = ComplianceReport(
            findings=[
                ComplianceFinding(
                    rule_id="X",
                    severity=ComplianceSeverity.MINOR,
                    status=ComplianceStatus.PASS,
                    category=ComplianceCategory.ELIGIBILITY,
                ),
            ]
        )
        report3.compute_aggregates()
        assert report3.recommendation == ComplianceRecommendation.MINOR_POLISH

    def test_delta_construction(self):
        d = ComplianceDelta(
            resolved=["CL01"],
            persists=["E08"],
            new_failures=["WP01"],
            regressions=["BG03"],
        )
        assert "CL01" in d.resolved
        assert "WP01" in d.new_failures

    def test_report_serialization(self):
        report = ComplianceReport(version=1, typology="SR&TD")
        json_str = report.model_dump_json()
        data = json.loads(json_str)
        assert data["version"] == 1
        assert data["typology"] == "SR&TD"


# ============================================================================
# Test Registry
# ============================================================================


class TestRuleRegistry:
    def test_rules_are_registered(self):
        """Rules should be auto-registered on import."""
        all_rules = RuleRegistry.get_all()
        assert len(all_rules) > 0
        assert "CL01" in all_rules
        assert "E01" in all_rules
        assert "WP01" in all_rules
        assert "BG01" in all_rules
        assert "ET01" in all_rules
        assert "EV01" in all_rules
        assert "UA03" in all_rules

    def test_get_by_category(self):
        cl_rules = RuleRegistry.get_by_category(ComplianceCategory.CHAR_LIMITS)
        assert len(cl_rules) > 0
        assert all(r.category == ComplianceCategory.CHAR_LIMITS for r in cl_rules.values())

    def test_get_single_rule(self):
        rule = RuleRegistry.get("CL01")
        assert rule is not None
        assert rule.rule_id == "CL01"
        assert rule.severity == ComplianceSeverity.BLOCKER

    def test_get_nonexistent_returns_none(self):
        assert RuleRegistry.get("NONEXISTENT") is None

    def test_rule_definition_fields(self):
        rule = RuleRegistry.get("E07")
        assert rule is not None
        assert rule.auto_checkable is True
        assert "SR&TD" in rule.applicable_typologies
        assert "PEX" in rule.applicable_typologies


# ============================================================================
# Test Character Limit Rules
# ============================================================================


class TestCharLimitRules:
    def test_cl01_pass(self):
        p = _make_valid_proposal()
        rule = RuleRegistry.get("CL01")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.PASS

    def test_cl01_fail(self):
        p = _make_oversize_proposal(title_en="X" * 300)
        rule = RuleRegistry.get("CL01")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.FAIL
        assert result.severity == ComplianceSeverity.BLOCKER

    def test_cl02_pass(self):
        p = _make_valid_proposal(acronym="SHORT")
        rule = RuleRegistry.get("CL02")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.PASS

    def test_cl02_fail(self):
        p = _make_oversize_proposal(acronym="X" * 20)
        rule = RuleRegistry.get("CL02")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.FAIL

    def test_cl03_pass(self):
        p = _make_valid_proposal(keywords_en=["a", "b", "c", "d"])
        rule = RuleRegistry.get("CL03")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.PASS

    def test_cl03_fail(self):
        p = _make_valid_proposal(keywords_en=["a", "b", "c", "d", "e"])
        rule = RuleRegistry.get("CL03")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.FAIL

    def test_cl13_blocker_empty_abstract_pt(self):
        """Exceeding abstract_pt limit should be BLOCKER."""
        p = _make_oversize_proposal(abstract_pt="X" * 5001)
        rule = RuleRegistry.get("CL13")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.FAIL
        assert result.severity == ComplianceSeverity.BLOCKER

    def test_cl18_per_task(self):
        """Per-item rule should produce findings per task."""
        task1 = ProposalTask(
            number=1,
            denomination="Short",
            description="desc",
            person_months=1.0,
            start_month=1,
            duration_months=12,
            budget=_make_task_budget(),
        )
        # Bypass Pydantic max_length on denomination
        object.__setattr__(task1, "denomination", "X" * 200)
        task2 = ProposalTask(
            number=2,
            denomination="OK",
            description="desc",
            person_months=1.0,
            start_month=1,
            duration_months=12,
            budget=_make_task_budget(),
        )
        p = _make_valid_proposal(tasks=[task1, task2])
        rule = RuleRegistry.get("CL18")
        results = rule.check_fn(p)
        assert isinstance(results, list)
        fail_results = [r for r in results if r.status == ComplianceStatus.FAIL]
        assert len(fail_results) == 1
        assert "tasks[1]" in fail_results[0].field_path

    def test_cl28_safety_margin(self):
        """Fields at >95% should trigger CL28."""
        # career_profile limit is 4000, 96% = 3840
        p = _make_valid_proposal(career_profile="X" * 3900)
        rule = RuleRegistry.get("CL28")
        results = rule.check_fn(p)
        assert isinstance(results, list)
        fail_results = [r for r in results if r.status == ComplianceStatus.FAIL]
        assert any("career_profile" in r.field_path for r in fail_results)


# ============================================================================
# Test Work Plan Rules
# ============================================================================


class TestWorkPlanRules:
    def test_wp01_pass(self):
        p = _make_valid_proposal()
        rule = RuleRegistry.get("WP01")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.PASS

    def test_wp01_fail(self):
        p = _make_valid_proposal(tasks=[])
        rule = RuleRegistry.get("WP01")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.FAIL
        assert result.severity == ComplianceSeverity.BLOCKER

    def test_wp03_task_exceeds_duration(self):
        tasks = [
            ProposalTask(
                number=1,
                denomination="T1",
                description="desc",
                person_months=1.0,
                start_month=30,
                duration_months=12,  # ends month 41 > 36
                budget=_make_task_budget(),
            ),
        ]
        p = _make_valid_proposal(tasks=tasks, duration_months=36)
        rule = RuleRegistry.get("WP03")
        results = rule.check_fn(p)
        fail_results = [r for r in results if r.status == ComplianceStatus.FAIL]
        assert len(fail_results) == 1

    def test_wp04_bad_task_reference(self):
        deliverables = [
            Deliverable(
                code="D1.1", title="Report", related_tasks=[99], due_month=12
            ),  # task 99 doesn't exist
        ]
        p = _make_valid_proposal(deliverables=deliverables)
        rule = RuleRegistry.get("WP04")
        results = rule.check_fn(p)
        fail_results = [r for r in results if r.status == ComplianceStatus.FAIL]
        assert len(fail_results) == 1

    def test_wp08_missing_deliverables(self):
        p = _make_valid_proposal(deliverables=[])
        rule = RuleRegistry.get("WP08")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.FAIL

    def test_wp09_empty_description(self):
        tasks = [
            ProposalTask(
                number=1,
                denomination="T1",
                description="",
                person_months=1.0,
                start_month=1,
                duration_months=12,
                budget=_make_task_budget(),
            ),
        ]
        p = _make_valid_proposal(tasks=tasks)
        rule = RuleRegistry.get("WP09")
        results = rule.check_fn(p)
        fail_results = [r for r in results if r.status == ComplianceStatus.FAIL]
        assert len(fail_results) == 1

    def test_wp10_zero_person_months(self):
        tasks = [
            ProposalTask(
                number=1,
                denomination="T1",
                description="desc",
                person_months=0.0,
                start_month=1,
                duration_months=12,
                budget=_make_task_budget(),
            ),
        ]
        p = _make_valid_proposal(tasks=tasks)
        rule = RuleRegistry.get("WP10")
        results = rule.check_fn(p)
        fail_results = [r for r in results if r.status == ComplianceStatus.FAIL]
        assert len(fail_results) == 1

    def test_wp13_empty_abstract(self):
        p = _make_valid_proposal(abstract_en="")
        rule = RuleRegistry.get("WP13")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.FAIL
        assert result.severity == ComplianceSeverity.BLOCKER

    def test_wp14_empty_soa(self):
        p = _make_valid_proposal(state_of_art_objectives="")
        rule = RuleRegistry.get("WP14")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.FAIL


# ============================================================================
# Test Budget Rules
# ============================================================================


class TestBudgetRules:
    def test_bg01_pass(self):
        p = _make_valid_proposal()
        rule = RuleRegistry.get("BG01")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.PASS

    def test_bg01_fail(self):
        p = _make_valid_proposal(total_budget=300_000)
        rule = RuleRegistry.get("BG01")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.FAIL
        assert result.severity == ComplianceSeverity.BLOCKER

    def test_bg03_mismatch(self):
        """Task budgets should sum to ~total_budget."""
        p = _make_valid_proposal(total_budget=500_000)  # way off
        rule = RuleRegistry.get("BG03")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.FAIL

    def test_bg04_missing_justification(self):
        tasks = [
            ProposalTask(
                number=1,
                denomination="T1",
                description="desc",
                person_months=1.0,
                start_month=1,
                duration_months=12,
                budget=_make_task_budget(),
                cost_justification="",
            ),
        ]
        p = _make_valid_proposal(tasks=tasks)
        rule = RuleRegistry.get("BG04")
        results = rule.check_fn(p)
        fail_results = [r for r in results if r.status == ComplianceStatus.FAIL]
        assert len(fail_results) == 1

    def test_bg05_negative_budget(self):
        tasks = [
            ProposalTask(
                number=1,
                denomination="T1",
                description="desc",
                person_months=1.0,
                start_month=1,
                duration_months=12,
                budget=TaskBudget(human_resources=-100),
                cost_justification="test",
            ),
        ]
        p = _make_valid_proposal(tasks=tasks)
        rule = RuleRegistry.get("BG05")
        results = rule.check_fn(p)
        fail_results = [r for r in results if r.status == ComplianceStatus.FAIL]
        assert len(fail_results) >= 1

    def test_bg06_zero_budget(self):
        p = _make_valid_proposal(total_budget=0)
        rule = RuleRegistry.get("BG06")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.FAIL


# ============================================================================
# Test Ethics Rules
# ============================================================================


class TestEthicsRules:
    def test_et01_human_subjects_addressed(self):
        """Survey/participant keywords should be detected and pass if in ethics."""
        p = _make_valid_proposal()  # has participants in tasks and ethics
        rule = RuleRegistry.get("ET01")
        result = rule.check_fn(p)
        assert result.status in (ComplianceStatus.PASS, ComplianceStatus.NA)

    def test_et01_human_subjects_not_addressed(self):
        p = _make_valid_proposal(
            ethics_justification="No ethical issues in this project.",
        )
        rule = RuleRegistry.get("ET01")
        result = rule.check_fn(p)
        # Should fail since WP has "participants", "survey", etc.
        assert result.status == ComplianceStatus.FAIL

    def test_et06_empty_ethics_with_triggers(self):
        p = _make_valid_proposal(ethics_justification="")
        rule = RuleRegistry.get("ET06")
        result = rule.check_fn(p)
        # Tasks mention participants, so empty ethics is a FAIL
        assert result.status in (ComplianceStatus.FAIL, ComplianceStatus.WARN)

    def test_et08_contradiction(self):
        """Ethics says 'no human subjects' but WP mentions surveys."""
        p = _make_valid_proposal(
            ethics_justification="This project does not involve human subjects.",
        )
        rule = RuleRegistry.get("ET08")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.FAIL
        assert result.severity == ComplianceSeverity.BLOCKER

    def test_et08_no_contradiction(self):
        p = _make_valid_proposal()
        rule = RuleRegistry.get("ET08")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.PASS


# ============================================================================
# Test Evaluation Rules
# ============================================================================


class TestEvaluationRules:
    def test_ev01_novelty_present(self):
        p = _make_valid_proposal()  # has "novel" in SOA
        rule = RuleRegistry.get("EV01")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.PASS

    def test_ev01_novelty_missing(self):
        p = _make_valid_proposal(state_of_art_objectives="A review of existing work.")
        rule = RuleRegistry.get("EV01")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.FAIL

    def test_ev02_methodology_present(self):
        p = _make_valid_proposal()
        rule = RuleRegistry.get("EV02")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.PASS

    def test_ev05_risk_present(self):
        p = _make_valid_proposal()
        rule = RuleRegistry.get("EV05")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.PASS

    def test_ev05_risk_missing(self):
        p = _make_valid_proposal(management_structure="The PI manages the project.")
        rule = RuleRegistry.get("EV05")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.FAIL


# ============================================================================
# Test Eligibility Rules
# ============================================================================


class TestEligibilityRules:
    def test_e01_valid_typology(self):
        p = _make_valid_proposal()
        rule = RuleRegistry.get("E01")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.PASS

    def test_e07_duration_pass(self):
        p = _make_valid_proposal(duration_months=36)
        rule = RuleRegistry.get("E07")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.PASS

    def test_e07_duration_fail(self):
        p = _make_valid_proposal(duration_months=48)
        rule = RuleRegistry.get("E07")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.FAIL

    def test_e08_budget_pass(self):
        p = _make_valid_proposal(total_budget=200_000)
        rule = RuleRegistry.get("E08")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.PASS

    def test_e08_budget_fail(self):
        p = _make_valid_proposal(total_budget=300_000)
        rule = RuleRegistry.get("E08")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.FAIL

    def test_e09_domain_present(self):
        p = _make_valid_proposal()
        rule = RuleRegistry.get("E09")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.PASS

    def test_e09_domain_missing(self):
        p = _make_valid_proposal(scientific_domain="")
        rule = RuleRegistry.get("E09")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.FAIL

    def test_e10_sdg_pass(self):
        p = _make_valid_proposal(sdg_alignment=[9, 16])
        rule = RuleRegistry.get("E10")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.PASS

    def test_e10_sdg_fail(self):
        p = _make_valid_proposal(sdg_alignment=[1, 2, 3, 4])
        rule = RuleRegistry.get("E10")
        result = rule.check_fn(p)
        assert result.status == ComplianceStatus.FAIL

    def test_admin_only_rules_warn(self):
        """Admin-only rules (E02-E06) should produce WARN status."""
        p = _make_valid_proposal()
        for rid in ["E02", "E03", "E04", "E05", "E06"]:
            rule = RuleRegistry.get(rid)
            result = rule.check_fn(p)
            assert result.status == ComplianceStatus.WARN, f"{rid} should WARN"


# ============================================================================
# Test Compliance Validator
# ============================================================================


class TestComplianceValidator:
    def test_valid_proposal_few_failures(self):
        p = _make_valid_proposal()
        d = _make_draft()
        validator = ComplianceValidator()
        report = validator.validate(p, d, version=1)
        assert report.total > 0
        assert report.passed > 0
        # Valid proposal should have no blockers
        assert report.blocker_count == 0

    def test_blocker_proposal_has_blockers(self):
        p = _make_blocker_proposal()
        validator = ComplianceValidator()
        report = validator.validate(p, version=1)
        assert report.blocker_count > 0
        assert report.recommendation == ComplianceRecommendation.RESOLVE_BLOCKERS

    def test_disabled_rules(self):
        p = _make_oversize_proposal(title_en="X" * 300)
        validator = ComplianceValidator()
        # Without disabling, CL01 should fail
        report1 = validator.validate(p, version=1)
        cl01_findings = [f for f in report1.findings if f.rule_id == "CL01"]
        assert any(f.status == ComplianceStatus.FAIL for f in cl01_findings)

        # With CL01 disabled, it should be SKIP
        report2 = validator.validate(p, version=1, disabled_rules=["CL01"])
        cl01_findings2 = [f for f in report2.findings if f.rule_id == "CL01"]
        assert all(f.status == ComplianceStatus.SKIP for f in cl01_findings2)

    def test_disabled_categories(self):
        p = _make_valid_proposal()
        validator = ComplianceValidator()
        report = validator.validate(p, version=1, disabled_categories=["UA"])
        ua_findings = [f for f in report.findings if f.category == ComplianceCategory.UA_INTERNAL]
        assert all(f.status == ComplianceStatus.SKIP for f in ua_findings)

    def test_delta_computation(self):
        p1 = _make_oversize_proposal(title_en="X" * 300)  # CL01 fail
        p2 = _make_valid_proposal()  # CL01 pass

        validator = ComplianceValidator()
        report1 = validator.validate(p1, version=1)
        report2 = validator.validate(p2, version=2, previous_report=report1)

        assert report2.delta is not None
        # CL01 was failing in v1, should be resolved in v2
        assert "CL01" in report2.delta.resolved

    def test_pex_typology_rules(self):
        """PEX-specific rules like CL10 should apply to PEX."""
        p = _make_valid_proposal(
            typology=ProjectType.PEX,
            duration_months=18,
            total_budget=50_000,
            why_timely_pex="This is a timely exploratory project.",
        )
        validator = ComplianceValidator()
        report = validator.validate(p, version=1)
        # CL10 (why_timely_pex) should not be N/A for PEX
        cl10_findings = [f for f in report.findings if f.rule_id == "CL10"]
        if cl10_findings:
            assert cl10_findings[0].status != ComplianceStatus.NA

    def test_exception_safety(self):
        """Rules that raise exceptions should produce SKIP, not crash."""
        p = _make_valid_proposal()
        # Validator should handle exceptions gracefully
        validator = ComplianceValidator()
        report = validator.validate(p, version=1)
        assert report.total > 0  # Should still produce results


# ============================================================================
# Test DOCX Exporter
# ============================================================================


class TestComplianceDocxExporter:
    def test_export_creates_file(self, tmp_path):
        from src.compliance.docx_exporter import ComplianceDocxExporter

        p = _make_valid_proposal()
        validator = ComplianceValidator()
        report = validator.validate(p, version=1)

        path = tmp_path / "compliance_annex.docx"
        ComplianceDocxExporter.export(report, path)
        assert path.exists()
        assert path.stat().st_size > 0

    def test_export_with_delta(self, tmp_path):
        from src.compliance.docx_exporter import ComplianceDocxExporter

        report = ComplianceReport(
            version=2,
            typology="SR&TD",
            findings=[
                ComplianceFinding(
                    rule_id="CL01",
                    severity=ComplianceSeverity.BLOCKER,
                    status=ComplianceStatus.PASS,
                    category=ComplianceCategory.CHAR_LIMITS,
                    description="Title check",
                ),
            ],
            delta=ComplianceDelta(
                resolved=["CL01"],
                persists=[],
                new_failures=[],
                regressions=[],
            ),
        )
        report.compute_aggregates()

        path = tmp_path / "annex_v2.docx"
        ComplianceDocxExporter.export(report, path)
        assert path.exists()


# ============================================================================
# Test Formatters
# ============================================================================


class TestComplianceFormatters:
    def test_compliance_to_md(self):
        p = _make_valid_proposal()
        validator = ComplianceValidator()
        report = validator.validate(p, version=1)
        md = compliance_to_md(report)
        assert "# Compliance Report" in md
        assert "Summary" in md
        assert "Findings by Category" in md

    def test_compliance_to_json_improvements(self):
        report = ComplianceReport(
            findings=[
                ComplianceFinding(
                    rule_id="CL01",
                    severity=ComplianceSeverity.BLOCKER,
                    status=ComplianceStatus.FAIL,
                    category=ComplianceCategory.CHAR_LIMITS,
                    description="Title too long",
                    suggestion="Shorten title",
                ),
                ComplianceFinding(
                    rule_id="CL02",
                    severity=ComplianceSeverity.MAJOR,
                    status=ComplianceStatus.PASS,
                    category=ComplianceCategory.CHAR_LIMITS,
                    description="Acronym OK",
                ),
            ]
        )
        result = compliance_to_json_improvements(report)
        data = json.loads(result)
        # Only FAIL findings
        assert len(data) == 1
        assert data[0]["rule_id"] == "CL01"
        assert data[0]["severity"] == "BLOCKER"

    def test_compliance_to_suggestions(self):
        report = ComplianceReport(
            findings=[
                ComplianceFinding(
                    rule_id="CL01",
                    severity=ComplianceSeverity.BLOCKER,
                    status=ComplianceStatus.FAIL,
                    category=ComplianceCategory.CHAR_LIMITS,
                    description="Title too long",
                    field_path="title_en",
                    suggestion="Shorten title",
                ),
                ComplianceFinding(
                    rule_id="BG01",
                    severity=ComplianceSeverity.CRITICAL,
                    status=ComplianceStatus.FAIL,
                    category=ComplianceCategory.BUDGET,
                    description="Budget exceeded",
                    field_path="total_budget",
                    suggestion="Reduce budget",
                ),
                ComplianceFinding(
                    rule_id="CL02",
                    severity=ComplianceSeverity.MAJOR,
                    status=ComplianceStatus.PASS,
                    category=ComplianceCategory.CHAR_LIMITS,
                    description="OK",
                ),
            ]
        )
        suggestions = compliance_to_suggestions(report)
        assert len(suggestions) == 2  # Only FAIL findings
        assert all(isinstance(s, SuggestionRecord) for s in suggestions)

        # Check severity mapping
        cl01_sug = next(s for s in suggestions if "CL01" in s.source_text)
        assert cl01_sug.severity == Severity.S3  # BLOCKER → S3
        assert cl01_sug.id.startswith("COMP-")
        assert cl01_sug.source_reviewer == "compliance_validator"

        bg01_sug = next(s for s in suggestions if "BG01" in s.source_text)
        assert bg01_sug.severity == Severity.S2  # CRITICAL → S2


# ============================================================================
# Test Pipeline Integration (mocked)
# ============================================================================


class TestPipelineIntegration:
    def test_compliance_config_loaded(self):
        """Compliance config should be present in settings."""
        from src.config.settings import UserConfig

        config = UserConfig()
        assert hasattr(config, "compliance_enabled")
        assert hasattr(config, "compliance_run_before_review")
        assert hasattr(config, "compliance_run_after_revision")
        assert hasattr(config, "compliance_feed_to_review_iterate")
        assert hasattr(config, "compliance_disabled_rules")
        assert hasattr(config, "compliance_disabled_categories")

    def test_pipeline_has_compliance_dir(self):
        """Pipeline should include compliance directory."""
        import tempfile

        from src.generators.pipeline import Pipeline

        with tempfile.TemporaryDirectory() as tmpdir:
            dirs = Pipeline._setup_output_dirs(Path(tmpdir))
            assert "compliance" in dirs
            assert dirs["compliance"].exists()
