from datetime import date

from src.models import EmailDraft, ExtractedEvidence, SelectedSignal, Source
from src.validation import validate_draft


BODY = (
    "Hi Jane, I saw Acme announced a procurement workflow redesign. "
    "For operations teams coordinating work across multiple tools, keeping "
    "those handoffs consistent can take attention away from the work itself. "
    "FlowPilot supports workflow automation and can route work between tools, "
    "so teams can make a process easier to manage without replacing the "
    "systems they already use. If this initiative is relevant to your team, "
    "would you be open to a short conversation about how you are approaching "
    "the workflow? Either way, I would be glad to learn what matters most."
)


def _review_context(load_fixture):
    fixture = load_fixture("happy_path")
    source = Source(**fixture["source"])
    evidence = ExtractedEvidence(**fixture["evidence"])
    signal = SelectedSignal(
        evidence_id=evidence.id,
        evidence_claim=evidence.claim,
        source_ids=[source.id],
        score=90,
        score_breakdown={},
        rationale="test",
        event_date=evidence.event_date,
    )
    return source, evidence, signal


def test_grounded_email_passes_deterministic_checks(load_fixture):
    source, evidence, signal = _review_context(load_fixture)
    draft = EmailDraft(subject="Acme workflow initiative", body=BODY, source_ids=[source.id])

    errors = validate_draft(
        draft, signal, evidence, [source], today=date(2026, 11, 22)
    )

    assert errors == []


def test_unsupported_numbers_and_recency_are_rejected(load_fixture):
    source, evidence, signal = _review_context(load_fixture)
    signal = signal.model_copy(update={"event_date": "2026-01-10"})
    draft = EmailDraft(
        subject="A 30% improvement?",
        body=BODY.replace("announced", "recently announced"),
        source_ids=[source.id],
    )

    errors = validate_draft(
        draft, signal, evidence, [source], today=date(2026, 11, 22)
    )

    assert any("number" in error for error in errors)
    assert any("recency" in error for error in errors)


def test_invalid_source_reference_is_rejected(load_fixture):
    source, evidence, signal = _review_context(load_fixture)
    draft = EmailDraft(subject="Hello", body=BODY, source_ids=["unknown"])

    errors = validate_draft(draft, signal, evidence, [source])

    assert any("source" in error.lower() for error in errors)
