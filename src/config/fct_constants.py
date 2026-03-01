"""
FCT PTDC 2025 Call — Constants, character limits, evaluation weights, and rules.
Extracted from: Application Guide (republication Dec 2025), Aviso de Abertura,
Regulamento 5/2024, Guide for Peer Reviewers, and UA Internal Rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# =============================================================================
# Project Typologies
# =============================================================================


class ProjectType(StrEnum):
    ICDT = "SR&TD"  # Investigação Científica e Desenvolvimento Tecnológico
    PEX = "PEX"  # Projetos Exploratórios


@dataclass(frozen=True)
class TypologyRules:
    max_duration_months: int
    max_extension_months: int
    max_funding_eur: int
    initial_advance_pct: float
    intermediate_payments: bool
    participating_institutions_allowed: bool
    call_budget_eur: int
    estimated_projects: int


TYPOLOGY_RULES: dict[ProjectType, TypologyRules] = {
    ProjectType.ICDT: TypologyRules(
        max_duration_months=36,
        max_extension_months=12,
        max_funding_eur=250_000,
        initial_advance_pct=0.30,
        intermediate_payments=True,
        participating_institutions_allowed=True,
        call_budget_eur=80_000_000,
        estimated_projects=320,
    ),
    ProjectType.PEX: TypologyRules(
        max_duration_months=18,
        max_extension_months=6,
        max_funding_eur=60_000,
        initial_advance_pct=0.75,
        intermediate_payments=False,
        participating_institutions_allowed=False,
        call_budget_eur=24_000_000,
        estimated_projects=400,
    ),
}


# =============================================================================
# Character Limits (Application Guide Republication Dec 2025)
# =============================================================================


@dataclass(frozen=True)
class CharLimits:
    """All character limits from Annex I of the Application Guide (republished)."""

    # --- General Data ---
    project_title: int = 255
    project_acronym: int = 15
    max_keywords: int = 4

    # --- Institutions ---
    institution_description: int = 1500  # per institution

    # --- PI Narrative CV ---
    career_profile: int = 4000
    contributions_new_ideas: int = 5000
    contributions_teams: int = 3000
    contributions_society: int = 3000
    further_details: int = 5000
    why_timely_pex: int = 3000  # PEX only

    # --- Team ---
    consultant_framework: int = 1000
    team_cv_synopsis: int = 10000

    # --- Work Plan ---
    abstract_pt: int = 5000
    abstract_en: int = 5000
    abstract_publication: int = 5000
    state_of_art_objectives: int = 6000
    research_plan_methods: int = 10000
    bibliographic_references: int = 10000
    past_publication: int = 600  # per publication

    # --- Tasks ---
    task_denomination: int = 150
    task_description: int = 4000
    cost_justification: int = 2500  # per task

    # --- Timeline & Management ---
    deliverable_description: int = 800
    milestone_description: int = 300
    management_structure: int = 3000

    # --- Ethics & Other ---
    ethics_justification: int = 3000
    other_project_relation: int = 2000

    # --- Computing ---
    computational_platforms: int = 400
    computational_justification: int = 400


CHAR_LIMITS = CharLimits()


# =============================================================================
# Evaluation Criteria Weights
# =============================================================================


@dataclass(frozen=True)
class EvalCriteria:
    """Evaluation criteria and weights from Guide for Peer Reviewers."""

    # Criterion A: Scientific merit and innovative nature (40%)
    criterion_a_weight: float = 0.40
    a1_scientific_merit_weight: float = 0.50  # within A
    a2_innovative_nature_weight: float = 0.50  # within A

    # Criterion B: PI and Research Team (30%)
    criterion_b_weight: float = 0.30
    b1_pi_merit_weight: float = 0.60  # within B
    b2_team_merit_weight: float = 0.40  # within B

    # Criterion C: Feasibility (30%)
    criterion_c_weight: float = 0.30

    # Minimum merit threshold
    min_merit_threshold: float = 7.0  # assumed from FCT standard


EVAL_CRITERIA = EvalCriteria()


# =============================================================================
# Budget Rules
# =============================================================================


@dataclass(frozen=True)
class BudgetRules:
    indirect_costs_pct: float = 0.25  # 25% of eligible direct costs
    building_adaptation_max_pct: float = 0.10  # max 10% of total eligible
    ua_minimum_budget_eur: int = 15_000  # UA internal rule


BUDGET_RULES = BudgetRules()


# =============================================================================
# Key Dates
# =============================================================================


@dataclass(frozen=True)
class CallDates:
    call_open: str = "2025-11-27"
    ua_internal_deadline: str = "2026-03-06"
    fct_submission_deadline: str = "2026-03-11T17:00:00+00:00"
    commitment_declaration_deadline: str = "2026-03-25T17:00:00+00:00"
    results_notification: str = "2026-10"  # approximate


CALL_DATES = CallDates()


# =============================================================================
# Deliverable Types (from Application Guide)
# =============================================================================


class DeliverableType(StrEnum):
    REPORT = "Report"
    DATA_MANAGEMENT_PLAN = "Data Management Plan"
    DEMONSTRATOR = "Demonstrator"
    DISSEMINATION = "Dissemination/Communication"
    DATASET = "Dataset"
    OTHER = "Other"


# =============================================================================
# Participation Rules
# =============================================================================


@dataclass(frozen=True)
class ParticipationRules:
    max_pi_applications: int = 1  # only 1 as PI regardless of typology
    max_member_if_pi: int = 1  # if PI, max 1 other as team member
    max_member_if_not_pi: int = 2  # if not PI, max 2 as team member
    max_research_units_per_institution: int = 3
    max_sdgs: int = 3


PARTICIPATION_RULES = ParticipationRules()


# =============================================================================
# Section mapping for the proposal generator
# =============================================================================

PROPOSAL_SECTIONS = [
    "general_data",
    "institutions",
    "pi_narrative_cv",
    "team_cv_synopsis",
    "abstract_pt",
    "abstract_en",
    "state_of_art_objectives",
    "research_plan_methods",
    "bibliographic_references",
    "tasks",
    "deliverables",
    "milestones",
    "management_structure",
    "ethics",
    "sdg_alignment",
    "budget",
]
