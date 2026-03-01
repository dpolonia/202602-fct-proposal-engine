"""Tests for DraftUpdater JSON parsing, field application, and retry logic."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.generators.draft_updater import UPDATABLE_FIELDS, DraftUpdater
from src.generators.models import DraftIdea
from src.utils.llm_client import LLMProvider, LLMResponse


def _make_draft(**overrides) -> DraftIdea:
    """Create a minimal DraftIdea for testing."""
    defaults = {
        "title": "Test Proposal",
        "research_topic": "Original research topic about AI governance.",
        "research_questions": ["RQ1: How?", "RQ2: Why?"],
        "methodology_notes": "Mixed methods.",
        "budget_notes": "Standard budget.",
        "ethical_considerations": "No ethics issues.",
        "pi_career_summary": "10 years experience.",
    }
    defaults.update(overrides)
    return DraftIdea(**defaults)


def _make_llm_response(text: str) -> LLMResponse:
    return LLMResponse(
        text=text,
        model="test-model",
        provider=LLMProvider.ANTHROPIC,
        input_tokens=100,
        output_tokens=200,
    )


class TestApplyUpdatesValidJson:
    """_apply_updates with valid JSON — fields are set on draft."""

    @pytest.mark.asyncio
    async def test_basic_field_update(self):
        draft = _make_draft()
        updater = DraftUpdater(llm=MagicMock())

        response = json.dumps(
            {
                "updated_fields": {
                    "research_topic": "Improved AI governance research topic.",
                    "methodology_notes": "Strengthened mixed methods approach.",
                },
                "changes_log": [
                    {
                        "field": "research_topic",
                        "review_comment": "too vague",
                        "change_description": "added specificity",
                    },
                ],
            }
        )

        changes = await updater._apply_updates(draft, response)
        assert draft.research_topic == "Improved AI governance research topic."
        assert draft.methodology_notes == "Strengthened mixed methods approach."
        assert len(changes) == 1
        assert changes[0]["field"] == "research_topic"

    @pytest.mark.asyncio
    async def test_research_questions_list(self):
        draft = _make_draft()
        updater = DraftUpdater(llm=MagicMock())

        response = json.dumps(
            {
                "updated_fields": {
                    "research_questions": [
                        "RQ1: How does AI affect governance?",
                        "RQ2: What frameworks exist?",
                        "RQ3: New question",
                    ],
                },
                "changes_log": [],
            }
        )

        await updater._apply_updates(draft, response)
        assert len(draft.research_questions) == 3
        assert "New question" in draft.research_questions[2]


class TestApplyUpdatesMarkdownWrapped:
    """_apply_updates with markdown-wrapped JSON — still works."""

    @pytest.mark.asyncio
    async def test_fenced_json(self):
        draft = _make_draft()
        updater = DraftUpdater(llm=MagicMock())

        response = (
            "```json\n"
            '{"updated_fields": {"budget_notes": "Revised budget."}, '
            '"changes_log": []}\n'
            "```"
        )

        _changes = await updater._apply_updates(draft, response)
        assert draft.budget_notes == "Revised budget."

    @pytest.mark.asyncio
    async def test_json_with_surrounding_text(self):
        draft = _make_draft()
        updater = DraftUpdater(llm=MagicMock())

        response = (
            "Here are the updates based on the review:\n\n"
            '{"updated_fields": {"ethical_considerations": "Enhanced ethics."}, '
            '"changes_log": [{"field": "ethical_considerations", '
            '"review_comment": "weak", "change_description": "strengthened"}]}\n\n'
            "I hope these address the concerns."
        )

        changes = await updater._apply_updates(draft, response)
        assert draft.ethical_considerations == "Enhanced ethics."
        assert len(changes) == 1


class TestApplyUpdatesMalformedRetry:
    """_apply_updates with malformed JSON triggers retry, retry succeeds."""

    @pytest.mark.asyncio
    async def test_retry_on_parse_failure(self):
        draft = _make_draft()
        mock_llm = AsyncMock()

        # Repair call returns valid JSON
        repair_response = _make_llm_response(
            json.dumps(
                {
                    "updated_fields": {"research_topic": "Repaired topic."},
                    "changes_log": [
                        {
                            "field": "research_topic",
                            "review_comment": "fix",
                            "change_description": "repaired",
                        }
                    ],
                }
            )
        )
        mock_llm.generate_json = AsyncMock(return_value=repair_response)

        updater = DraftUpdater(llm=mock_llm)

        # Initial response is broken JSON
        broken = '{"updated_fields": {"research_topic": "has {braces} inside'

        changes = await updater._apply_updates(draft, broken)
        assert draft.research_topic == "Repaired topic."
        assert len(changes) == 1
        # Verify repair was called
        mock_llm.generate_json.assert_called_once()


class TestApplyUpdatesUnparseable:
    """_apply_updates with totally unparseable text → retry also fails → returns []."""

    @pytest.mark.asyncio
    async def test_total_failure_returns_empty(self):
        draft = _make_draft()
        original_topic = draft.research_topic
        mock_llm = AsyncMock()

        # Repair also fails
        mock_llm.generate_json = AsyncMock(
            return_value=_make_llm_response("Still not valid JSON at all!")
        )

        updater = DraftUpdater(llm=mock_llm)

        changes = await updater._apply_updates(draft, "Completely unparseable garbage")
        assert changes == []
        assert draft.research_topic == original_topic  # unchanged


class TestApplyUpdatesFieldFiltering:
    """Only updatable fields are applied (unknown fields ignored)."""

    @pytest.mark.asyncio
    async def test_unknown_fields_ignored(self):
        draft = _make_draft()
        updater = DraftUpdater(llm=MagicMock())

        response = json.dumps(
            {
                "updated_fields": {
                    "research_topic": "Updated topic.",
                    "title": "SHOULD NOT CHANGE",
                    "nonexistent_field": "ignored",
                },
                "changes_log": [],
            }
        )

        await updater._apply_updates(draft, response)
        assert draft.research_topic == "Updated topic."
        assert draft.title == "Test Proposal"  # unchanged — not in UPDATABLE_FIELDS

    @pytest.mark.asyncio
    async def test_empty_values_ignored(self):
        draft = _make_draft()
        updater = DraftUpdater(llm=MagicMock())

        response = json.dumps(
            {
                "updated_fields": {
                    "research_topic": "",
                    "methodology_notes": "Updated notes.",
                },
                "changes_log": [],
            }
        )

        original_topic = draft.research_topic
        await updater._apply_updates(draft, response)
        assert draft.research_topic == original_topic  # empty value skipped
        assert draft.methodology_notes == "Updated notes."

    def test_updatable_fields_constant(self):
        """Verify the UPDATABLE_FIELDS tuple matches expected fields."""
        for field in UPDATABLE_FIELDS:
            assert hasattr(DraftIdea.model_fields, "__contains__")
            assert field in DraftIdea.model_fields, f"{field} not in DraftIdea"
