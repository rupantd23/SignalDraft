import re
from datetime import date

from src.models import EmailDraft, ExtractedEvidence, SelectedSignal, Source


RECENCY_TERMS = re.compile(
    r"\b(recently|just announced|this week|this month|last week|last month|"
    r"earlier this year|newly)\b",
    re.IGNORECASE,
)
NUMBER = re.compile(r"\b\d+(?:[.,]\d+)?%?\b")
SELLER_CAPABILITIES = (
    "workflow automation",
    "automate repetitive workflows",
    "route work",
    "routing work",
    "crm handoff",
    "crm handoffs",
    "handoffs between tools",
)


def validate_draft(
    draft: EmailDraft,
    signal: SelectedSignal,
    evidence: ExtractedEvidence,
    sources: list[Source],
    today: date | None = None,
) -> list[str]:
    errors: list[str] = []
    word_count = len(draft.body.split())
    if not 70 <= word_count <= 120:
        errors.append(f"Email body must be 70–120 words; got {word_count}.")
    source_ids = {source.id for source in sources}
    allowed_ids = set(signal.source_ids)
    if not draft.source_ids or not set(draft.source_ids).issubset(source_ids):
        errors.append("Draft references a missing or invalid source.")
    if not set(draft.source_ids).issubset(allowed_ids):
        errors.append("Draft references a source that does not support the selected signal.")
    if evidence.source_id not in allowed_ids:
        errors.append("Selected signal has no valid supporting evidence source.")
    if not any(term in draft.body.casefold() for term in SELLER_CAPABILITIES):
        errors.append("Draft must describe an approved FlowPilot capability.")
    if evidence.claim.casefold() not in draft.body.casefold():
        claim_terms = {
            token
            for token in re.findall(r"[a-z]{4,}", evidence.claim.casefold())
            if token not in {"their", "there", "about", "announced", "company"}
        }
        body_terms = set(re.findall(r"[a-z]{4,}", draft.body.casefold()))
        if len(claim_terms & body_terms) < min(2, len(claim_terms)):
            errors.append("Draft does not clearly refer to the selected evidence.")
    if NUMBER.search(f"{draft.subject} {draft.body}"):
        errors.append("Draft contains a number that has not been approved by evidence.")
    if RECENCY_TERMS.search(f"{draft.subject} {draft.body}"):
        date_known = bool(signal.event_date)
        event_year_old = False
        if signal.event_date:
            try:
                event_year_old = (
                    (today or date.today()) - date.fromisoformat(signal.event_date[:10])
                ).days > 90
            except ValueError:
                event_year_old = True
        if not date_known or event_year_old:
            errors.append("Draft uses recency language unsupported by a recent event date.")
    if not draft.subject.strip() or not draft.body.strip():
        errors.append("Draft subject and body must both be present.")
    return errors
