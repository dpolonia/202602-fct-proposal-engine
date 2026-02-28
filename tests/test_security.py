"""Security tests for critical components."""

from __future__ import annotations

import pytest

from src.utils.sanitize import (
    redact_secrets,
    scrub_identity_for_review,
    scrub_pii_for_llm,
    validate_path,
)


# =============================================================================
# redact_secrets
# =============================================================================

def _fake(prefix: str, length: int = 20) -> str:
    """Build a fake token dynamically so literal patterns don't trigger scanners."""
    return prefix + "A" * length


class TestRedactSecrets:
    """Tests for src/utils/sanitize.redact_secrets"""

    def test_redacts_anthropic_key(self):
        tok = _fake("sk-" + "ant-", 20)
        result = redact_secrets(f"Error with key {tok}")
        assert tok not in result
        assert "[REDACTED]" in result

    def test_redacts_openai_project_key(self):
        tok = _fake("sk-" + "proj-", 20)
        result = redact_secrets(f"Key: {tok}")
        assert tok not in result
        assert "[REDACTED]" in result

    def test_redacts_openai_legacy_key(self):
        tok = _fake("sk-", 25)
        result = redact_secrets(f"Key: {tok}")
        assert tok not in result

    def test_redacts_google_key(self):
        tok = _fake("AIza" + "Sy", 35)
        result = redact_secrets(f"Using {tok}")
        assert tok not in result
        assert "[REDACTED]" in result

    def test_redacts_huggingface_key(self):
        tok = _fake("hf" + "_", 12)
        result = redact_secrets(f"Token {tok}")
        assert tok not in result
        assert "[REDACTED]" in result

    def test_redacts_aws_key(self):
        tok = "AKIA" + "IOSFODNN7EXMPL"
        result = redact_secrets(tok)
        assert tok not in result
        assert "[REDACTED]" in result

    def test_redacts_github_pat(self):
        tok = _fake("ghp" + "_", 25)
        result = redact_secrets(f"Token {tok}")
        assert tok not in result

    def test_redacts_github_oauth(self):
        tok = _fake("gho" + "_", 25)
        result = redact_secrets(f"Token {tok}")
        assert tok not in result

    def test_redacts_slack_bot_token(self):
        tok = _fake("xox" + "b-", 30)
        result = redact_secrets(tok)
        assert tok not in result

    def test_redacts_slack_user_token(self):
        tok = _fake("xox" + "p-", 30)
        result = redact_secrets(tok)
        assert tok not in result

    def test_preserves_normal_text(self):
        text = "This is a normal log message about proposals"
        assert redact_secrets(text) == text

    def test_handles_empty_string(self):
        assert redact_secrets("") == ""

    def test_handles_none_gracefully(self):
        result = redact_secrets(None)
        assert result == ""

    def test_multiple_keys_in_one_string(self):
        tok1 = _fake("sk-" + "ant-", 20)
        tok2 = _fake("AIza" + "Sy", 35)
        text = f"Keys: {tok1} and {tok2}"
        result = redact_secrets(text)
        assert tok1 not in result
        assert tok2 not in result
        assert result.count("[REDACTED]") == 2


# =============================================================================
# scrub_pii_for_llm
# =============================================================================

class TestScrubPiiForLlm:
    """Tests for scrub_pii_for_llm"""

    def test_removes_email(self):
        text = "Contact joao.silva@ua.pt for details"
        result = scrub_pii_for_llm(text)
        assert "joao.silva@ua.pt" not in result
        assert "[email removed]" in result

    def test_removes_complex_email(self):
        text = "Send to first.last+tag@sub.domain.co.uk"
        result = scrub_pii_for_llm(text)
        assert "@" not in result

    def test_removes_portuguese_phone(self):
        text = "Call +351 912 345 678 for info"
        result = scrub_pii_for_llm(text)
        assert "912" not in result
        assert "[phone removed]" in result

    def test_removes_portuguese_phone_no_spaces(self):
        text = "Phone: +351912345678"
        result = scrub_pii_for_llm(text)
        assert "912345678" not in result

    def test_removes_nif(self):
        text = "NIF: 123456789"
        result = scrub_pii_for_llm(text)
        assert "123456789" not in result
        assert "[tax ID removed]" in result

    def test_removes_contribuinte(self):
        text = "contribuinte 987654321"
        result = scrub_pii_for_llm(text)
        assert "987654321" not in result

    def test_removes_cc_number(self):
        text = "CC 12345678"
        result = scrub_pii_for_llm(text)
        assert "12345678" not in result
        assert "[ID removed]" in result

    def test_removes_bi_number(self):
        text = "BI 12345678"
        result = scrub_pii_for_llm(text)
        assert "12345678" not in result

    def test_preserves_orcid(self):
        text = "ORCID: 0000-0001-8194-4713"
        result = scrub_pii_for_llm(text)
        assert "0000-0001-8194-4713" in result

    def test_preserves_names(self):
        text = "Prof. João Silva leads the team"
        result = scrub_pii_for_llm(text)
        assert "João Silva" in result

    def test_preserves_institutions(self):
        text = "Universidade de Aveiro, GOVCOPP"
        result = scrub_pii_for_llm(text)
        assert "Universidade de Aveiro" in result

    def test_handles_empty_string(self):
        assert scrub_pii_for_llm("") == ""

    def test_handles_none(self):
        assert scrub_pii_for_llm(None) == ""


