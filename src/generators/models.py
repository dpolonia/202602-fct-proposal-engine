"""
Data models for the entire proposal lifecycle:
  DraftIdea → Proposal → Review → RevisedProposal
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from src.config.fct_constants import DeliverableType, ProjectType


# =============================================================================
# Input: Draft Research Idea
# =============================================================================

class TeamMember(BaseModel):
    name: str
    email: str = ""
    institution: str
    role: str = "team_member"  # pi, co_pi, team_member, to_hire, consultant
    expertise: str = ""
    orcid: str = ""


class DraftIdea(BaseModel):
    """The minimal input the PI provides to kick off the proposal generation."""

    # Core idea
    title: str = Field(..., max_length=255, description="Working title (EN)")
    title_pt: str = Field("", max_length=255, description="Working title (PT)")
    acronym: str = Field("", max_length=15)
    typology: ProjectType = ProjectType.ICDT

    # Research framing
    research_topic: str = Field(..., description="1-3 paragraph description of the research idea")
    research_questions: list[str] = Field(default_factory=list, description="Draft research questions")
    keywords_en: list[str] = Field(default_factory=list, max_length=4)
    keywords_pt: list[str] = Field(default_factory=list, max_length=4)
    scientific_domain: str = ""
    scientific_area: str = ""
    scientific_subarea: str = ""

    # Team
    pi: TeamMember | None = None
    team_members: list[TeamMember] = Field(default_factory=list)
    hirings_planned: list[TeamMember] = Field(default_factory=list)

    # Institutions
    principal_contractor: str = "Universidade de Aveiro"
    research_units: list[str] = Field(default_factory=list, max_length=3)
    participating_institutions: list[str] = Field(default_factory=list)
    collaborative_institutions: list[str] = Field(default_factory=list)

    # Optional context
    pi_career_summary: str = ""
    related_publications: list[str] = Field(default_factory=list)
    related_projects: list[str] = Field(default_factory=list)
    methodology_notes: str = ""
    budget_notes: str = ""
    ethical_considerations: str = ""
    sdg_alignment: list[int] = Field(default_factory=list, description="UN SDG numbers (1-17), max 3")

    # Preferences
    target_start_date: str = ""
    duration_months: int = 0  # 0 = use max for typology
    estimated_budget: float = 0.0


# =============================================================================
# Output: Full Proposal
# =============================================================================

class TaskBudget(BaseModel):
    human_resources: float = 0.0
    missions_travel: float = 0.0
    equipment: float = 0.0
    consumables: float = 0.0
    services: float = 0.0
    registrations_publications: float = 0.0
    other: float = 0.0

    @property
    def direct_costs(self) -> float:
        return sum([
            self.human_resources, self.missions_travel, self.equipment,
            self.consumables, self.services, self.registrations_publications, self.other,
        ])

    @property
    def indirect_costs(self) -> float:
        return self.direct_costs * 0.25

    @property
    def total(self) -> float:
        return self.direct_costs + self.indirect_costs


class ProposalTask(BaseModel):
    number: int
    denomination: str = Field(..., max_length=150)
    description: str = Field(..., max_length=4000)
    expected_results: str = ""
    assigned_members: list[str] = Field(default_factory=list)
    person_months: float = 0.0
    start_month: int = 1
    duration_months: int = 6
    budget: TaskBudget = Field(default_factory=TaskBudget)
    cost_justification: str = Field("", max_length=2500)


class Deliverable(BaseModel):
    code: str  # e.g., D1.1
    title: str
    type: DeliverableType = DeliverableType.REPORT
    description: str = Field("", max_length=800)
    related_tasks: list[int] = Field(default_factory=list)
    due_month: int = 0


class Milestone(BaseModel):
    code: str  # e.g., M1
    denomination: str
    description: str = Field("", max_length=300)
    related_tasks: list[int] = Field(default_factory=list)
    due_month: int = 0


class Proposal(BaseModel):
    """Complete FCT PTDC 2025 proposal matching the myFCT form structure."""

    # --- General Data ---
    title_en: str = Field("", max_length=255)
    title_pt: str = Field("", max_length=255)
    acronym: str = Field("", max_length=15)
    typology: ProjectType = ProjectType.ICDT
    keywords_en: list[str] = Field(default_factory=list)
    keywords_pt: list[str] = Field(default_factory=list)
    scientific_domain: str = ""
    scientific_area: str = ""
    scientific_subarea: str = ""
    start_date: str = ""
    duration_months: int = 36

    # --- Institutions ---
    institution_description: str = Field("", max_length=1500)
    participating_institutions_desc: dict[str, str] = Field(default_factory=dict)
    collaborative_institutions_desc: dict[str, str] = Field(default_factory=dict)

    # --- PI Narrative CV ---
    career_profile: str = Field("", max_length=4000)
    contributions_new_ideas: str = Field("", max_length=5000)
    contributions_teams: str = Field("", max_length=3000)
    contributions_society: str = Field("", max_length=3000)
    further_details: str = Field("", max_length=5000)
    why_timely_pex: str = Field("", max_length=3000)  # PEX only

    # --- Team ---
    team_cv_synopsis: str = Field("", max_length=10000)

    # --- Work Plan ---
    abstract_pt: str = Field("", max_length=5000)
    abstract_en: str = Field("", max_length=5000)
    state_of_art_objectives: str = Field("", max_length=6000)
    research_plan_methods: str = Field("", max_length=10000)
    bibliographic_references: str = Field("", max_length=10000)

    # --- Tasks & Timeline ---
    tasks: list[ProposalTask] = Field(default_factory=list)
    deliverables: list[Deliverable] = Field(default_factory=list)
    milestones: list[Milestone] = Field(default_factory=list)
    management_structure: str = Field("", max_length=3000)

    # --- Ethics & SDGs ---
    ethics_justification: str = Field("", max_length=3000)
    sdg_alignment: list[int] = Field(default_factory=list)

    # --- Budget (summary) ---
    total_budget: float = 0.0
    budget_by_institution: dict[str, float] = Field(default_factory=dict)

    def char_count_report(self) -> dict[str, dict[str, int]]:
        """Returns actual vs. limit character counts for each constrained field."""
        from src.config.fct_constants import CHAR_LIMITS as CL
        fields = {
            "career_profile": (self.career_profile, CL.career_profile),
            "contributions_new_ideas": (self.contributions_new_ideas, CL.contributions_new_ideas),
            "contributions_teams": (self.contributions_teams, CL.contributions_teams),
            "contributions_society": (self.contributions_society, CL.contributions_society),
            "further_details": (self.further_details, CL.further_details),
            "team_cv_synopsis": (self.team_cv_synopsis, CL.team_cv_synopsis),
            "abstract_pt": (self.abstract_pt, CL.abstract_pt),
            "abstract_en": (self.abstract_en, CL.abstract_en),
            "state_of_art_objectives": (self.state_of_art_objectives, CL.state_of_art_objectives),
            "research_plan_methods": (self.research_plan_methods, CL.research_plan_methods),
            "bibliographic_references": (self.bibliographic_references, CL.bibliographic_references),
            "management_structure": (self.management_structure, CL.management_structure),
            "ethics_justification": (self.ethics_justification, CL.ethics_justification),
        }
        return {
            name: {"actual": len(text), "limit": limit, "remaining": limit - len(text)}
            for name, (text, limit) in fields.items()
        }


# =============================================================================
# Review Models
# =============================================================================

class CriterionScore(BaseModel):
    criterion: str  # A, B, C
    sub_criterion: str = ""  # A1, A2, B1, B2
    score: float = Field(ge=1.0, le=10.0)
    justification: str = ""
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class ReviewReport(BaseModel):
    """Single reviewer's assessment."""
    reviewer_id: str  # e.g., "claude_rigor", "openai_innovation"
    reviewer_model: str
    reviewer_provider: str
    perspective: str  # "scientific_rigor", "innovation", "feasibility", "domain_expert"
    overall_score: float = Field(ge=1.0, le=10.0)
    criterion_scores: list[CriterionScore] = Field(default_factory=list)
    general_comments: str = ""
    major_revisions: list[str] = Field(default_factory=list)
    minor_revisions: list[str] = Field(default_factory=list)
    decision: str = "major_revision"  # accept, minor_revision, major_revision, reject


