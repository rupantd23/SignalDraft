from src.identity import resolve_identity
from src.models import ProspectInput, Source


def test_identity_requires_name_and_company_in_same_source(load_fixture):
    fixture = load_fixture("happy_path")
    prospect = ProspectInput(**fixture["prospect"])
    source = Source(**fixture["source"])

    result = resolve_identity(prospect, [source])

    assert result.status == "verified"
    assert result.supporting_source_ids == ["src-happy"]


def test_ambiguous_identity_cannot_be_upgraded_by_same_name(load_fixture):
    fixture = load_fixture("ambiguous_identity")
    prospect = ProspectInput(**fixture["prospect"])
    source = Source(**fixture["source"])

    result = resolve_identity(prospect, [source], fixture["identity_assessment"])

    assert result.status == "ambiguous"


def test_conflicting_employer_requires_cited_support(load_fixture):
    fixture = load_fixture("conflicting_employment")
    prospect = ProspectInput(**fixture["prospect"])
    source = Source(**fixture["source"])

    result = resolve_identity(prospect, [source], fixture["identity_assessment"])

    assert result.status == "conflicting"
    assert result.supporting_source_ids == ["src-conflict"]


def test_missing_identity_evidence_is_unverified(load_fixture):
    fixture = load_fixture("sparse_footprint")
    prospect = ProspectInput(**fixture["prospect"])

    result = resolve_identity(prospect, [])

    assert result.status == "unverified"
