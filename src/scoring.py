from datetime import date
from urllib.parse import urlparse

from src.models import ExtractedEvidence, SelectedSignal, Source


def source_quality(source: Source) -> int:
    host = urlparse(str(source.url)).hostname or ""
    if host.endswith((".gov", ".edu")):
        return 95
    if any(part in host for part in ("linkedin.com", "reuters.com", "bloomberg.com")):
        return 80
    return 60


def freshness_score(event_date: str | None, today: date | None = None) -> int:
    if not event_date:
        return 50
    try:
        event = date.fromisoformat(event_date[:10])
    except ValueError:
        return 50
    days_old = ((today or date.today()) - event).days
    if days_old < 0:
        return 0
    if days_old <= 90:
        return 100
    if days_old <= 180:
        return 75
    if days_old <= 365:
        return 40
    return 0


def score_signals(
    evidence: list[ExtractedEvidence],
    sources: list[Source],
    today: date | None = None,
) -> list[SelectedSignal]:
    source_by_id = {source.id: source for source in sources}
    scored: list[SelectedSignal] = []
    for item in evidence:
        source = source_by_id.get(item.source_id)
        if source is None:
            continue
        quality = source_quality(source)
        freshness = freshness_score(item.event_date, today)
        breakdown = {
            "role_relevance": item.role_relevance,
            "offer_relevance": item.offer_relevance,
            "source_quality": quality,
            "freshness": freshness,
        }
        score = round(
            item.role_relevance * 0.30
            + item.offer_relevance * 0.30
            + quality * 0.20
            + freshness * 0.20
        )
        if freshness == 0 or score < 60:
            continue
        scored.append(
            SelectedSignal(
                evidence_id=item.id,
                evidence_claim=item.claim,
                source_ids=[item.source_id],
                score=score,
                score_breakdown=breakdown,
                rationale=(
                    f"Role relevance {item.role_relevance}, offer relevance "
                    f"{item.offer_relevance}, source quality {quality}, "
                    f"freshness {freshness} (heuristic score, not probability)."
                ),
                event_date=item.event_date,
            )
        )
    return sorted(scored, key=lambda signal: signal.score, reverse=True)
