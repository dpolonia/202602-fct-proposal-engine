"""
Character limit compliance rules — CL01-CL28.

Pure arithmetic checks using CHAR_LIMITS from fct_constants.py.
"""

from __future__ import annotations

from src.compliance.models import (
    ComplianceCategory,
    ComplianceFinding,
    ComplianceSeverity,
    ComplianceStatus,
)
from src.compliance.registry import RuleRegistry
from src.config.fct_constants import CHAR_LIMITS as CL


def _check_char_limit(
    value: str,
    limit: int,
    rule_id: str,
    description: str,
    severity: ComplianceSeverity,
    field_path: str,
) -> ComplianceFinding:
    """Check a single string field against a character limit."""
    actual = len(value)
    if actual > limit:
        return ComplianceFinding(
            rule_id=rule_id,
            category=ComplianceCategory.CHAR_LIMITS,
            severity=severity,
            status=ComplianceStatus.FAIL,
            description=description,
            actual_value=str(actual),
            expected_value=f"<= {limit}",
            field_path=field_path,
            suggestion=f"Reduce by {actual - limit} characters.",
        )
    return ComplianceFinding(
        rule_id=rule_id,
        category=ComplianceCategory.CHAR_LIMITS,
        severity=severity,
        status=ComplianceStatus.PASS,
        description=description,
        actual_value=str(actual),
        expected_value=f"<= {limit}",
        field_path=field_path,
    )


# --- Single-field rules (CL01-CL17, CL23-CL27) ---

_SINGLE_FIELD_RULES = [
    (
        "CL01",
        "title_en",
        CL.project_title,
        ComplianceSeverity.BLOCKER,
        "Project title (EN): max 255 characters",
    ),
    (
        "CL02",
        "acronym",
        CL.project_acronym,
        ComplianceSeverity.BLOCKER,
        "Project acronym: max 15 characters",
    ),
    (
        "CL04",
        "institution_description",
        CL.institution_description,
        ComplianceSeverity.MAJOR,
        "Institution description: max 1500 characters",
    ),
    (
        "CL05",
        "career_profile",
        CL.career_profile,
        ComplianceSeverity.MAJOR,
        "Career profile: max 4000 characters",
    ),
    (
        "CL06",
        "contributions_new_ideas",
        CL.contributions_new_ideas,
        ComplianceSeverity.MAJOR,
        "Contributions — new ideas: max 5000 characters",
    ),
    (
        "CL07",
        "contributions_teams",
        CL.contributions_teams,
        ComplianceSeverity.MAJOR,
        "Contributions — teams: max 3000 characters",
    ),
    (
        "CL08",
        "contributions_society",
        CL.contributions_society,
        ComplianceSeverity.MAJOR,
        "Contributions — society: max 3000 characters",
    ),
    (
        "CL09",
        "further_details",
        CL.further_details,
        ComplianceSeverity.MAJOR,
        "Further details: max 5000 characters",
    ),
    (
        "CL10",
        "why_timely_pex",
        CL.why_timely_pex,
        ComplianceSeverity.MAJOR,
        "Why timely (PEX): max 3000 characters",
    ),
    (
        "CL11",
        "team_cv_synopsis",
        CL.team_cv_synopsis,
        ComplianceSeverity.MAJOR,
        "Team CV synopsis: max 10000 characters",
    ),
    (
        "CL12",
        "management_structure",
        CL.management_structure,
        ComplianceSeverity.MAJOR,
        "Management structure: max 3000 characters",
    ),
    (
        "CL13",
        "abstract_pt",
        CL.abstract_pt,
        ComplianceSeverity.BLOCKER,
        "Abstract (PT): max 5000 characters",
    ),
    (
        "CL14",
        "abstract_en",
        CL.abstract_en,
        ComplianceSeverity.BLOCKER,
        "Abstract (EN): max 5000 characters",
    ),
    (
        "CL15",
        "state_of_art_objectives",
        CL.state_of_art_objectives,
        ComplianceSeverity.BLOCKER,
        "State of art & objectives: max 6000 characters",
    ),
    (
        "CL16",
        "research_plan_methods",
        CL.research_plan_methods,
        ComplianceSeverity.BLOCKER,
        "Research plan & methods: max 10000 characters",
    ),
    (
        "CL17",
        "bibliographic_references",
        CL.bibliographic_references,
        ComplianceSeverity.MAJOR,
        "Bibliographic references: max 10000 characters",
    ),
    (
        "CL23",
        "ethics_justification",
        CL.ethics_justification,
        ComplianceSeverity.MAJOR,
        "Ethics justification: max 3000 characters",
    ),
    (
        "CL24",
        "title_pt",
        CL.project_title,
        ComplianceSeverity.BLOCKER,
        "Project title (PT): max 255 characters",
    ),
]


