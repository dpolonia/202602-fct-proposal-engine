"""
Ethics compliance rules — ET01-ET08.

Keyword scanning (no LLM). Checks for consistency between work plan
activities and ethics justification.
"""

from __future__ import annotations

import re

from src.compliance.models import (
    ComplianceCategory,
    ComplianceFinding,
    ComplianceSeverity,
    ComplianceStatus,
)
from src.compliance.registry import RuleRegistry

# Keyword sets for ethics detection
_HUMAN_SUBJECTS_KEYWORDS = [
    "participant",
    "interview",
    "survey",
    "questionnaire",
    "informed consent",
    "human subject",
    "focus group",
    "experimental group",
    "control group",
    "respondent",
]

_PERSONAL_DATA_KEYWORDS = [
    "personal data",
    "gdpr",
    "anonymis",
    "pseudonymis",
    "data protection",
    "privacy",
    "sensitive data",
    "data subject",
    "consent form",
]

_HEALTH_DATA_KEYWORDS = [
    "patient",
    "health record",
    "clinical",
    "hospital",
    "nhs",
    "insa",
    "dgs",
    "microdata",
    "tstr",
    "medical",
    "biobank",
    "biological sample",
]

_ANIMAL_KEYWORDS = [
    "animal experiment",
    "animal model",
    "in vivo",
    "laboratory animal",
    "mice",
    "rats",
    "vertebrate",
]

_DUAL_USE_KEYWORDS = [
    "dual use",
    "biosecurity",
    "pathogen",
    "gain of function",
    "weaponiz",
    "surveillance",
    "military",
]


def _collect_work_plan_text(proposal) -> str:
    """Collect all work plan text for keyword scanning."""
    parts = []
    for t in proposal.tasks:
        parts.append(t.denomination.lower())
        parts.append(t.description.lower())
    parts.append(proposal.research_plan_methods.lower())
    return " ".join(parts)


def _has_keywords(text: str, keywords: list[str]) -> list[str]:
    """Return which keywords were found in text."""
    found = []
    text_lower = text.lower()
    for kw in keywords:
        if kw in text_lower:
            found.append(kw)
    return found


def _ethics_acknowledges(ethics_text: str, keywords: list[str]) -> bool:
    """Check if ethics section mentions relevant keywords."""
    ethics_lower = ethics_text.lower()
    return any(kw in ethics_lower for kw in keywords)


# --- ET01: Human subjects detected but not in ethics ---


@RuleRegistry.register(
    rule_id="ET01",
    category=ComplianceCategory.ETHICS,
    severity=ComplianceSeverity.CRITICAL,
    description="Human subjects in work plan must be addressed in ethics section",
)
def check_et01(proposal, draft=None) -> ComplianceFinding:
    wp_text = _collect_work_plan_text(proposal)
    found = _has_keywords(wp_text, _HUMAN_SUBJECTS_KEYWORDS)
    if not found:
        return ComplianceFinding(
            rule_id="ET01",
            category=ComplianceCategory.ETHICS,
            severity=ComplianceSeverity.CRITICAL,
            status=ComplianceStatus.NA,
            description="No human subject keywords detected in work plan",
        )
    acknowledged = _ethics_acknowledges(
        proposal.ethics_justification,
        _HUMAN_SUBJECTS_KEYWORDS + ["ethics", "human", "consent", "committee"],
    )
    if not acknowledged:
        return ComplianceFinding(
            rule_id="ET01",
            category=ComplianceCategory.ETHICS,
            severity=ComplianceSeverity.CRITICAL,
            status=ComplianceStatus.FAIL,
            description="Human subject activities detected but not addressed in ethics",
            actual_value=f"Keywords found: {', '.join(found[:5])}",
            field_path="ethics_justification",
            suggestion="Add ethics justification for human subject involvement.",
        )
    return ComplianceFinding(
        rule_id="ET01",
        category=ComplianceCategory.ETHICS,
        severity=ComplianceSeverity.CRITICAL,
        status=ComplianceStatus.PASS,
        description="Human subject activities addressed in ethics section",
        actual_value=f"Keywords: {', '.join(found[:5])}",
    )


