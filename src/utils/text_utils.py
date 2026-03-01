"""
Text utilities for safe character-limit handling.
Prevents mid-sentence and mid-word truncation in proposal sections.
"""

from __future__ import annotations

import re


def safe_truncate(text: str, max_chars: int) -> str:
    """Truncate text to max_chars without cutting mid-sentence or mid-word.

    Strategy:
    1. Find the last sentence boundary (. ? ! followed by whitespace) within limit.
    2. Fall back to the last word boundary (whitespace) within limit.
    3. Last resort: hard cut at max_chars.
    """
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]

    # Try sentence boundary: last '. ', '? ', '! ' within limit
    sentence_end = re.search(r"[.?!]\s", truncated[::-1])
    if sentence_end:
        cut_pos = max_chars - sentence_end.start()
        # Include the punctuation but not the trailing space
        candidate = text[:cut_pos].rstrip()
        if len(candidate) >= max_chars * 0.5:  # Don't lose more than half
            return candidate

    # Try word boundary
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.5:
        return text[:last_space].rstrip()

    # Hard cut as last resort
    return truncated


def safe_limit(limit: int, buffer_pct: float = 0.05, min_buffer: int = 200) -> int:
    """Return a reduced character limit that leaves a safety buffer.

    The buffer is max(limit * buffer_pct, min_buffer), ensuring the LLM
    targets a slightly lower count so that final output stays within the
    hard limit even after minor formatting differences.
    """
    buffer = max(int(limit * buffer_pct), min_buffer)
    return max(limit - buffer, 1)
