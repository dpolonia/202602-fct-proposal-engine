"""
Decorator-based rule registry for compliance checks.

Each rule file registers its checks on import via @RuleRegistry.register().
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from src.compliance.models import (
    ComplianceCategory,
    ComplianceFinding,
    ComplianceSeverity,
)

logger = logging.getLogger(__name__)


@dataclass
class RuleDefinition:
    """Metadata + callable for a single compliance rule."""

    rule_id: str
    category: ComplianceCategory
    severity: ComplianceSeverity
    description: str
    check_fn: Callable[..., ComplianceFinding | list[ComplianceFinding]]
    applicable_typologies: list[str] = field(default_factory=lambda: ["SR&TD", "PEX"])
    requires_draft: bool = False
    auto_checkable: bool = True


class RuleRegistry:
    """Central registry for all compliance rules."""

    _rules: dict[str, RuleDefinition] = {}

    @classmethod
    def register(
        cls,
        rule_id: str,
        category: ComplianceCategory,
        severity: ComplianceSeverity,
        description: str,
        applicable_typologies: list[str] | None = None,
        requires_draft: bool = False,
        auto_checkable: bool = True,
    ) -> Callable:
        """Decorator to register a compliance rule function."""

        def decorator(fn: Callable) -> Callable:
            cls._rules[rule_id] = RuleDefinition(
                rule_id=rule_id,
                category=category,
                severity=severity,
                description=description,
                check_fn=fn,
                applicable_typologies=(applicable_typologies or ["SR&TD", "PEX"]),
                requires_draft=requires_draft,
                auto_checkable=auto_checkable,
            )
            return fn

        return decorator

    @classmethod
    def get_all(cls) -> dict[str, RuleDefinition]:
        """Return all registered rules."""
        return dict(cls._rules)

    @classmethod
    def get_by_category(
        cls,
        category: ComplianceCategory,
    ) -> dict[str, RuleDefinition]:
        """Return rules filtered by category."""
        return {k: v for k, v in cls._rules.items() if v.category == category}

    @classmethod
    def get(cls, rule_id: str) -> RuleDefinition | None:
        """Return a single rule by ID."""
        return cls._rules.get(rule_id)

    @classmethod
    def clear(cls) -> None:
        """Clear all registered rules (for testing)."""
        cls._rules.clear()
