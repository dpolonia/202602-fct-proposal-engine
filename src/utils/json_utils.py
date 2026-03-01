"""
Robust JSON extraction from LLM output.

Replaces the fragile `find("{") / rfind("}")` pattern that fails when
string values inside JSON contain literal braces.

Algorithm: character-by-character walk that tracks whether we're inside
a JSON string (respecting `\"` escapes) and counts brace/bracket depth
to find the matching closing delimiter.
"""

from __future__ import annotations

import re


def extract_json(text: str) -> str:
    """Extract the first complete JSON object or array from *text*.

    Handles:
    - Clean JSON passthrough
    - JSON wrapped in markdown ``​`json ... `​`` fences
    - JSON with explanation text before/after
    - Braces inside string values (the key regression that broke rfind)
    - Nested objects and arrays

    Returns the extracted JSON substring, or *text* unchanged if no valid
    JSON boundaries are found.
    """
    clean = text.strip()

    # Strip markdown fences first
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", clean, re.DOTALL)
    if m:
        clean = m.group(1).strip()

    # Find the first '{' or '[' — whichever comes first
    obj_start = clean.find("{")
    arr_start = clean.find("[")

    if obj_start == -1 and arr_start == -1:
        return text  # no JSON boundaries found

    # Pick whichever delimiter appears first
    if obj_start == -1:
        start = arr_start
    elif arr_start == -1:
        start = obj_start
    else:
        start = min(obj_start, arr_start)

    open_char = clean[start]
    close_char = "}" if open_char == "{" else "]"

    # Walk character by character with string-awareness
    end = _find_matching_close(clean, start, open_char, close_char)
    if end != -1:
        return clean[start : end + 1]

    return text  # fallback: return original


def _find_matching_close(text: str, start: int, open_char: str, close_char: str) -> int:
    """Find the position of the closing delimiter that matches *open_char* at *start*.

    Respects JSON string quoting (double-quotes with backslash escapes) so
    braces/brackets inside string values are not miscounted.

    Returns the index of the matching close character, or -1 if not found.
    """
    depth = 0
    in_string = False
    i = start

    while i < len(text):
        ch = text[i]

        if in_string:
            if ch == "\\" and i + 1 < len(text):
                i += 2  # skip escaped character
                continue
            if ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == open_char:
                depth += 1
            elif ch == close_char:
                depth -= 1
                if depth == 0:
                    return i

        i += 1

    return -1
