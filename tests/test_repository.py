from src.models import ProspectInput, ResearchRun
from src.repository import SQLiteRepository
from src.review import update_review
from src.models import EmailDraft


def test_completed_runs_reopen_and_edit_clears_approval(tmp_path):
    repo = SQLiteRepository(str(tmp_path / "runs.sqlite"))
    run = ResearchRun(
        prospect=ProspectInput(full_name="Jane Smith", company_name="Acme")
    )
    run.outcome = "draft_ready"
    run.review_status = "approved"
    run.draft = EmailDraft(
        subject="Original subject",
        body="Original body",
        source_ids=["source-1"],
    )
    repo.save(run)

    reopened = repo.get(run.id)

    assert reopened is not None
    assert reopened.draft.subject == "Original subject"
    assert reopened.review_status == "approved"


def test_editing_requires_a_selected_signal():
    run = ResearchRun(
        prospect=ProspectInput(full_name="Jane Smith", company_name="Acme")
    )

    updated, errors = update_review(run, "Changed", "Changed body", "edited")

    assert errors
    assert updated.review_status == "pending"
