from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


IdentityStatus = Literal["verified", "ambiguous", "conflicting", "unverified"]
RunOutcome = Literal["draft_ready", "needs_clarification", "abstained", "failed"]
ReviewStatus = Literal["pending", "approved", "rejected"]


class ProspectInput(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    company_name: str = Field(min_length=2, max_length=160)
    company_domain: str = Field(default="", max_length=253)
    job_title: str = Field(default="", max_length=160)

    @field_validator("full_name", "company_name", "company_domain", "job_title")
    @classmethod
    def strip_whitespace(cls, value: str) -> str:
        return value.strip()


class Source(BaseModel):
    id: str
    title: str
    url: HttpUrl
    content: str
    published_date: str | None = None


class ExtractedEvidence(BaseModel):
    id: str
    claim: str
    quote: str
    source_id: str
    event_date: str | None = None
    signal_type: str = ""
    role_relevance: int = Field(default=0, ge=0, le=100)
    offer_relevance: int = Field(default=0, ge=0, le=100)


class IdentityResult(BaseModel):
    status: IdentityStatus
    rationale: str
    supporting_source_ids: list[str] = Field(default_factory=list)


class SelectedSignal(BaseModel):
    evidence_id: str
    evidence_claim: str
    source_ids: list[str]
    score: int = Field(ge=0, le=100)
    score_breakdown: dict[str, int]
    rationale: str
    event_date: str | None = None


class EmailDraft(BaseModel):
    subject: str
    body: str
    source_ids: list[str] = Field(default_factory=list)


class StageResult(BaseModel):
    name: str
    status: Literal["completed", "needs_attention", "failed"]
    detail: str
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class ResearchRun(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    prospect: ProspectInput
    outcome: RunOutcome = "failed"
    identity: IdentityResult | None = None
    sources: list[Source] = Field(default_factory=list)
    evidence: list[ExtractedEvidence] = Field(default_factory=list)
    selected_signal: SelectedSignal | None = None
    draft: EmailDraft | None = None
    stages: list[StageResult] = Field(default_factory=list)
    error: str | None = None
    review_status: ReviewStatus = "pending"
    review_history: list[dict[str, str]] = Field(default_factory=list)


class EvidenceExtraction(BaseModel):
    claims: list["EvidenceClaimOutput"] = Field(default_factory=list)


class EvidenceClaimOutput(BaseModel):
    claim: str
    quote: str
    source_id: str
    event_date: str | None = None
    signal_type: str = ""
    role_relevance: int = Field(default=0, ge=0, le=100)
    offer_relevance: int = Field(default=0, ge=0, le=100)


class DraftGeneration(BaseModel):
    subject: str
    body: str
    source_ids: list[str] = Field(default_factory=list)
