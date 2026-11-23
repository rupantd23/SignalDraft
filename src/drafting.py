from src.gemini import GeminiService
from src.models import (
    DraftGeneration,
    EmailDraft,
    ExtractedEvidence,
    ProspectInput,
    SelectedSignal,
)
from src.validation import validate_draft


def create_validated_draft(
    gemini: GeminiService,
    prospect: ProspectInput,
    signal: SelectedSignal,
    evidence: ExtractedEvidence,
    sources: list,
    repair: bool = True,
) -> tuple[EmailDraft | None, list[str]]:
    source_ids = signal.source_ids
    errors: list[str] = []
    for attempt in range(2 if repair else 1):
        generated: DraftGeneration = gemini.generate_draft(
            prospect_name=prospect.full_name,
            company_name=prospect.company_name,
            job_title=prospect.job_title,
            signal_claim=signal.evidence_claim,
            signal_quote=evidence.quote,
            source_ids=source_ids,
            repair_feedback="; ".join(errors) if attempt else "",
        )
        draft = EmailDraft(
            subject=generated.subject.strip(),
            body=generated.body.strip(),
            source_ids=generated.source_ids,
        )
        errors = validate_draft(draft, signal, evidence, sources)
        if not errors:
            return draft, []
    return None, errors
