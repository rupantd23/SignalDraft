from collections.abc import Callable

from src.drafting import create_validated_draft
from src.gemini import GeminiError, GeminiService
from src.identity import resolve_identity
from src.models import ProspectInput, ResearchRun, StageResult
from src.research import ResearchError, ResearchService
from src.scoring import score_signals


def run_pipeline(
    prospect: ProspectInput,
    research_service: ResearchService | None = None,
    gemini_service: GeminiService | None = None,
) -> ResearchRun:
    run = ResearchRun(prospect=prospect)

    def stage(name: str, detail: str, status: str = "completed") -> None:
        run.stages.append(
            StageResult(name=name, detail=detail, status=status)  # type: ignore[arg-type]
        )

    try:
        research = research_service or ResearchService()
        run.sources = research.research(prospect)
        if not run.sources:
            stage("Research", "No usable public sources were found.", "needs_attention")
            run.outcome = "abstained"
            run.error = "No public sources were found; no draft was generated."
            return run
        stage("Research", f"Retrieved and extracted {len(run.sources)} source(s).")

        gemini = gemini_service or GeminiService()
        assessment = gemini.classify_identity(
            prospect.full_name, prospect.company_name, run.sources
        )
        run.identity = resolve_identity(prospect, run.sources, assessment)
        if run.identity.status != "verified":
            stage(
                "Identity verification",
                f"{run.identity.status.title()}: {run.identity.rationale}",
                "needs_attention",
            )
            run.outcome = (
                "needs_clarification"
                if run.identity.status in {"ambiguous", "conflicting"}
                else "abstained"
            )
            run.error = (
                "Identity was not verified. Correct the prospect details or "
                "provide stronger identifying information."
            )
            return run
        stage("Identity verification", run.identity.rationale)

        run.evidence = gemini.extract_evidence(
            prospect.full_name, prospect.company_name, run.sources
        )
        if not run.evidence:
            stage(
                "Evidence extraction",
                "No source-backed business signal passed quote verification.",
                "needs_attention",
            )
            run.outcome = "abstained"
            run.error = "No eligible business signal was supported by an exact source quote."
            return run
        stage("Evidence extraction", f"Verified {len(run.evidence)} cited claim(s).")

        scored_signals = score_signals(run.evidence, run.sources)
        if not scored_signals:
            stage(
                "Signal selection",
                "No sufficiently relevant, fresh signal passed deterministic gates.",
                "needs_attention",
            )
            run.outcome = "abstained"
            run.error = "No eligible signal met the relevance and freshness rules."
            return run
        run.selected_signal = scored_signals[0]
        stage(
            "Signal selection",
            f"Selected signal score: {run.selected_signal.score}/100 "
            "(heuristic, not a probability).",
        )

        evidence = next(
            item for item in run.evidence if item.id == run.selected_signal.evidence_id
        )
        run.draft, validation_errors = create_validated_draft(
            gemini=gemini,
            prospect=prospect,
            signal=run.selected_signal,
            evidence=evidence,
            sources=run.sources,
        )
        if run.draft is None:
            stage(
                "Draft validation",
                "Draft failed validation after one repair attempt: "
                + "; ".join(validation_errors),
                "needs_attention",
            )
            run.outcome = "abstained"
            run.error = "The generated draft did not pass safety and quality checks."
            return run
        stage("Draft validation", "Draft passed deterministic checks after generation.")
        run.outcome = "draft_ready"
        return run
    except (ResearchError, GeminiError) as exc:
        stage("Provider request", str(exc), "failed")
        run.outcome = "failed"
        run.error = str(exc)
        return run
