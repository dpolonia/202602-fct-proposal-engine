"""
CLI for FCT Proposal Engine.
Defaults from config.yaml; CLI flags override where provided.

    fct-engine generate -i draft.yaml
    fct-engine review   -i proposal.json
    fct-engine pipeline -i draft.yaml -n 3
    fct-engine config   --show
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from src.config.settings import cfg

console = Console()


def _setup_log(verbose: bool):
    level = "DEBUG" if verbose else cfg.log_level
    handlers = [RichHandler(console=console, rich_tracebacks=True)] if cfg.rich_console else []
    logging.basicConfig(level=level, format="%(message)s", handlers=handlers or None)


# =============================================================================
# Root group
# =============================================================================

@click.group()
@click.option("-v", "--verbose", is_flag=True, help="DEBUG logging")
@click.option("-c", "--config", "config_path", default=None,
              help="Path to config.yaml (default: ./config.yaml)")
def cli(verbose, config_path):
    """FCT Proposal Engine — AI-powered proposal generator & peer reviewer."""
    if config_path:
        cfg.reload(Path(config_path))
    _setup_log(verbose)


# =============================================================================
# generate
# =============================================================================

@cli.command()
@click.option("-i", "--input", "input_path", required=True, help="Draft idea (YAML/JSON)")
@click.option("-o", "--output", "output_dir", default=None, help="Output dir (default: from config.yaml)")
def generate(input_path, output_dir):
    """Generate a proposal from a draft idea."""
    console.print(Panel("🔬 [bold]Proposal Generator[/bold]", style="blue"))

    async def _run():
        import yaml
        from src.generators.models import DraftIdea
        from src.generators.proposal_generator import ProposalGenerator

        p = Path(input_path)
        data = yaml.safe_load(p.read_text()) if p.suffix in (".yaml", ".yml") else json.loads(p.read_text())
        draft = DraftIdea(**data)
        gen = ProposalGenerator()

        with console.status("[bold green]Generating…"):
            proposal = await gen.generate(draft)

        out = Path(output_dir or cfg.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        outfile = out / "proposal.json"
        outfile.write_text(proposal.model_dump_json(indent=2))

        _print_char_table(proposal)
        console.print(f"\n✅ Saved: {outfile}")

    asyncio.run(_run())


# =============================================================================
# review
# =============================================================================

@cli.command()
@click.option("-i", "--input", "input_path", required=True, help="Proposal JSON")
@click.option("-o", "--output", "output_dir", default=None, help="Output dir")
def review(input_path, output_dir):
    """Run multi-model peer review on a proposal."""
    console.print(Panel("📋 [bold]AI Peer Review[/bold]", style="yellow"))

    async def _run():
        from src.generators.models import Proposal
        from src.reviewers.panel_reviewer import ReviewPanel

        proposal = Proposal(**json.loads(Path(input_path).read_text()))
        panel = ReviewPanel()

        with console.status("[bold yellow]Reviewing…"):
            consensus = await panel.review(proposal)

        out = Path(output_dir or cfg.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        outfile = out / "review.json"
        outfile.write_text(consensus.model_dump_json(indent=2))

        _print_review_table(consensus)
        console.print(f"\n📄 Saved: {outfile}")

    asyncio.run(_run())


# =============================================================================
# pipeline
# =============================================================================

@cli.command()
@click.option("-i", "--input", "input_path", required=True, help="Draft idea (YAML/JSON)")
@click.option("-o", "--output", "output_dir", default=None, help="Output dir")
@click.option("-n", "--iterations", default=None, type=int,
              help=f"Review-revise cycles (default: {cfg.iterations} from config.yaml)")
def pipeline(input_path, output_dir, iterations):
    """Full pipeline: generate → review → revise (iterative)."""
    n = iterations if iterations is not None else cfg.iterations
    console.print(Panel(f"🚀 [bold]Full Pipeline[/bold] ({n} iterations)", style="green"))

    async def _run():
        from src.generators.pipeline import run_pipeline
        result = await run_pipeline(input_path, output_dir, iterations=n)

        if result.get("history"):
            t = Table(title="Iteration History")
            t.add_column("Iter"); t.add_column("Score", justify="center")
            t.add_column("Decision"); t.add_column("A", justify="center")
            t.add_column("B", justify="center"); t.add_column("C", justify="center")
            for h in result["history"]:
                ws = h.get("weighted_scores", {})
                t.add_row(str(h["iteration"] + 1), f"{h['score']:.1f}", h["decision"],
                          f"{ws.get('A', 0):.1f}", f"{ws.get('B', 0):.1f}", f"{ws.get('C', 0):.1f}")
            console.print(t)

        console.print(f"\n✅ Output: {result['output_dir']}")

    asyncio.run(_run())


# =============================================================================
# config (show / validate current settings)
# =============================================================================

@cli.command("config")
@click.option("--show", is_flag=True, help="Print resolved configuration")
def config_cmd(show):
    """Show or validate the current config.yaml settings."""
    if show:
        t = Table(title="Resolved Configuration")
        t.add_column("Setting", style="cyan"); t.add_column("Value")
        t.add_row("Typology", cfg.typology)
        t.add_row("Principal contractor", cfg.principal_contractor)
        t.add_row("Research units", ", ".join(cfg.default_research_units))
        t.add_row("Generator", f"{cfg.generator.provider.value} / {cfg.generator.model}")
        t.add_row("Consensus LLM", f"{cfg.consensus.provider.value} / {cfg.consensus.model}")
        t.add_row("Revision LLM", f"{cfg.revision.provider.value} / {cfg.revision.model}")
        t.add_row("Panel reviewers", ", ".join(r.id for r in cfg.enabled_reviewers))
        t.add_row("Iterations", str(cfg.iterations))
        t.add_row("Stop on accept", str(cfg.stop_on_accept))
        t.add_row("Scopus enabled", str(cfg.scopus_enabled))
        t.add_row("Output dir", cfg.output_dir)
        t.add_row("Formats", ", ".join(
            f for f, on in [("json", cfg.out_json), ("md", cfg.out_markdown),
                            ("docx", cfg.out_docx), ("char_report", cfg.out_char_report)] if on))
        console.print(t)

        from src.config.settings import secrets
        avail = Table(title="API Key Status")
        avail.add_column("Provider"); avail.add_column("Status")
        for p in ("anthropic", "openai", "google", "huggingface", "scopus"):
            key = getattr(secrets, f"{p}_api_key", "")
            avail.add_row(p, "✅ set" if key else "❌ missing")
        console.print(avail)


# =============================================================================
# Helpers
# =============================================================================

def _print_char_table(proposal):
    t = Table(title="Character Counts")
    t.add_column("Section", style="cyan"); t.add_column("Used", justify="right")
    t.add_column("Limit", justify="right"); t.add_column("Left", justify="right")
    t.add_column("OK?")
    for name, c in proposal.char_count_report().items():
        t.add_row(name, str(c["actual"]), str(c["limit"]), str(c["remaining"]),
                  "✅" if c["remaining"] >= 0 else "❌ OVER")
    console.print(t)


def _print_review_table(consensus):
    t = Table(title="Panel Results")
    t.add_column("Reviewer", style="cyan"); t.add_column("Score", justify="center")
    t.add_column("Decision")
    for r in consensus.individual_reviews:
        t.add_row(r.reviewer_id, f"{r.overall_score:.1f}", r.decision)
    t.add_row("", "", "", end_section=True)
    t.add_row("[bold]CONSENSUS[/bold]", f"[bold]{consensus.consensus_score:.1f}[/bold]",
              f"[bold]{consensus.panel_decision}[/bold]")
    console.print(t)


def main():
    cli()


if __name__ == "__main__":
    main()
