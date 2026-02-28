"""
Data models for the entire proposal lifecycle:
  DraftIdea → Proposal → Review → RevisedProposal
"""

from __future__ import annotations

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