class ConsensusReport(BaseModel):
    """Aggregated panel review from multiple AI models."""
    individual_reviews: list[ReviewReport] = Field(default_factory=list)
    consensus_score: float = 0.0
    weighted_scores: dict[str, float] = Field(default_factory=dict)  # A, B, C
    key_strengths: list[str] = Field(default_factory=list)
    key_weaknesses: list[str] = Field(default_factory=list)
    priority_revisions: list[str] = Field(default_factory=list)
    panel_decision: str = "major_revision"
    panel_narrative: str = ""


# =============================================================================
# FCT-REVIEW-ITERATE v1 — Grading Enums & Data Models
# =============================================================================

class Severity(str, Enum):
    """S3=Disqualifying/Fatal, S2=Major, S1=Moderate, S0=Minor."""
    S3 = "S3"  # -15 readiness
    S2 = "S2"  # -8 readiness
    S1 = "S1"  # -3 readiness
    S0 = "S0"  # -1 readiness


class EvidenceStatus(str, Enum):
    """How well the critique is supported by evidence."""
    E2 = "E2"  # Explicit — direct quote or data
    E1 = "E1"  # Implicit — reasonable inference
    E0 = "E0"  # Speculative — no clear basis


class Confidence(str, Enum):
    """Reviewer confidence in the critique."""
    C2 = "C2"  # High
    C1 = "C1"  # Medium
    C0 = "C0"  # Low


