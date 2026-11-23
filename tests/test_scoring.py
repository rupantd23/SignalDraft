from datetime import date

from src.models import ExtractedEvidence, Source
from src.scoring import freshness_score, score_signals


def test_old_event_is_not_made_fresh_by_current_page(load_fixture):
    fixture = load_fixture("stale_news")
    source = Source(**fixture["source"])
    evidence = ExtractedEvidence(**fixture["evidence"])

    result = score_signals([evidence], [source], today=date(2026, 11, 22))

    assert result == []
    assert freshness_score("2024-01-10", date(2026, 11, 22)) == 0


def test_recent_eligible_signal_uses_weighted_heuristic(load_fixture):
    fixture = load_fixture("happy_path")
    source = Source(**fixture["source"])
    evidence = ExtractedEvidence(**fixture["evidence"])

    result = score_signals([evidence], [source], today=date(2026, 11, 22))

    assert len(result) == 1
    assert result[0].score >= 60
    assert result[0].score_breakdown["freshness"] == 100
