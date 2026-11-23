from functools import lru_cache
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import settings
from src.models import ProspectInput, ResearchRun
from src.pipeline import run_pipeline
from src.repository import RunRepository, create_repository
from src.review import update_review


app = FastAPI(title="SignalDraft API", version="1.0.0")

allowed_origins = [
    origin.strip()
    for origin in settings.frontend_origin.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache
def repository() -> RunRepository:
    return create_repository(settings)


class ReviewRequest(BaseModel):
    subject: str
    body: str
    action: Literal["edited", "approved", "rejected"]


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "ok": True,
        "gemini_configured": bool(settings.gemini_api_key),
        "tavily_configured": bool(settings.tavily_api_key),
        "persistence": "supabase" if settings.supabase_configured else "sqlite",
    }


@app.post("/api/runs", response_model=ResearchRun)
def create_run(prospect: ProspectInput) -> ResearchRun:
    run = run_pipeline(prospect)
    try:
        repository().save(run)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="The run completed, but could not be saved to the configured database.",
        ) from exc
    return run


@app.get("/api/runs", response_model=list[ResearchRun])
def list_runs(
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ResearchRun]:
    try:
        return repository().list_recent(limit)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not load research runs from the configured database.",
        ) from exc


@app.get("/api/runs/{run_id}", response_model=ResearchRun)
def get_run(run_id: str) -> ResearchRun:
    try:
        run = repository().get(run_id)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not load the requested research run.",
        ) from exc
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found.")
    return run


@app.patch("/api/runs/{run_id}/review", response_model=ResearchRun)
def review_run(run_id: str, request: ReviewRequest) -> ResearchRun:
    try:
        run = repository().get(run_id)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not load the requested research run.",
        ) from exc
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found.")

    updated, errors = update_review(
        run,
        subject=request.subject,
        body=request.body,
        action=request.action,
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    try:
        repository().save(updated)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="The review was valid, but could not be saved.",
        ) from exc
    return updated
