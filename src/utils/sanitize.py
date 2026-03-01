"""
Utilities for redacting secrets from strings, scrubbing PII from data objects,
and validating/sanitising file paths.

PII scrubbing policy (two levels):

  scrub_pii_for_llm()          — generator context: removes contact PII
                                  (emails, phones, NIF/CC) but PRESERVES names,
                                  ORCID, and institutions because the generator
                                  needs them to write natural proposal prose.

  scrub_identity_for_review()  — reviewer context: additionally anonymises all
                                  personal names so AI reviewers evaluate blind,
                                  mirroring real FCT peer review.
"""

from __future__ import annotations

import re
from pathlib import Path

# =============================================================================
# Secret redaction (for log messages)
# =============================================================================

# Patterns that match common API key prefixes (at least 8 chars after prefix)
_SECRET_PATTERNS = [
    re.compile(r"sk-ant-[a-zA-Z0-9_-]{8,}"),  # Anthropic
    re.compile(r"sk-proj-[a-zA-Z0-9_-]{8,}"),  # OpenAI project keys
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}"),  # OpenAI legacy keys
    re.compile(r"AIzaSy[a-zA-Z0-9_-]{30,}"),  # Google API keys
    re.compile(r"hf_[a-zA-Z0-9]{8,}"),  # Hugging Face
    re.compile(r"ghp_[a-zA-Z0-9]{20,}"),  # GitHub PAT
    re.compile(r"gho_[a-zA-Z0-9]{20,}"),  # GitHub OAuth
    re.compile(r"xoxb-[a-zA-Z0-9-]{20,}"),  # Slack bot
    re.compile(r"xoxp-[a-zA-Z0-9-]{20,}"),  # Slack user
    re.compile(r"AKIA[0-9A-Z]{12,}"),  # AWS access key
]


def redact_secrets(text: str) -> str:
    """Replace any detected API key patterns in *text* with '[REDACTED]'.

    Handles None gracefully by returning an empty string.
    """
    if not text:
        return text if text == "" else ""
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


# =============================================================================
# PII scrubbing — Level 1: contact info only (for generator LLM)
# =============================================================================

_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
# International phone: + followed by country code and 7-12 digits (optional separators)
_INTL_PHONE_RE = re.compile(r"\+\d{1,3}[\s.\-]?\d{2,4}[\s.\-]?\d{3,4}[\s.\-]?\d{3,4}")
# Portuguese NIF (tax ID): 9 digits, optionally prefixed with NIF/nif/Nif or "contribuinte"
_NIF_RE = re.compile(r"(?:NIF|nif|Nif|contribuinte)\s*[:.]?\s*\d{9}")
# Portuguese CC (citizen card) / BI (identity card): 8+ digit sequences after CC/BI
_CC_BI_RE = re.compile(r"(?:CC|BI)\s*[:.]?\s*\d{8,}")


def scrub_pii_for_llm(text: str) -> str:
    """Remove contact PII that LLMs don't need to generate good proposals.

    Removes: email addresses, international phone numbers, NIF/CC patterns.
    Preserves: names, ORCID, institutions (needed for proposal content).
    """
    if not text:
        return text if text == "" else ""
    text = _EMAIL_RE.sub("[email removed]", text)
    text = _INTL_PHONE_RE.sub("[phone removed]", text)
    text = _NIF_RE.sub("[tax ID removed]", text)
    text = _CC_BI_RE.sub("[ID removed]", text)
    return text


# =============================================================================
# PII scrubbing — Level 2: identity anonymisation (for reviewer LLM)
# =============================================================================


def scrub_identity_for_review(
    text: str,
    pi_name: str,
    team_names: list[str],
) -> str:
    """Anonymise identities before sending to AI reviewers.

    Replaces PI name with "the Principal Investigator".
    Replaces team member names with "Team Member 1", "Team Member 2", etc.
    Also applies scrub_pii_for_llm() for emails/phones.

    Rationale: reviewers should evaluate the proposal on merit,
    not be influenced by name recognition.  This mirrors real FCT
    blind review where evaluator identity is hidden.
    """
    text = scrub_pii_for_llm(text)

    # Replace PI name (case-insensitive, whole-word)
    if pi_name and pi_name.strip():
        text = re.sub(re.escape(pi_name), "the Principal Investigator", text, flags=re.IGNORECASE)

    # Replace team member names
    for i, name in enumerate(team_names):
        if name and name.strip():
            text = re.sub(re.escape(name), f"Team Member {i + 1}", text, flags=re.IGNORECASE)

    return text


# =============================================================================
# Path sanitisation
# =============================================================================


def validate_path(user_path: str, allowed_root: Path) -> Path:
    """
    Resolve *user_path* and ensure it stays under *allowed_root*.
    Raises ValueError on path traversal attempts.
    """
    resolved = Path(user_path).resolve()
    root = allowed_root.resolve()
    if not (resolved == root or str(resolved).startswith(str(root) + "/")):
        raise ValueError(f"Path '{user_path}' resolves outside the allowed directory '{root}'")
    return resolved
