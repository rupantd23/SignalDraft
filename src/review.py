from datetime import datetime, timezone

from src.models import EmailDraft, ResearchRun
from src.validation import validate_draft


def update_review(
    run: ResearchRun,
    subject: str,
    body: str,
    action: str,
) -> tuple[ResearchRun, list[str]]:
    if run.draft is None or run.selected_signal is None:
        return run, ["This run does not have a draft to review."]
    edited = EmailDraft(
        subject=subject.strip(),
        body=body.strip(),
        source_ids=run.draft.source_ids,
    )
    run.draft = edited
    errors = validate_draft(
        edited,
        run.selected_signal,
        next(item for item in run.evidence if item.id == run.selected_signal.evidence_id),
        run.sources,
    )
    if action == "approved" and errors:
        return run, errors
    if action not in {"edited", "approved", "rejected"}:
        return run, ["Unknown review action."]
    run.review_status = "pending" if action == "edited" else action
    run.review_history.append(
        {
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "note": "Draft edited; approval cleared."
            if action == "edited"
            else "; ".join(errors),
        }
    )
    return run, []