# --- ET02: Personal data detected but not in ethics ---


@RuleRegistry.register(
    rule_id="ET02",
    category=ComplianceCategory.ETHICS,
    severity=ComplianceSeverity.CRITICAL,
    description="Personal data handling in work plan must be addressed in ethics",
)
def check_et02(proposal, draft=None) -> ComplianceFinding:
    wp_text = _collect_work_plan_text(proposal)
    found = _has_keywords(wp_text, _PERSONAL_DATA_KEYWORDS)
    if not found:
        return ComplianceFinding(
            rule_id="ET02",
            category=ComplianceCategory.ETHICS,
            severity=ComplianceSeverity.CRITICAL,
            status=ComplianceStatus.NA,
            description="No personal data keywords detected in work plan",
        )
    acknowledged = _ethics_acknowledges(
        proposal.ethics_justification,
        _PERSONAL_DATA_KEYWORDS + ["gdpr", "data protection", "privacy", "dpo"],
    )
    if not acknowledged:
        return ComplianceFinding(
            rule_id="ET02",
            category=ComplianceCategory.ETHICS,
            severity=ComplianceSeverity.CRITICAL,
            status=ComplianceStatus.FAIL,
            description="Personal data handling detected but not in ethics section",
            actual_value=f"Keywords: {', '.join(found[:5])}",
            field_path="ethics_justification",
            suggestion="Add GDPR/data protection discussion to ethics section.",
        )
    return ComplianceFinding(
        rule_id="ET02",
        category=ComplianceCategory.ETHICS,
        severity=ComplianceSeverity.CRITICAL,
        status=ComplianceStatus.PASS,
        description="Personal data handling addressed in ethics section",
    )


# --- ET03: Health data detected but not in ethics ---


@RuleRegistry.register(
    rule_id="ET03",
    category=ComplianceCategory.ETHICS,
    severity=ComplianceSeverity.CRITICAL,
    description="Health/clinical data in work plan must be addressed in ethics",
)
def check_et03(proposal, draft=None) -> ComplianceFinding:
    wp_text = _collect_work_plan_text(proposal)
    found = _has_keywords(wp_text, _HEALTH_DATA_KEYWORDS)
    if not found:
        return ComplianceFinding(
            rule_id="ET03",
            category=ComplianceCategory.ETHICS,
            severity=ComplianceSeverity.CRITICAL,
            status=ComplianceStatus.NA,
            description="No health/clinical data keywords detected",
        )
    acknowledged = _ethics_acknowledges(
        proposal.ethics_justification,
        _HEALTH_DATA_KEYWORDS + ["ethics committee", "health", "clinical"],
    )
    if not acknowledged:
        return ComplianceFinding(
            rule_id="ET03",
            category=ComplianceCategory.ETHICS,
            severity=ComplianceSeverity.CRITICAL,
            status=ComplianceStatus.FAIL,
            description="Health/clinical data detected but not in ethics",
            actual_value=f"Keywords: {', '.join(found[:5])}",
            field_path="ethics_justification",
            suggestion="Add health data handling to ethics section.",
        )
    return ComplianceFinding(
        rule_id="ET03",
        category=ComplianceCategory.ETHICS,
        severity=ComplianceSeverity.CRITICAL,
        status=ComplianceStatus.PASS,
        description="Health data handling addressed in ethics section",
    )


# --- ET04: Animal experiments ---