def _register_single_field_rules() -> None:
    """Register all single-field character limit rules."""
    for rule_id, field_name, limit, severity, description in _SINGLE_FIELD_RULES:
        # PEX-only rule
        typologies = ["PEX"] if field_name == "why_timely_pex" else ["SR&TD", "PEX"]

        def make_check(fld=field_name, lim=limit, rid=rule_id, desc=description, sev=severity):
            def check(proposal, draft=None):
                value = getattr(proposal, fld, "")
                return _check_char_limit(value, lim, rid, desc, sev, fld)

            return check

        RuleRegistry.register(
            rule_id=rule_id,
            category=ComplianceCategory.CHAR_LIMITS,
            severity=severity,
            description=description,
            applicable_typologies=typologies,
        )(make_check())


_register_single_field_rules()


# --- CL03: Keywords count ---


@RuleRegistry.register(
    rule_id="CL03",
    category=ComplianceCategory.CHAR_LIMITS,
    severity=ComplianceSeverity.MAJOR,
    description="Keywords: max 4 per language",
)
def check_cl03(proposal, draft=None) -> ComplianceFinding:
    en_count = len(proposal.keywords_en)
    pt_count = len(proposal.keywords_pt)
    max_kw = CL.max_keywords
    if en_count > max_kw or pt_count > max_kw:
        return ComplianceFinding(
            rule_id="CL03",
            category=ComplianceCategory.CHAR_LIMITS,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.FAIL,
            description="Keywords: max 4 per language",
            actual_value=f"EN={en_count}, PT={pt_count}",
            expected_value=f"<= {max_kw} each",
            field_path="keywords_en / keywords_pt",
            suggestion="Reduce keywords to max 4 per language.",
        )
    return ComplianceFinding(
        rule_id="CL03",
        category=ComplianceCategory.CHAR_LIMITS,
        severity=ComplianceSeverity.MAJOR,
        status=ComplianceStatus.PASS,
        description="Keywords: max 4 per language",
        actual_value=f"EN={en_count}, PT={pt_count}",
        expected_value=f"<= {max_kw} each",
        field_path="keywords_en / keywords_pt",
    )


# --- Per-item rules: CL18-CL22 ---


@RuleRegistry.register(
    rule_id="CL18",
    category=ComplianceCategory.CHAR_LIMITS,
    severity=ComplianceSeverity.MAJOR,
    description="Task denomination: max 150 characters each",
)
def check_cl18(proposal, draft=None) -> list[ComplianceFinding]:
    findings = []
    for task in proposal.tasks:
        findings.append(
            _check_char_limit(
                task.denomination,
                CL.task_denomination,
                "CL18",
                "Task denomination: max 150 characters",
                ComplianceSeverity.MAJOR,
                f"tasks[{task.number}].denomination",
            )
        )
    return findings or [
        ComplianceFinding(
            rule_id="CL18",
            category=ComplianceCategory.CHAR_LIMITS,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.PASS,
            description="Task denomination: max 150 characters each",
        )
    ]


@RuleRegistry.register(
    rule_id="CL19",
    category=ComplianceCategory.CHAR_LIMITS,
    severity=ComplianceSeverity.MAJOR,
    description="Task description: max 4000 characters each",
)
def check_cl19(proposal, draft=None) -> list[ComplianceFinding]:
    findings = []
    for task in proposal.tasks:
        findings.append(
            _check_char_limit(
                task.description,
                CL.task_description,
                "CL19",
                "Task description: max 4000 characters",
                ComplianceSeverity.MAJOR,
                f"tasks[{task.number}].description",
            )
        )
    return findings or [
        ComplianceFinding(
            rule_id="CL19",
            category=ComplianceCategory.CHAR_LIMITS,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.PASS,
            description="Task description: max 4000 characters each",
        )
    ]


