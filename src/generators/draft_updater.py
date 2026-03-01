"""
DraftUpdater: evolves the draft idea based on review feedback.
Saves backups, diffs, and change logs for traceability.
"""

from __future__ import annotations

import difflib
import json
import logging
import re
import shutil
from pathlib import Path

import yaml

from src.config.settings import cfg
from src.generators.models import ConsensusReport, DraftIdea
from src.utils.llm_client import BaseLLMClient, get_llm_for_role
from src.utils.prompt_loader import load_prompt_template

logger = logging.getLogger(__name__)

# Fields in DraftIdea that can be updated from review feedback
UPDATABLE_FIELDS = (
    "research_topic",
    "research_questions",
    "methodology_notes",
    "budget_notes",
    "ethical_considerations",
    "pi_career_summary",
)


class DraftUpdater:
    """Evolves a DraftIdea based on review consensus feedback."""

    def __init__(self, llm: BaseLLMClient | None = None):
        self.llm = llm or get_llm_for_role(cfg.revision)

    async def update_draft(
        self,
        draft: DraftIdea,
        consensus: ConsensusReport,
        version: int,
        output_dir: Path,
    ) -> tuple[DraftIdea, list[dict]]:
        """Update draft fields based on review feedback.

        Returns:
            Tuple of (updated_draft, changes_log).
        """
        prompt = load_prompt_template("draft_update").format(
            research_topic=draft.research_topic[:2000],
            research_questions="; ".join(draft.research_questions),
            methodology_notes=draft.methodology_notes[:1000],
            budget_notes=draft.budget_notes[:500],
            ethical_considerations=draft.ethical_considerations[:500],
            pi_career_summary=draft.pi_career_summary[:1000],
            score=consensus.consensus_score,
            decision=consensus.panel_decision,
            weaknesses="\n".join(f"- {w}" for w in consensus.key_weaknesses[:8]),
            revisions="\n".join(f"- {r}" for r in consensus.priority_revisions[:8]),
            narrative=consensus.panel_narrative[:2000],
        )

        resp = await self.llm.generate(prompt, max_tokens=4000, temperature=0.3)
        changes_log = self._apply_updates(draft, resp.text)
        logger.info(f"  Draft updated: {len(changes_log)} field(s) changed for v{version + 1}")
        return draft, changes_log

    def _apply_updates(self, draft: DraftIdea, response_text: str) -> list[dict]:
        """Parse LLM response and apply updates to draft in-place."""
        try:
            clean = self._extract_json(response_text)
            data = json.loads(clean)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Draft update JSON parse failed: {e}")
            return []

        updated_fields = data.get("updated_fields", {})
        changes_log = data.get("changes_log", [])

        for field, value in updated_fields.items():
            if field not in UPDATABLE_FIELDS:
                continue
            if not value:
                continue
            setattr(draft, field, value)

        return changes_log

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract JSON from LLM output, stripping markdown fences."""
        clean = text.strip()
        m = re.search(r"```(?:json)?\s*\n?(.*?)```", clean, re.DOTALL)
        if m:
            return m.group(1).strip()
        for start_char, end_char in [("{", "}"), ("[", "]")]:
            start = clean.find(start_char)
            end = clean.rfind(end_char)
            if start != -1 and end > start:
                return clean[start:end + 1]
        return clean

    @staticmethod
    def save_backup(
        draft: DraftIdea,
        version: int,
        output_dir: Path,
        original_path: Path | None = None,
    ) -> None:
        """Save a YAML backup of the draft before updating it.

        On the first call (version == 1), also copies the original input file
        verbatim as original_draft.yaml.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        if version == 1 and original_path and original_path.exists():
            dest = output_dir / "original_draft.yaml"
            if not dest.exists():
                shutil.copy2(original_path, dest)
                logger.info(f"  Saved: {dest}")

        backup_path = output_dir / f"draft_pre_v{version + 1}.yaml"
        draft_dict = draft.model_dump(mode="json")
        backup_path.write_text(
            yaml.dump(draft_dict, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        logger.info(f"  Saved: {backup_path}")

    @staticmethod
    def save_diff(
        old_draft: DraftIdea,
        new_draft: DraftIdea,
        version: int,
        output_dir: Path,
    ) -> None:
        """Save a unified diff between the old and new draft YAML serializations."""
        output_dir.mkdir(parents=True, exist_ok=True)

        old_yaml = yaml.dump(old_draft.model_dump(mode="json"),
                             default_flow_style=False, allow_unicode=True)
        new_yaml = yaml.dump(new_draft.model_dump(mode="json"),
                             default_flow_style=False, allow_unicode=True)

        diff = difflib.unified_diff(
            old_yaml.splitlines(keepends=True),
            new_yaml.splitlines(keepends=True),
            fromfile=f"draft_v{version}.yaml",
            tofile=f"draft_v{version + 1}.yaml",
        )
        diff_text = "".join(diff)
        if diff_text:
            diff_path = output_dir / f"draft_v{version}_to_v{version + 1}.diff"
            diff_path.write_text(diff_text, encoding="utf-8")
            logger.info(f"  Saved: {diff_path}")

    @staticmethod
    def save_changes_log(
        changes_log: list[dict],
        version: int,
        output_dir: Path,
    ) -> None:
        """Save the changes log as JSON."""
        if not changes_log:
            return
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"draft_changes_v{version}_to_v{version + 1}.json"
        path.write_text(json.dumps(changes_log, indent=2), encoding="utf-8")
        logger.info(f"  Saved: {path}")