class Effort(str, Enum):
    """Estimated effort to address the suggestion."""
    F3 = "F3"  # High redesign
    F2 = "F2"  # Moderate rewrite
    F1 = "F1"  # Small edit
    F0 = "F0"  # Trivial fix


class Impact(str, Enum):
    """Expected impact on proposal quality if addressed."""
    I3 = "I3"  # Large uplift
    I2 = "I2"  # Noticeable improvement
    I1 = "I1"  # Minor improvement
    I0 = "I0"  # Negligible


class Dependency(str, Enum):
    """Whether fixing this unlocks other fixes."""
    D2 = "D2"  # Unlocks multiple downstream fixes
    D1 = "D1"  # Unlocks one other fix
    D0 = "D0"  # Independent


class Actionability(str, Enum):
    """How actionable the suggestion is."""
    A2 = "A2"  # Fully actionable — clear steps
    A1 = "A1"  # Partially actionable — needs interpretation
    A0 = "A0"  # Vague — no clear steps


SEVERITY_PENALTY = {
    Severity.S3: 15,
    Severity.S2: 8,
    Severity.S1: 3,
    Severity.S0: 1,
}


class SuggestionRecord(BaseModel):
    """Atomized, graded critique from a reviewer."""
    id: str = ""                            # SUG-001, SUG-002, ...
    source_reviewer: str = ""               # reviewer_id
    source_text: str = ""                   # original critique quote
    issue: str = ""                         # 1-2 line normalized critique
    recommended_fix: str = ""               # concrete steps
    criterion_tags: list[str] = Field(default_factory=list)   # ["A1", "C"]
    target_sections: list[str] = Field(default_factory=list)  # proposal field names
    severity: Severity = Severity.S1
    evidence_status: EvidenceStatus = EvidenceStatus.E1
    confidence: Confidence = Confidence.C1
    effort: Effort = Effort.F1
    impact: Impact = Impact.I1
    dependency: Dependency = Dependency.D0
    actionability: Actionability = Actionability.A1
    acceptance_test: str = ""               # how to verify fixed
    depends_on: list[str] = Field(default_factory=list)   # SUG-xxx IDs
    blocks: list[str] = Field(default_factory=list)       # SUG-xxx IDs


class SuggestionAction(BaseModel):
    """Record of what was done with a suggestion during revision."""
    suggestion_id: str = ""
    action: str = "deferred"                # adopted | partially_adopted | deferred | not_adopted
    edit_summary: str = ""
    section_modified: str = ""
    before_text_snippet: str = ""           # first 200 chars before
    after_text_snippet: str = ""            # first 200 chars after
    acceptance_test_result: str = "Not yet"  # Pass | Not yet | Deferred
    reason_if_not_adopted: str = ""


class ConsistencyCheck(BaseModel):
    """Result of a single consistency check."""
    check_name: str = ""                    # e.g. "budget_totals_reconcile"
    passed: bool = True
    details: str = ""
    auto_fixed: bool = False


class StoplightEntry(BaseModel):
    """Stoplight status for one evaluation criterion."""
    criterion: str = ""                     # A, B, C, E
    color: str = "green"                    # green, amber, red
    s3_count: int = 0
    s2_count: int = 0
    rationale: str = ""


class LLMCallRecord(BaseModel):
    """Record of a single LLM API call with token counts and cost."""
    call_id: str = ""                       # e.g. "atomize", "revise_state_of_art"
    step: str = ""                          # "atomize", "revise", "consistency", "narrative"
    model: str = ""
    provider: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    timestamp: str = ""


class CostSummary(BaseModel):
    """Aggregate cost summary for one review-iterate cycle."""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    calls: list[LLMCallRecord] = Field(default_factory=list)
    by_step: dict[str, float] = Field(default_factory=dict)   # step -> cost_usd
    by_model: dict[str, float] = Field(default_factory=dict)  # model -> cost_usd


class ImprovementReport(BaseModel):
    """Full improvement report produced after each review-iterate cycle."""
    version: int = 0
    timestamp: str = ""
    readiness_index: float = 0.0            # 0-100
    stoplight: list[StoplightEntry] = Field(default_factory=list)
    all_suggestions: list[SuggestionRecord] = Field(default_factory=list)
    actions: list[SuggestionAction] = Field(default_factory=list)
    consistency_checks: list[ConsistencyCheck] = Field(default_factory=list)
    top5_ids: list[str] = Field(default_factory=list)
    executive_summary: str = ""
    science_method_changes: str = ""
    feasibility_budget_changes: str = ""
    ethics_compliance_changes: str = ""
    risk_register: str = ""                 # markdown table of top-5 risks
    cost_summary: CostSummary | None = None
    llm_call_log: list[LLMCallRecord] = Field(default_factory=list)
