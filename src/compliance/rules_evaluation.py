"""
Evaluation alignment rules — EV01-EV09.

Section presence heuristics with keyword detection to ensure
proposal content aligns with FCT evaluation criteria.
"""

from __future__ import annotations

from src.compliance.models import (
    ComplianceCategory,
    ComplianceFinding,
    ComplianceSeverity,
    ComplianceStatus,
)
from src.compliance.registry import RuleRegistry


def _has_any_keyword(text: str, keywords: list[str]) -> bool:
    """Check if any keyword is present in text (case-insensitive)."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


# --- EV01: SOA contains innovation/novelty keywords ---


@RuleRegistry.register(
    rule_id="EV01",
    category=ComplianceCategory.EVALUATION,
    severity=ComplianceSeverity.MAJOR,
    description="State of art should highlight novelty/innovation (criterion A2)",
)
def check_ev01(proposal, draft=None) -> ComplianceFinding:
    if not proposal.state_of_art_objectives.strip():
        return ComplianceFinding(
            rule_id="EV01",
            category=ComplianceCategory.EVALUATION,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.SKIP,
            description="SOA section is empty",
        )
    novelty_kw = [
        "novel",
        "innovat",
        "original",
        "first",
        "pioneer",
        "unique",
        "gap",
        "unexplored",
        "new approach",
        "advancement",
        "breakthrough",
        "state-of-the-art",
        "beyond",
    ]
    if not _has_any_keyword(proposal.state_of_art_objectives, novelty_kw):
        return ComplianceFinding(
            rule_id="EV01",
            category=ComplianceCategory.EVALUATION,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.FAIL,
            description="SOA lacks novelty/innovation language (important for A2)",
            field_path="state_of_art_objectives",
            suggestion="Add explicit novelty claims positioned against prior art.",
        )
    return ComplianceFinding(
        rule_id="EV01",
        category=ComplianceCategory.EVALUATION,
        severity=ComplianceSeverity.MAJOR,
        status=ComplianceStatus.PASS,
        description="SOA contains innovation/novelty language",
    )


# --- EV02: Research plan describes methodology ---


@RuleRegistry.register(
    rule_id="EV02",
    category=ComplianceCategory.EVALUATION,
    severity=ComplianceSeverity.MAJOR,
    description="Research plan must describe methodology (criterion A1)",
)
def check_ev02(proposal, draft=None) -> ComplianceFinding:
    if not proposal.research_plan_methods.strip():
        return ComplianceFinding(
            rule_id="EV02",
            category=ComplianceCategory.EVALUATION,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.SKIP,
            description="Research plan is empty",
        )
    method_kw = [
        "method",
        "approach",
        "framework",
        "design",
        "technique",
        "protocol",
        "procedure",
        "analysis",
        "strategy",
        "model",
        "algorithm",
        "instrument",
        "measurement",
    ]
    if not _has_any_keyword(proposal.research_plan_methods, method_kw):
        return ComplianceFinding(
            rule_id="EV02",
            category=ComplianceCategory.EVALUATION,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.FAIL,
            description="Research plan lacks methodology language (A1)",
            field_path="research_plan_methods",
            suggestion="Describe research methodology explicitly.",
        )
    return ComplianceFinding(
        rule_id="EV02",
        category=ComplianceCategory.EVALUATION,
        severity=ComplianceSeverity.MAJOR,
        status=ComplianceStatus.PASS,
        description="Research plan describes methodology",
    )


# --- EV03: Career profile mentions publications/track record ---


@RuleRegistry.register(
    rule_id="EV03",
    category=ComplianceCategory.EVALUATION,
    severity=ComplianceSeverity.MAJOR,
    description="Career profile should mention publications/track record (criterion B1)",
)
def check_ev03(proposal, draft=None) -> ComplianceFinding:
    if not proposal.career_profile.strip():
        return ComplianceFinding(
            rule_id="EV03",
            category=ComplianceCategory.EVALUATION,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.SKIP,
            description="Career profile is empty",
        )
    track_kw = [
        "publication",
        "h-index",
        "h index",
        "track record",
        "journal",
        "paper",
        "cited",
        "citation",
        "impact factor",
        "scopus",
        "web of science",
        "orcid",
        "peer-review",
    ]
    if not _has_any_keyword(proposal.career_profile, track_kw):
        return ComplianceFinding(
            rule_id="EV03",
            category=ComplianceCategory.EVALUATION,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.FAIL,
            description="Career profile lacks publication/track record mention (B1)",
            field_path="career_profile",
            suggestion="Add publication metrics and track record evidence.",
        )
    return ComplianceFinding(
        rule_id="EV03",
        category=ComplianceCategory.EVALUATION,
        severity=ComplianceSeverity.MAJOR,
        status=ComplianceStatus.PASS,
        description="Career profile mentions publications/track record",
    )


# --- EV04: Team CV mentions complementarity ---


@RuleRegistry.register(
    rule_id="EV04",
    category=ComplianceCategory.EVALUATION,
    severity=ComplianceSeverity.MAJOR,
    description="Team CV should show complementarity/expertise alignment (B2)",
)
def check_ev04(proposal, draft=None) -> ComplianceFinding:
    if not proposal.team_cv_synopsis.strip():
        return ComplianceFinding(
            rule_id="EV04",
            category=ComplianceCategory.EVALUATION,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.SKIP,
            description="Team CV is empty",
        )
    team_kw = [
        "complementar",
        "expertise",
        "experience",
        "specialist",
        "collaboration",
        "interdisciplin",
        "multidisciplin",
        "skill",
        "competenc",
    ]
    if not _has_any_keyword(proposal.team_cv_synopsis, team_kw):
        return ComplianceFinding(
            rule_id="EV04",
            category=ComplianceCategory.EVALUATION,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.FAIL,
            description="Team CV lacks complementarity/expertise language (B2)",
            field_path="team_cv_synopsis",
            suggestion="Highlight team member expertise and complementarity.",
        )
    return ComplianceFinding(
        rule_id="EV04",
        category=ComplianceCategory.EVALUATION,
        severity=ComplianceSeverity.MAJOR,
        status=ComplianceStatus.PASS,
        description="Team CV shows complementarity/expertise",
    )


# --- EV05: Management mentions risk/contingency ---


@RuleRegistry.register(
    rule_id="EV05",
    category=ComplianceCategory.EVALUATION,
    severity=ComplianceSeverity.MAJOR,
    description="Management structure should mention risk/contingency (criterion C)",
)
def check_ev05(proposal, draft=None) -> ComplianceFinding:
    if not proposal.management_structure.strip():
        return ComplianceFinding(
            rule_id="EV05",
            category=ComplianceCategory.EVALUATION,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.SKIP,
            description="Management section is empty",
        )
    risk_kw = [
        "risk",
        "contingenc",
        "mitigation",
        "fallback",
        "plan b",
        "alternative",
        "escalat",
        "monitor",
        "quality assurance",
    ]
    if not _has_any_keyword(proposal.management_structure, risk_kw):
        return ComplianceFinding(
            rule_id="EV05",
            category=ComplianceCategory.EVALUATION,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.FAIL,
            description="Management lacks risk/contingency discussion (C)",
            field_path="management_structure",
            suggestion="Add risk assessment and contingency plans.",
        )
    return ComplianceFinding(
        rule_id="EV05",
        category=ComplianceCategory.EVALUATION,
        severity=ComplianceSeverity.MAJOR,
        status=ComplianceStatus.PASS,
        description="Management mentions risk/contingency",
    )


# --- EV06: Budget justification references tasks ---


@RuleRegistry.register(
    rule_id="EV06",
    category=ComplianceCategory.EVALUATION,
    severity=ComplianceSeverity.MAJOR,
    description="Cost justifications should reference specific tasks",
)
def check_ev06(proposal, draft=None) -> ComplianceFinding:
    if not proposal.tasks:
        return ComplianceFinding(
            rule_id="EV06",
            category=ComplianceCategory.EVALUATION,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.SKIP,
            description="No tasks",
        )
    task_ref_kw = ["task", "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8"]
    tasks_with_justification = [t for t in proposal.tasks if t.cost_justification.strip()]
    if not tasks_with_justification:
        return ComplianceFinding(
            rule_id="EV06",
            category=ComplianceCategory.EVALUATION,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.SKIP,
            description="No cost justifications to check",
        )
    all_justifications = " ".join(t.cost_justification for t in tasks_with_justification)
    if not _has_any_keyword(all_justifications, task_ref_kw):
        return ComplianceFinding(
            rule_id="EV06",
            category=ComplianceCategory.EVALUATION,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.WARN,
            description="Cost justifications don't explicitly reference tasks",
            suggestion="Reference specific tasks in budget justifications.",
        )
    return ComplianceFinding(
        rule_id="EV06",
        category=ComplianceCategory.EVALUATION,
        severity=ComplianceSeverity.MAJOR,
        status=ComplianceStatus.PASS,
        description="Cost justifications reference tasks",
    )


# --- EV07: Deliverables are measurable ---


@RuleRegistry.register(
    rule_id="EV07",
    category=ComplianceCategory.EVALUATION,
    severity=ComplianceSeverity.MINOR,
    description="Deliverables should have measurable descriptions",
)
def check_ev07(proposal, draft=None) -> ComplianceFinding:
    if not proposal.deliverables:
        return ComplianceFinding(
            rule_id="EV07",
            category=ComplianceCategory.EVALUATION,
            severity=ComplianceSeverity.MINOR,
            status=ComplianceStatus.SKIP,
            description="No deliverables",
        )
    measurable_kw = [
        "report",
        "paper",
        "dataset",
        "prototype",
        "software",
        "model",
        "framework",
        "publication",
        "document",
        "plan",
        "demo",
        "deliverable",
        "output",
    ]
    all_desc = " ".join(d.description + " " + d.title for d in proposal.deliverables)
    if not _has_any_keyword(all_desc, measurable_kw):
        return ComplianceFinding(
            rule_id="EV07",
            category=ComplianceCategory.EVALUATION,
            severity=ComplianceSeverity.MINOR,
            status=ComplianceStatus.WARN,
            description="Deliverable descriptions may lack measurability",
            suggestion="Ensure deliverables describe concrete, measurable outputs.",
        )
    return ComplianceFinding(
        rule_id="EV07",
        category=ComplianceCategory.EVALUATION,
        severity=ComplianceSeverity.MINOR,
        status=ComplianceStatus.PASS,
        description="Deliverables appear measurable",
    )


# --- EV08: Impact pathway ---


@RuleRegistry.register(
    rule_id="EV08",
    category=ComplianceCategory.EVALUATION,
    severity=ComplianceSeverity.MINOR,
    description="Proposal should describe an impact pathway",
)
def check_ev08(proposal, draft=None) -> ComplianceFinding:
    # Check across multiple sections for impact language
    combined = " ".join(
        [
            proposal.state_of_art_objectives,
            proposal.research_plan_methods,
            proposal.contributions_society,
        ]
    )
    impact_kw = [
        "impact",
        "disseminat",
        "exploit",
        "transfer",
        "stakeholder",
        "adoption",
        "policy",
        "societal",
        "economic",
        "valoriz",
    ]
    if not _has_any_keyword(combined, impact_kw):
        return ComplianceFinding(
            rule_id="EV08",
            category=ComplianceCategory.EVALUATION,
            severity=ComplianceSeverity.MINOR,
            status=ComplianceStatus.WARN,
            description="No clear impact pathway language found",
            suggestion="Add impact/dissemination pathway discussion.",
        )
    return ComplianceFinding(
        rule_id="EV08",
        category=ComplianceCategory.EVALUATION,
        severity=ComplianceSeverity.MINOR,
        status=ComplianceStatus.PASS,
        description="Impact pathway language detected",
    )


# --- EV09: Dissemination plan ---


@RuleRegistry.register(
    rule_id="EV09",
    category=ComplianceCategory.EVALUATION,
    severity=ComplianceSeverity.MINOR,
    description="Proposal should include a dissemination plan",
)
def check_ev09(proposal, draft=None) -> ComplianceFinding:
    combined = " ".join(
        [
            proposal.research_plan_methods,
            proposal.management_structure,
        ]
    )
    # Also check deliverable titles/descriptions
    for d in proposal.deliverables:
        combined += " " + d.title + " " + d.description
    dissemination_kw = [
        "disseminat",
        "publish",
        "conference",
        "workshop",
        "open access",
        "open data",
        "communication",
        "outreach",
        "website",
        "repository",
    ]
    if not _has_any_keyword(combined, dissemination_kw):
        return ComplianceFinding(
            rule_id="EV09",
            category=ComplianceCategory.EVALUATION,
            severity=ComplianceSeverity.MINOR,
            status=ComplianceStatus.WARN,
            description="No clear dissemination plan detected",
            suggestion="Add dissemination/communication plan.",
        )
    return ComplianceFinding(
        rule_id="EV09",
        category=ComplianceCategory.EVALUATION,
        severity=ComplianceSeverity.MINOR,
        status=ComplianceStatus.PASS,
        description="Dissemination plan language detected",
    )
