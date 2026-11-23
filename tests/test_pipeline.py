from datetime import date

from src.models import (
    DraftGeneration,
    ExtractedEvidence,
    ProspectInput,
    Source,
)
from src.pipeline import run_pipeline


VALID_BODY = (
    "Hi Jane, I saw Acme announced a procurement workflow redesign. "
    "For operations teams coordinating work across multiple tools, keeping "
    "those handoffs consistent can take attention away from the work itself. "
    "FlowPilot supports workflow automation and can route work between tools, "
    "so teams can make a process easier to manage without replacing the "
    "systems they already use. If this initiative is relevant to your team, "
    "would you be open to a short conversation about how you are approaching "
    "the workflow? Either way, I would be glad to learn what matters most."
)


class FakeResearch:
    def __init__(self, source):
        self.source = source

    def research(self, _prospect):
        return [self.source]


class FakeGemini:
    def __init__(self, source, status="verified"):
        self.source = source
        self.status = status
        self.extract_called = False

    def classify_identity(self, *_args):
        return {
            "status": self.status,
            "rationale": "fixture identity result",
            "supporting_source_ids": [self.source.id],
        }

    def extract_evidence(self, *_args):
        self.extract_called = True
        return [
            ExtractedEvidence(
                id="e1",
                claim="Acme announced a procurement workflow redesign",
                quote="announced a procurement workflow redesign on 2026-10-10",
                source_id=self.source.id,
                event_date="2026-10-10",
                role_relevance=85,
                offer_relevance=90,
            )
        ]

    def generate_draft(self, **_kwargs):
        return DraftGeneration(
            subject="Acme workflow initiative",
            body=VALID_BODY,
            source_ids=[self.source.id],
        )


def test_verified_prospect_reaches_grounded_draft(load_fixture):
    fixture = load_fixture("happy_path")
    prospect = ProspectInput(**fixture["prospect"])
    source = Source(**fixture["source"])
    gemini = FakeGemini(source)

    run = run_pipeline(prospect, FakeResearch(source), gemini)

    assert run.outcome == "draft_ready"
    assert run.draft is not None
    assert run.identity.status == "verified"
    assert run.stages[-1].name == "Draft validation"


def test_ambiguous_identity_stops_before_evidence_or_drafting(load_fixture):
    fixture = load_fixture("ambiguous_identity")
    prospect = ProspectInput(**fixture["prospect"])
    source = Source(**fixture["source"])
    gemini = FakeGemini(source, status="ambiguous")

    run = run_pipeline(prospect, FakeResearch(source), gemini)

    assert run.outcome == "needs_clarification"
    assert run.draft is None
    assert gemini.extract_called is False
