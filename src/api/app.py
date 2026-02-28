"""
FastAPI application.  All settings from config.yaml and .env.
Includes /config endpoint so users can inspect resolved settings.
"""

from __future__ import annotations

import hmac
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from src.config.fct_constants import CALL_DATES, CHAR_LIMITS, EVAL_CRITERIA, TYPOLOGY_RULES
from src.config.settings import cfg, secrets
from src.generators.models import DraftIdea, Proposal
from src.utils.sanitize import redact_secrets

logger = logging.getLogger(__name__)

# --- API Key Authentication ---------------------------------------------------

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

MAX_JOBS = 1000
JOB_TTL_SECONDS = 24 * 60 * 60  # 24 hours


async def verify_api_key(api_key: str | None = Security(_api_key_header)) -> str:
    """Validate the X-API-Key header. Skipped only for /health."""
    configured_key = secrets.fct_api_key
    if not configured_key:
        # If no key configured, allow access (development mode)
        return "dev"
    if not api_key or not hmac.compare_digest(api_key, configured_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key


app = FastAPI(
    title="FCT Proposal Engine API",
    description="AI-powered proposal generator & multi-model peer reviewer for FCT PTDC 2025",
    version="0.3.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

jobs: dict[str, dict] = {}


# --- Job cleanup --------------------------------------------------------------

def _cleanup_jobs() -> int:
    """Remove jobs older than JOB_TTL_SECONDS. Returns number removed."""
    now = datetime.now(timezone.utc)
    expired = [
        jid for jid, jdata in jobs.items()
        if (now - datetime.fromisoformat(jdata["started"].replace("Z", "+00:00"))).total_seconds()
        > JOB_TTL_SECONDS
    ]
    for jid in expired:
        del jobs[jid]
    return len(expired)


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


@app.get("/config", dependencies=[Depends(verify_api_key)])
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


@app.get("/rules", dependencies=[Depends(verify_api_key)])
async def get_rules() -> dict:
    return {
        "typologies": {k.value: v.__dict__ for k, v in TYPOLOGY_RULES.items()},
        "character_limits": CHAR_LIMITS.__dict__,
        "evaluation_criteria": EVAL_CRITERIA.__dict__,
        "call_dates": CALL_DATES.__dict__,
    }


@app.post("/generate", response_model=JobResponse, dependencies=[Depends(verify_api_key)])
async def generate_proposal(draft: DraftIdea, bg: BackgroundTasks):
    _cleanup_jobs()
    if len(jobs) >= MAX_JOBS:
        raise HTTPException(503, "Too many active jobs. Try again later.")
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "running", "type": "generate", "started": datetime.now(timezone.utc).isoformat()}
    bg.add_task(_run_generate, job_id, draft)
    return JobResponse(job_id=job_id, status="running", message="Generation started.")


@app.post("/review", response_model=JobResponse, dependencies=[Depends(verify_api_key)])
async def review_proposal(proposal: Proposal, bg: BackgroundTasks):
    _cleanup_jobs()
    if len(jobs) >= MAX_JOBS:
        raise HTTPException(503, "Too many active jobs. Try again later.")
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "running", "type": "review", "started": datetime.now(timezone.utc).isoformat()}
    bg.add_task(_run_review, job_id, proposal)
    return JobResponse(job_id=job_id, status="running", message="Review started.")


@app.post("/pipeline", response_model=JobResponse, dependencies=[Depends(verify_api_key)])
async def run_pipeline_endpoint(req: PipelineRequest, bg: BackgroundTasks):
    _cleanup_jobs()
    if len(jobs) >= MAX_JOBS:
        raise HTTPException(503, "Too many active jobs. Try again later.")
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "running", "type": "pipeline", "started": datetime.now(timezone.utc).isoformat()}
    bg.add_task(_run_pipeline, job_id, req.draft, req.iterations)
    return JobResponse(job_id=job_id, status="running", message="Pipeline started.")


@app.get("/jobs/{job_id}", dependencies=[Depends(verify_api_key)])
async def get_job(job_id: str) -> dict:
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]


@app.post("/validate", dependencies=[Depends(verify_api_key)])
async def validate_proposal(proposal: Proposal) -> dict:
    report = proposal.char_count_report()
    violations = {k: v for k, v in report.items() if v["remaining"] < 0}
    return {"valid": len(violations) == 0, "char_counts": report, "violations": violations}


@app.post("/config/reload", dependencies=[Depends(verify_api_key)])
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
        jobs[job_id].update(status="failed", error=redact_secrets(str(e)))


async def _run_review(job_id: str, proposal: Proposal) -> None:
    try:
        from src.reviewers.panel_reviewer import ReviewPanel
        consensus = await ReviewPanel().review(proposal)
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["result"] = json.loads(consensus.model_dump_json())
    except Exception as e:
        jobs[job_id].update(status="failed", error=redact_secrets(str(e)))


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
        jobs[job_id].update(status="failed", error=redact_secrets(str(e)))