@RuleRegistry.register(
    rule_id="CL20",
    category=ComplianceCategory.CHAR_LIMITS,
    severity=ComplianceSeverity.MAJOR,
    description="Cost justification: max 2500 characters each",
)
def check_cl20(proposal, draft=None) -> list[ComplianceFinding]:
    findings = []
    for task in proposal.tasks:
        findings.append(
            _check_char_limit(
                task.cost_justification,
                CL.cost_justification,
                "CL20",
                "Cost justification: max 2500 characters",
                ComplianceSeverity.MAJOR,
                f"tasks[{task.number}].cost_justification",
            )
        )
    return findings or [
        ComplianceFinding(
            rule_id="CL20",
            category=ComplianceCategory.CHAR_LIMITS,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.PASS,
            description="Cost justification: max 2500 characters each",
        )
    ]


@RuleRegistry.register(
    rule_id="CL21",
    category=ComplianceCategory.CHAR_LIMITS,
    severity=ComplianceSeverity.MAJOR,
    description="Deliverable description: max 800 characters each",
)
def check_cl21(proposal, draft=None) -> list[ComplianceFinding]:
    findings = []
    for d in proposal.deliverables:
        findings.append(
            _check_char_limit(
                d.description,
                CL.deliverable_description,
                "CL21",
                "Deliverable description: max 800 characters",
                ComplianceSeverity.MAJOR,
                f"deliverables[{d.code}].description",
            )
        )
    return findings or [
        ComplianceFinding(
            rule_id="CL21",
            category=ComplianceCategory.CHAR_LIMITS,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.PASS,
            description="Deliverable description: max 800 characters each",
        )
    ]


@RuleRegistry.register(
    rule_id="CL22",
    category=ComplianceCategory.CHAR_LIMITS,
    severity=ComplianceSeverity.MAJOR,
    description="Milestone description: max 300 characters each",
)
def check_cl22(proposal, draft=None) -> list[ComplianceFinding]:
    findings = []
    for m in proposal.milestones:
        findings.append(
            _check_char_limit(
                m.description,
                CL.milestone_description,
                "CL22",
                "Milestone description: max 300 characters",
                ComplianceSeverity.MAJOR,
                f"milestones[{m.code}].description",
            )
        )
    return findings or [
        ComplianceFinding(
            rule_id="CL22",
            category=ComplianceCategory.CHAR_LIMITS,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.PASS,
            description="Milestone description: max 300 characters each",
        )
    ]


# --- CL28: 95% safety margin check ---

_SAFETY_MARGIN_FIELDS = {
    "title_en": CL.project_title,
    "abstract_pt": CL.abstract_pt,
    "abstract_en": CL.abstract_en,
    "state_of_art_objectives": CL.state_of_art_objectives,
    "research_plan_methods": CL.research_plan_methods,
    "career_profile": CL.career_profile,
    "contributions_new_ideas": CL.contributions_new_ideas,
    "contributions_teams": CL.contributions_teams,
    "contributions_society": CL.contributions_society,
    "further_details": CL.further_details,
    "team_cv_synopsis": CL.team_cv_synopsis,
    "management_structure": CL.management_structure,
    "ethics_justification": CL.ethics_justification,
    "bibliographic_references": CL.bibliographic_references,
}


@RuleRegistry.register(
    rule_id="CL28",
    category=ComplianceCategory.CHAR_LIMITS,
    severity=ComplianceSeverity.MAJOR,
    description="95% safety margin: fields >95% of limit flagged",
)
def check_cl28(proposal, draft=None) -> list[ComplianceFinding]:
    findings = []
    for field_name, limit in _SAFETY_MARGIN_FIELDS.items():
        value = getattr(proposal, field_name, "")
        actual = len(value)
        threshold = int(limit * 0.95)
        if actual > threshold and actual <= limit:
            findings.append(
                ComplianceFinding(
                    rule_id="CL28",
                    category=ComplianceCategory.CHAR_LIMITS,
                    severity=ComplianceSeverity.MAJOR,
                    status=ComplianceStatus.FAIL,
                    description=f"95% safety margin: {field_name} at {actual}/{limit} "
                    f"({actual * 100 // limit}%)",
                    actual_value=str(actual),
                    expected_value=f"<= {threshold} (95% of {limit})",
                    field_path=field_name,
                    suggestion=f"Consider trimming — only {limit - actual} chars remaining.",
                )
            )
    return findings or [
        ComplianceFinding(
            rule_id="CL28",
            category=ComplianceCategory.CHAR_LIMITS,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.PASS,
            description="All fields within 95% safety margin",
        )
    ]