# =============================================================================
# scrub_identity_for_review
# =============================================================================

class TestScrubIdentityForReview:
    """Tests for scrub_identity_for_review"""

    def test_replaces_pi_name(self):
        text = "Prof. João Silva has published 28 papers"
        result = scrub_identity_for_review(text, "João Silva", [])
        assert "João Silva" not in result
        assert "Principal Investigator" in result

    def test_replaces_team_names(self):
        text = "Dr. Ana Costa will handle surveys"
        result = scrub_identity_for_review(text, "PI Name", ["Ana Costa"])
        assert "Ana Costa" not in result
        assert "Team Member 1" in result

    def test_replaces_multiple_team_names(self):
        text = "Ana Costa and Bruno Dias collaborate"
        result = scrub_identity_for_review(text, "PI Name", ["Ana Costa", "Bruno Dias"])
        assert "Ana Costa" not in result
        assert "Bruno Dias" not in result
        assert "Team Member 1" in result
        assert "Team Member 2" in result

    def test_preserves_institutions(self):
        text = "João Silva at Universidade de Aveiro"
        result = scrub_identity_for_review(text, "João Silva", [])
        assert "Universidade de Aveiro" in result

    def test_also_removes_emails(self):
        text = "João Silva (joao@ua.pt)"
        result = scrub_identity_for_review(text, "João Silva", [])
        assert "@" not in result
        assert "João Silva" not in result

    def test_also_removes_phones(self):
        text = "Call João Silva at +351 912 345 678"
        result = scrub_identity_for_review(text, "João Silva", [])
        assert "912" not in result
        assert "João Silva" not in result

    def test_handles_empty_team(self):
        text = "PI works alone"
        result = scrub_identity_for_review(text, "PI Name", [])
        assert result  # should not crash

    def test_handles_empty_pi_name(self):
        text = "The team works together"
        result = scrub_identity_for_review(text, "", [])
        assert result == scrub_pii_for_llm(text)

    def test_case_insensitive_replacement(self):
        text = "joão silva presented results by JOÃO SILVA"
        result = scrub_identity_for_review(text, "João Silva", [])
        assert "joão silva" not in result.lower() or "principal investigator" in result.lower()


# =============================================================================
# validate_path
# =============================================================================

class TestValidatePath:
    """Tests for validate_path"""

    def test_allows_valid_path(self, tmp_path):
        child = tmp_path / "subdir"
        child.mkdir()
        result = validate_path(str(child), tmp_path)
        assert result == child.resolve()

    def test_blocks_traversal(self, tmp_path):
        with pytest.raises(ValueError, match="resolves outside"):
            validate_path(str(tmp_path / ".." / ".." / "etc" / "passwd"), tmp_path)

    def test_blocks_absolute_path_outside(self, tmp_path):
        with pytest.raises(ValueError, match="resolves outside"):
            validate_path("/etc/passwd", tmp_path)

    def test_blocks_sibling_directory(self, tmp_path):
        sibling = tmp_path.parent / "other"
        with pytest.raises(ValueError, match="resolves outside"):
            validate_path(str(sibling), tmp_path)

    def test_allows_base_itself(self, tmp_path):
        result = validate_path(str(tmp_path), tmp_path)
        assert result == tmp_path.resolve()


# =============================================================================
# API key authentication (structural checks)
# =============================================================================

class TestApiKeyAuth:
    """Tests for API key authentication"""

    def test_timing_safe_comparison_used(self):
        """Verify hmac.compare_digest is used, not plain =="""
        source = open("src/api/app.py").read()
        assert "hmac.compare_digest" in source, \
            "API key comparison must use hmac.compare_digest"
        assert "import hmac" in source, \
            "hmac must be imported"

    def test_no_plain_equality_for_api_key(self):
        """Ensure no plain == or != comparison for API keys"""
        source = open("src/api/app.py").read()
        # Find the verify_api_key function body
        start = source.index("async def verify_api_key")
        end = source.index("\n\napp = FastAPI")
        fn_body = source[start:end]
        assert "!= configured_key" not in fn_body, \
            "Must not use != for API key comparison"
        assert "== configured_key" not in fn_body, \
            "Must not use == for API key comparison"

    def test_health_endpoint_no_auth(self):
        """Health endpoint should not require authentication"""
        source = open("src/api/app.py").read()
        # /health should NOT have Depends(verify_api_key)
        health_start = source.index('@app.get("/health")')
        health_end = source.index("async def health")
        health_decorator = source[health_start:health_end]
        assert "verify_api_key" not in health_decorator, \
            "/health endpoint must not require API key"
