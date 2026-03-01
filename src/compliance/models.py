"""
Compliance validation data models.

Pydantic models for compliance findings, reports, and deltas.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import IntEnum, StrEnum

from pydantic import BaseModel, Field


class ComplianceSeverity(IntEnum):
    """Severity of a compliance violation. Lower = more severe."""

    BLOCKER = 1
    CRITICAL = 2
    MAJOR = 3
    MINOR = 4


class ComplianceStatus(StrEnum):
    """Status of a single compliance check."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    NA = "N/A"
    SKIP = "SKIP"


class ComplianceCategory(StrEnum):
    """Category of compliance rules."""

    ELIGIBILITY = "E"
    CHAR_LIMITS = "CL"
    WORK_PLAN = "WP"
    BUDGET = "BG"
    UA_INTERNAL = "UA"
    ETHICS = "ET"
    EVALUATION = "EV"


class ComplianceFinding(BaseModel):
    """Result of a single compliance rule check."""

    rule_id: str = ""
    category: ComplianceCategory = ComplianceCategory.ELIGIBILITY
    severity: ComplianceSeverity = ComplianceSeverity.MINOR
    status: ComplianceStatus = ComplianceStatus.PASS
    description: str = ""
    notes: str = ""
    actual_value: str = ""
    expected_value: str = ""
    field_path: str = ""
    suggestion: str = ""


class ComplianceDelta(BaseModel):
    """Changes between two consecutive compliance reports."""

    resolved: list[str] = Field(default_factory=list)
    persists: list[str] = Field(default_factory=list)
    new_failures: list[str] = Field(default_factory=list)
    regressions: list[str] = Field(default_factory=list)


class ComplianceRecommendation(StrEnum):
    """Overall recommendation based on compliance status."""

    RESOLVE_BLOCKERS = "RESOLVE_BLOCKERS"
    RESOLVE_CRITICAL = "RESOLVE_CRITICAL"
    PROCEED_TO_REVIEW = "PROCEED_TO_REVIEW"
    MINOR_POLISH = "MINOR_POLISH"


class ComplianceReport(BaseModel):
    """Full compliance validation report for one proposal version."""

    version: int = 0
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    typology: str = ""
    findings: list[ComplianceFinding] = Field(default_factory=list)

    # Aggregate counts
    total: int = 0
    passed: int = 0
    failed: int = 0
    warned: int = 0
    na: int = 0
    skipped: int = 0
    blocker_count: int = 0
    critical_count: int = 0
    major_count: int = 0
    minor_count: int = 0

    recommendation: ComplianceRecommendation = ComplianceRecommendation.PROCEED_TO_REVIEW
    delta: ComplianceDelta | None = None

    def compute_aggregates(self) -> None:
        """Recompute aggregate counts from findings list."""
        self.total = len(self.findings)
        self.passed = sum(1 for f in self.findings if f.status == ComplianceStatus.PASS)
        self.failed = sum(1 for f in self.findings if f.status == ComplianceStatus.FAIL)
        self.warned = sum(1 for f in self.findings if f.status == ComplianceStatus.WARN)
        self.na = sum(1 for f in self.findings if f.status == ComplianceStatus.NA)
        self.skipped = sum(1 for f in self.findings if f.status == ComplianceStatus.SKIP)

        failed_findings = [f for f in self.findings if f.status == ComplianceStatus.FAIL]
        self.blocker_count = sum(
            1 for f in failed_findings if f.severity == ComplianceSeverity.BLOCKER
        )
        self.critical_count = sum(
            1 for f in failed_findings if f.severity == ComplianceSeverity.CRITICAL
        )
        self.major_count = sum(1 for f in failed_findings if f.severity == ComplianceSeverity.MAJOR)
        self.minor_count = sum(1 for f in failed_findings if f.severity == ComplianceSeverity.MINOR)

        # Recommendation cascade
        if self.blocker_count > 0:
            self.recommendation = ComplianceRecommendation.RESOLVE_BLOCKERS
        elif self.critical_count > 0:
            self.recommendation = ComplianceRecommendation.RESOLVE_CRITICAL
        elif self.major_count > 0:
            self.recommendation = ComplianceRecommendation.PROCEED_TO_REVIEW
        else:
            self.recommendation = ComplianceRecommendation.MINOR_POLISH
