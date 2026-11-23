from src.gemini import GeminiService
from src.models import EvidenceClaimOutput, EvidenceExtraction, ProspectInput, Source


def test_extraction_discards_unverifiable_quotes(load_fixture):
    fixture = load_fixture("happy_path")
    prospect = ProspectInput(**fixture["prospect"])
    source = Source(**fixture["source"])
    service = GeminiService.__new__(GeminiService)
    service._generate_structured = lambda _prompt, _model: EvidenceExtraction(
        claims=[
            EvidenceClaimOutput(
                claim="Supported claim",
                quote=fixture["evidence"]["quote"],
                source_id=source.id,
                event_date="2026-10-10",
                role_relevance=80,
                offer_relevance=80,
            ),
            EvidenceClaimOutput(
                claim="Invented claim",
                quote="This quote is absent from the source",
                source_id=source.id,
                role_relevance=90,
                offer_relevance=90,
            ),
            EvidenceClaimOutput(
                claim="Unknown source",
                quote="Jane Smith",
                source_id="missing",
                role_relevance=90,
                offer_relevance=90,
            ),
        ]
    )

    evidence = service.extract_evidence(
        prospect.full_name, prospect.company_name, [source]
    )

    assert len(evidence) == 1
    assert evidence[0].claim == "Supported claim"