@RuleRegistry.register(
    rule_id="ET04",
    category=ComplianceCategory.ETHICS,
    severity=ComplianceSeverity.CRITICAL,
    description="Animal experiments must be addressed in ethics section",
)
def check_et04(proposal, draft=None) -> ComplianceFinding:
    wp_text = _collect_work_plan_text(proposal)
    found = _has_keywords(wp_text, _ANIMAL_KEYWORDS)
    if not found:
        return ComplianceFinding(
            rule_id="ET04",
            category=ComplianceCategory.ETHICS,
            severity=ComplianceSeverity.CRITICAL,
            status=ComplianceStatus.NA,
            description="No animal experiment keywords detected",
        )
    acknowledged = _ethics_acknowledges(
        proposal.ethics_justification,
        _ANIMAL_KEYWORDS + ["3rs", "animal welfare", "ethics committee"],
    )
    if not acknowledged:
        return ComplianceFinding(
            rule_id="ET04",
            category=ComplianceCategory.ETHICS,
            severity=ComplianceSeverity.CRITICAL,
            status=ComplianceStatus.FAIL,
            description="Animal experiments detected but not in ethics section",
            actual_value=f"Keywords: {', '.join(found[:5])}",
            field_path="ethics_justification",
            suggestion="Add animal experiment ethics justification.",
        )
    return ComplianceFinding(
        rule_id="ET04",
        category=ComplianceCategory.ETHICS,
        severity=ComplianceSeverity.CRITICAL,
        status=ComplianceStatus.PASS,
        description="Animal experiments addressed in ethics section",
    )


# --- ET05: Dual-use research ---


@RuleRegistry.register(
    rule_id="ET05",
    category=ComplianceCategory.ETHICS,
    severity=ComplianceSeverity.CRITICAL,
    description="Dual-use concerns must be addressed if detected",
)
def check_et05(proposal, draft=None) -> ComplianceFinding:
    wp_text = _collect_work_plan_text(proposal)
    found = _has_keywords(wp_text, _DUAL_USE_KEYWORDS)
    if not found:
        return ComplianceFinding(
            rule_id="ET05",
            category=ComplianceCategory.ETHICS,
            severity=ComplianceSeverity.CRITICAL,
            status=ComplianceStatus.NA,
            description="No dual-use keywords detected",
        )
    acknowledged = _ethics_acknowledges(
        proposal.ethics_justification,
        _DUAL_USE_KEYWORDS + ["dual use", "security", "misuse"],
    )
    if not acknowledged:
        return ComplianceFinding(
            rule_id="ET05",
            category=ComplianceCategory.ETHICS,
            severity=ComplianceSeverity.CRITICAL,
            status=ComplianceStatus.FAIL,
            description="Dual-use concerns detected but not in ethics section",
            actual_value=f"Keywords: {', '.join(found[:5])}",
            field_path="ethics_justification",
            suggestion="Add dual-use risk assessment to ethics section.",
        )
    return ComplianceFinding(
        rule_id="ET05",
        category=ComplianceCategory.ETHICS,
        severity=ComplianceSeverity.CRITICAL,
        status=ComplianceStatus.PASS,
        description="Dual-use concerns addressed in ethics section",
    )


# --- ET06: Ethics section non-empty when any trigger found ---


@RuleRegistry.register(
    rule_id="ET06",
    category=ComplianceCategory.ETHICS,
    severity=ComplianceSeverity.MAJOR,
    description="Ethics justification should not be empty",
)
def check_et06(proposal, draft=None) -> ComplianceFinding:
    if not proposal.ethics_justification.strip():
        # Check if any ethics-relevant keywords exist
        wp_text = _collect_work_plan_text(proposal)
        all_keywords = (
            _HUMAN_SUBJECTS_KEYWORDS
            + _PERSONAL_DATA_KEYWORDS
            + _HEALTH_DATA_KEYWORDS
            + _ANIMAL_KEYWORDS
        )
        found = _has_keywords(wp_text, all_keywords)
        if found:
            return ComplianceFinding(
                rule_id="ET06",
                category=ComplianceCategory.ETHICS,
                severity=ComplianceSeverity.MAJOR,
                status=ComplianceStatus.FAIL,
                description="Ethics justification is empty but ethical issues detected",
                actual_value=f"Keywords: {', '.join(found[:5])}",
                field_path="ethics_justification",
                suggestion="Add ethics justification addressing detected issues.",
            )
        return ComplianceFinding(
            rule_id="ET06",
            category=ComplianceCategory.ETHICS,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.WARN,
            description="Ethics justification is empty (consider adding one)",
            notes="Even if no ethical issues are detected, a brief statement is recommended.",
        )
    return ComplianceFinding(
        rule_id="ET06",
        category=ComplianceCategory.ETHICS,
        severity=ComplianceSeverity.MAJOR,
        status=ComplianceStatus.PASS,
        description="Ethics justification is present",
        actual_value=f"{len(proposal.ethics_justification)} chars",
    )


