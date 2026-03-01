"""Tests for src.utils.json_utils.extract_json()."""

import json

from src.utils.json_utils import extract_json


class TestExtractJsonClean:
    """Clean JSON passthrough."""

    def test_simple_object(self):
        raw = '{"key": "value"}'
        assert json.loads(extract_json(raw)) == {"key": "value"}

    def test_simple_array(self):
        raw = "[1, 2, 3]"
        assert json.loads(extract_json(raw)) == [1, 2, 3]

    def test_nested_object(self):
        raw = '{"a": {"b": {"c": 1}}, "d": [1, {"e": 2}]}'
        result = json.loads(extract_json(raw))
        assert result["a"]["b"]["c"] == 1
        assert result["d"][1]["e"] == 2


class TestExtractJsonMarkdownFences:
    """JSON wrapped in markdown fences."""

    def test_json_fence(self):
        raw = '```json\n{"key": "value"}\n```'
        assert json.loads(extract_json(raw)) == {"key": "value"}

    def test_plain_fence(self):
        raw = '```\n{"key": "value"}\n```'
        assert json.loads(extract_json(raw)) == {"key": "value"}

    def test_fence_with_leading_text(self):
        raw = 'Here is the JSON:\n```json\n{"key": "value"}\n```'
        assert json.loads(extract_json(raw)) == {"key": "value"}

    def test_fence_with_trailing_text(self):
        raw = '```json\n{"key": "value"}\n```\nHope this helps!'
        assert json.loads(extract_json(raw)) == {"key": "value"}


class TestExtractJsonSurroundingText:
    """JSON with explanation text before/after (the 'Extra data' case)."""

    def test_text_before_json(self):
        raw = 'Here are the updates:\n{"updated_fields": {"research_topic": "new"}}'
        result = json.loads(extract_json(raw))
        assert result["updated_fields"]["research_topic"] == "new"

    def test_text_after_json(self):
        raw = '{"key": "value"}\n\nI hope this addresses the reviewer concerns.'
        assert json.loads(extract_json(raw)) == {"key": "value"}

    def test_text_before_and_after(self):
        raw = (
            "Based on the review feedback, here are my updates:\n\n"
            '{"updated_fields": {"research_topic": "improved topic"}, '
            '"changes_log": []}\n\n'
            "These changes address the key weaknesses identified by the panel."
        )
        result = json.loads(extract_json(raw))
        assert result["updated_fields"]["research_topic"] == "improved topic"


class TestExtractJsonBracesInStrings:
    """Braces inside string values (the 'Expecting delimiter' regression)."""

    def test_curly_braces_in_value(self):
        raw = '{"formula": "f(x) = {x + 1}", "ok": true}'
        result = json.loads(extract_json(raw))
        assert result["formula"] == "f(x) = {x + 1}"
        assert result["ok"] is True

    def test_nested_braces_in_value(self):
        raw = '{"code": "if (x) { return {a: 1}; }", "valid": true}'
        result = json.loads(extract_json(raw))
        assert result["code"] == "if (x) { return {a: 1}; }"

    def test_brackets_in_value(self):
        raw = '{"note": "array notation: [1, 2, 3]", "items": [1]}'
        result = json.loads(extract_json(raw))
        assert result["note"] == "array notation: [1, 2, 3]"

    def test_escaped_quotes_in_value(self):
        raw = r'{"text": "He said \"hello {world}\"", "ok": true}'
        result = json.loads(extract_json(raw))
        assert "hello {world}" in result["text"]

    def test_real_regression_case(self):
        """Simulate the actual failure: JSON followed by extra explanation."""
        json_part = json.dumps(
            {
                "updated_fields": {
                    "methodology_notes": "Use mixed methods {qualitative + quantitative}"
                },
                "changes_log": [
                    {
                        "field": "methodology_notes",
                        "review_comment": "weak",
                        "change_description": "added",
                    }
                ],
            }
        )
        raw = json_part + "\n\nNote: The braces in {qualitative + quantitative} denote a set."
        result = json.loads(extract_json(raw))
        assert "qualitative" in result["updated_fields"]["methodology_notes"]


class TestExtractJsonArrays:
    """Array extraction."""

    def test_array_of_objects(self):
        raw = '[{"id": 1}, {"id": 2}]'
        result = json.loads(extract_json(raw))
        assert len(result) == 2
        assert result[0]["id"] == 1

    def test_array_with_surrounding_text(self):
        raw = 'The tasks are:\n[{"number": 1, "name": "Literature Review"}]\nEnd.'
        result = json.loads(extract_json(raw))
        assert result[0]["number"] == 1

    def test_array_preferred_when_first(self):
        """When [ appears before {, array is extracted."""
        raw = '[{"a": 1}]'
        result = json.loads(extract_json(raw))
        assert isinstance(result, list)


class TestExtractJsonDeeplyNested:
    """Deeply nested objects."""

    def test_deep_nesting(self):
        raw = '{"a": {"b": {"c": {"d": {"e": "deep"}}}}}'
        result = json.loads(extract_json(raw))
        assert result["a"]["b"]["c"]["d"]["e"] == "deep"

    def test_mixed_nesting(self):
        raw = '{"items": [{"sub": [{"val": 1}]}, {"sub": [{"val": 2}]}]}'
        result = json.loads(extract_json(raw))
        assert result["items"][1]["sub"][0]["val"] == 2


class TestExtractJsonNoValidJson:
    """No valid JSON returns input as-is."""

    def test_plain_text(self):
        raw = "This is just plain text with no JSON at all."
        assert extract_json(raw) == raw

    def test_empty_string(self):
        assert extract_json("") == ""

    def test_whitespace_only(self):
        assert extract_json("   \n  ").strip() == ""
