"""
FastAPI application.  All settings from config.yaml and .env.
Includes /config endpoint so users can inspect resolved settings.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config.fct_constants import CALL_DATES, CHAR_LIMITS, EVAL_CRITERIA, TYPOLOGY_RULES
from src.config.settings import cfg, secrets
from src.generators.models import DraftIdea, Proposal

logger = logging.getLogger(__name__)

app = FastAPI(
    title="FCT Proposal Engine API",
    description="AI-powered proposal generator & multi-model peer reviewer for FCT PTDC 2025",
    version="0.2.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

jobs: dict[str, dict] = {}


class JobResponse(BaseModel):
    job_id: str
    status: str
    message: str


class PipelineRequest(BaseModel):
    draft: DraftIdea
    iterations: int | None = None  # None = use config.yaml default


# =============================================================================
# Endpoints
# =============================================================================

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "ts": datetime.utcnow().isoformat()}


@app.get("/config")
async def get_config() -> dict:
    """Return resolved user settings (no secrets)."""
    return {
        "project": {
            "typology": cfg.typology,
            "principal_contractor": cfg.principal_contractor,
            "research_units": cfg.default_research_units,
        },
        "llm": {
            "generator": {"provider": cfg.generator.provider.value, "model": cfg.generator.model},
            "consensus": {"provider": cfg.consensus.provider.value, "model": cfg.consensus.model},
            "revision": {"provider": cfg.revision.provider.value, "model": cfg.revision.model},
        },
        "review_panel": [
            {"id": r.id, "provider": r.provider.value, "model": r.model,
             "perspective": r.perspective, "enabled": r.enabled}
            for r in cfg.review_panel
        ],
        "pipeline": {
            "iterations": cfg.iterations,
            "stop_on_accept": cfg.stop_on_accept,
            "max_concurrent_reviews": cfg.max_concurrent_reviews,
        },
        "scopus": {"enabled": cfg.scopus_enabled, "max_results": cfg.scopus_max_results,
                    "year_from": cfg.scopus_year_from},
        "output": {"dir": cfg.output_dir, "json": cfg.out_json, "markdown": cfg.out_markdown,
                    "docx": cfg.out_docx, "char_report": cfg.out_char_report},
        "api_keys_set": {p: secrets.has_key(p) for p in ("anthropic", "openai", "google", "huggingface")},
    }


@app.get("/rules")
async def get_rules() -> dict:
    return {
        "typologies": {k.value: v.__dict__ for k, v in TYPOLOGY_RULES.items()},
        "character_limits": CHAR_LIMITS.__dict__,
        "evaluation_criteria": EVAL_CRITERIA.__dict__,
        "call_dates": CALL_DATES.__dict__,
    }


@app.post("/generate", response_model=JobResponse)
async def generate_proposal(draft: DraftIdea, bg: BackgroundTasks):
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "running", "type": "generate", "started": datetime.utcnow().isoformat()}
    bg.add_task(_run_generate, job_id, draft)
    return JobResponse(job_id=job_id, status="running", message="Generation started.")


@app.post("/review", response_model=JobResponse)
async def review_proposal(proposal: Proposal, bg: BackgroundTasks):
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "running", "type": "review", "started": datetime.utcnow().isoformat()}
    bg.add_task(_run_review, job_id, proposal)
    return JobResponse(job_id=job_id, status="running", message="Review started.")


@app.post("/pipeline", response_model=JobResponse)
async def run_pipeline_endpoint(req: PipelineRequest, bg: BackgroundTasks):
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "running", "type": "pipeline", "started": datetime.utcnow().isoformat()}
    bg.add_task(_run_pipeline, job_id, req.draft, req.iterations)
    return JobResponse(job_id=job_id, status="running", message="Pipeline started.")


@app.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]


@app.post("/validate")
async def validate_proposal(proposal: Proposal) -> dict:
    report = proposal.char_count_report()
    violations = {k: v for k, v in report.items() if v["remaining"] < 0}
    return {"valid": len(violations) == 0, "char_counts": report, "violations": violations}


@app.post("/config/reload")
async def reload_config() -> dict:
    """Hot-reload config.yaml without restarting."""
    cfg.reload()
    return {"status": "reloaded"}


# =============================================================================
# Background tasks
# =============================================================================

async def _run_generate(job_id: str, draft: DraftIdea) -> None:
    try:
        from src.generators.proposal_generator import ProposalGenerator
        proposal = await ProposalGenerator().generate(draft)
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["result"] = json.loads(proposal.model_dump_json())
    except Exception as e:
        jobs[job_id].update(status="failed", error=str(e))


async def _run_review(job_id: str, proposal: Proposal) -> None:
    try:
        from src.reviewers.panel_reviewer import ReviewPanel
        consensus = await ReviewPanel().review(proposal)
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["result"] = json.loads(consensus.model_dump_json())
    except Exception as e:
        jobs[job_id].update(status="failed", error=str(e))


async def _run_pipeline(job_id: str, draft: DraftIdea, iterations: int | None) -> None:
    try:
        from src.generators.pipeline import Pipeline
        result = await Pipeline().run(draft, iterations=iterations)
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["result"] = {
            "proposal": json.loads(result["proposal"].model_dump_json()),
            "history": result["history"],
            "output_dir": result["output_dir"],
        }
    except Exception as e:
        jobs[job_id].update(status="failed", error=str(e))