# --- ET07: Ethics approval timeline mentioned ---


@RuleRegistry.register(
    rule_id="ET07",
    category=ComplianceCategory.ETHICS,
    severity=ComplianceSeverity.MAJOR,
    description="Ethics approval timeline should be mentioned if ethics issues exist",
)
def check_et07(proposal, draft=None) -> ComplianceFinding:
    wp_text = _collect_work_plan_text(proposal)
    all_triggers = _HUMAN_SUBJECTS_KEYWORDS + _PERSONAL_DATA_KEYWORDS + _HEALTH_DATA_KEYWORDS
    found = _has_keywords(wp_text, all_triggers)
    if not found:
        return ComplianceFinding(
            rule_id="ET07",
            category=ComplianceCategory.ETHICS,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.NA,
            description="No ethics triggers — timeline check not applicable",
        )
    ethics_lower = proposal.ethics_justification.lower()
    timeline_keywords = [
        "month",
        "before",
        "prior to",
        "approval",
        "timeline",
        "schedule",
        "submit",
        "application",
        "committee",
    ]
    if not any(kw in ethics_lower for kw in timeline_keywords):
        return ComplianceFinding(
            rule_id="ET07",
            category=ComplianceCategory.ETHICS,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.FAIL,
            description="Ethics issues detected but no approval timeline in ethics section",
            field_path="ethics_justification",
            suggestion="Add timeline for ethics approval submission.",
        )
    return ComplianceFinding(
        rule_id="ET07",
        category=ComplianceCategory.ETHICS,
        severity=ComplianceSeverity.MAJOR,
        status=ComplianceStatus.PASS,
        description="Ethics approval timeline is mentioned",
    )


# --- ET08: Contradiction between ethics claims and WP activities ---


@RuleRegistry.register(
    rule_id="ET08",
    category=ComplianceCategory.ETHICS,
    severity=ComplianceSeverity.BLOCKER,
    description="No contradiction between ethics claims and work plan activities",
)
def check_et08(proposal, draft=None) -> ComplianceFinding:
    """Check for contradictions: ethics says 'no human subjects' but WP has them."""
    ethics_lower = proposal.ethics_justification.lower()

    # Denial patterns
    denial_patterns = [
        r"no\s+(human\s+subjects?|participants?|personal\s+data)",
        r"does\s+not\s+involve\s+(human|personal|patient|clinical)",
        r"not\s+applicable.*?(human|personal|patient|clinical)",
        r"no\s+ethical\s+issues",
    ]
    has_denial = any(re.search(p, ethics_lower) for p in denial_patterns)

    if not has_denial:
        return ComplianceFinding(
            rule_id="ET08",
            category=ComplianceCategory.ETHICS,
            severity=ComplianceSeverity.BLOCKER,
            status=ComplianceStatus.PASS,
            description="No ethics denial detected — no contradiction possible",
        )

    # Check if WP actually mentions these activities
    wp_text = _collect_work_plan_text(proposal)
    all_triggers = _HUMAN_SUBJECTS_KEYWORDS + _PERSONAL_DATA_KEYWORDS + _HEALTH_DATA_KEYWORDS
    found = _has_keywords(wp_text, all_triggers)
    if found:
        return ComplianceFinding(
            rule_id="ET08",
            category=ComplianceCategory.ETHICS,
            severity=ComplianceSeverity.BLOCKER,
            status=ComplianceStatus.FAIL,
            description="CONTRADICTION: Ethics section denies issues but WP mentions them",
            actual_value=f"WP keywords: {', '.join(found[:5])}",
            field_path="ethics_justification",
            suggestion="Reconcile ethics claims with actual work plan activities.",
        )
    return ComplianceFinding(
        rule_id="ET08",
        category=ComplianceCategory.ETHICS,
        severity=ComplianceSeverity.BLOCKER,
        status=ComplianceStatus.PASS,
        description="Ethics denial consistent with work plan content",
    )
