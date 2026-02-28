"""
Loads prompt templates from data/prompts/*.yaml.
Templates are cached on first access.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "prompts"


@lru_cache(maxsize=None)
def _load_file(name: str) -> dict:
    path = _PROMPTS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def get_prompt(file: str, key: str) -> str:
    """Load a prompt template from data/prompts/{file}.yaml[{key}]."""
    data = _load_file(file)
    value = data
    for part in key.split("."):
        value = value[part]
    return value.strip()
