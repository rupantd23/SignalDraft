import json
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from src.config import Settings, settings
from src.models import (
    DraftGeneration,
    EvidenceExtraction,
    ExtractedEvidence,
    Source,
)


class GeminiError(RuntimeError):
    """Raised when Gemini cannot complete a requested operation."""


T = TypeVar("T", bound=BaseModel)


class GeminiService:
    def __init__(self, config: Settings = settings) -> None:
        if not config.gemini_api_key:
            raise GeminiError("GEMINI_API_KEY is not configured.")
        self.model = config.gemini_model
        self.client = genai.Client(api_key=config.gemini_api_key)

    def _generate_structured(self, prompt: str, response_model: type[T]) -> T:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_model,
                    temperature=0.1,
                ),
            )
            if response.parsed is not None:
                return response_model.model_validate(response.parsed)
            if not response.text:
                raise GeminiError("Gemini returned an empty response.")
            return response_model.model_validate_json(response.text)
        except GeminiError:
            raise
        except Exception as exc:
            provider_error = str(exc).upper()
            if any(marker in provider_error for marker in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED")):
                raise GeminiError(
                    "Gemini is temporarily busy. Please wait a moment and try again."
                ) from exc
            raise GeminiError(
                "Gemini could not complete this request. Please try again."
            ) from exc

    def extract_evidence(
        self, prospect_name: str, company_name: str, sources: list[Source]
    ) -> list[ExtractedEvidence]:
        source_text = [
            {
                "id": source.id,
                "url": str(source.url),
                "title": source.title,
                "content": source.content[:6000],
            }
            for source in sources
        ]
        prompt = f"""
You extract only verifiable public evidence for B2B sales research.
Prospect: {prospect_name}
Company: {company_name}

Return claims about an actual business event, initiative, hiring, change, or
operational problem that could reasonably make workflow automation relevant.
Use a short verbatim quote from one provided source, its exact source id, and
the event date only when explicitly stated. Do not infer the date from when a
page was crawled or updated. Score role and offer relevance from 0 to 100.
Never invent facts, dates, source ids, quotes, or personal details. Return an
empty claims list when no useful support exists.

SELLER: FlowPilot helps teams automate repetitive workflows, route work between
tools, and improve CRM handoffs. Do not claim any other seller capability.
SOURCES:
{json.dumps(source_text, ensure_ascii=False)}
"""
        output = self._generate_structured(prompt, EvidenceExtraction)
        source_by_id = {source.id: source for source in sources}
        evidence: list[ExtractedEvidence] = []
        for index, item in enumerate(output.claims, start=1):
            source = source_by_id.get(item.source_id)
            if source is None or not item.quote.strip():
                continue
            if item.quote.casefold() not in source.content.casefold():
                continue
            evidence.append(
                ExtractedEvidence(
                    id=f"e{index}",
                    claim=item.claim.strip(),
                    quote=item.quote.strip(),
                    source_id=item.source_id,
                    event_date=item.event_date,
                    signal_type=item.signal_type.strip(),
                    role_relevance=item.role_relevance,
                    offer_relevance=item.offer_relevance,
                )
            )
        return evidence

    def classify_identity(
        self,
        prospect_name: str,
        company_name: str,
        sources: list[Source],
    ) -> dict[str, object]:
        source_text = [
            {
                "id": source.id,
                "url": str(source.url),
                "title": source.title,
                "content": source.content[:4000],
            }
            for source in sources
        ]
        prompt = f"""
Assess whether these sources identify the exact same professional.
Prospect name: {prospect_name}
Expected company: {company_name}

Classify as verified only when a source directly connects the full name and
expected company. Use conflicting only when a source clearly connects the full
name to a different current employer. Use ambiguous when a plausible person is
found but employer identity is unclear, and unverified when no matching person
is supported. Cite only supplied source ids and explain the evidence briefly.
Do not treat search-result similarity as proof.
SOURCES:
{json.dumps(source_text, ensure_ascii=False)}
"""

        class IdentityResponse(BaseModel):
            status: str
            rationale: str
            supporting_source_ids: list[str]

        result = self._generate_structured(prompt, IdentityResponse)
        return result.model_dump()

    def generate_draft(
        self,
        prospect_name: str,
        company_name: str,
        job_title: str,
        signal_claim: str,
        signal_quote: str,
        source_ids: list[str],
        repair_feedback: str = "",
    ) -> DraftGeneration:
        prompt = f"""
Write a concise, personalized first-touch B2B sales email for FlowPilot.
Prospect: {prospect_name}, {job_title or "role not provided"} at {company_name}.
Verified business signal: {signal_claim}
Verbatim evidence: {signal_quote}
Allowed source ids: {json.dumps(source_ids)}

FlowPilot is fictional and offers only workflow automation, routing work
between tools, and improving CRM handoffs. Connect the verified signal to one
of those capabilities without asserting an unverified problem, outcome, metric,
customer, product feature, or relationship. Do not imply you know the prospect
personally. Do not use any numbers or unsupported recency language. Return a
natural subject and an email body of 70 to 120 whitespace-separated words.
Do not include a signature, source URLs, or citations in the email body.
Return only allowed source ids in source_ids.
{f"Repair the previous draft to address: {repair_feedback}" if repair_feedback else ""}
"""
        return self._generate_structured(prompt, DraftGeneration)
