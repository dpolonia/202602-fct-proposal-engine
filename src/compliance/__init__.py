"""
FCT Compliance Validation Layer.

Automated compliance checks for FCT PTDC 2025 proposals covering:
  - Character limits (CL01-CL28)
  - Eligibility (E01-E11)
  - Work plan consistency (WP01-WP14)
  - Budget arithmetic (BG01-BG10)
  - UA internal rules (UA01-UA13)
  - Ethics (ET01-ET08)
  - Evaluation alignment (EV01-EV09)
"""

# Import rule files to trigger decorator registration
from src.compliance import (
    rules_budget,  # noqa: F401
    rules_char_limits,  # noqa: F401
    rules_eligibility,  # noqa: F401
    rules_ethics,  # noqa: F401
    rules_evaluation,  # noqa: F401
    rules_ua_internal,  # noqa: F401
    rules_work_plan,  # noqa: F401
)

# Re-export main classes
from src.compliance.models import (  # noqa: F401
    ComplianceCategory,
    ComplianceDelta,
    ComplianceFinding,
    ComplianceRecommendation,
    ComplianceReport,
    ComplianceSeverity,
    ComplianceStatus,
)
from src.compliance.registry import RuleRegistry  # noqa: F401
from src.compliance.validator import ComplianceValidator  # noqa: F401

__all__ = [
    "ComplianceValidator",
    "ComplianceReport",
    "ComplianceFinding",
    "ComplianceSeverity",
    "ComplianceStatus",
    "ComplianceCategory",
    "ComplianceDelta",
    "ComplianceRecommendation",
    "RuleRegistry",
]
