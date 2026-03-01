"""
Loads prompt templates from data/prompts/*.yaml and data/prompts/*.txt.
Templates are cached on first access.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import yaml

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "prompts"


@cache
def _load_yaml(name: str) -> dict:
    path = _PROMPTS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@cache
def _load_txt(name: str) -> str:
    path = _PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def get_prompt(file: str, key: str) -> str:
    """Load a prompt template.

    For YAML files: data/prompts/{file}.yaml → nested key lookup via dot notation.
    For txt files:  data/prompts/{file}.txt  → returns full file content (key ignored).
    """
    # Try .txt first (flat file — key is unused)
    txt_path = _PROMPTS_DIR / f"{file}.txt"
    if txt_path.exists():
        return _load_txt(file)
    # Fall back to YAML with nested key lookup
    data = _load_yaml(file)
    value = data
    for part in key.split("."):
        value = value[part]
    return value.strip()


def load_prompt_template(name: str) -> str:
    """Load a .txt prompt template from data/prompts/{name}.txt."""
    return _load_txt(name)
