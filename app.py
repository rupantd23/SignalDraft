import streamlit as st
from pydantic import ValidationError

from src.config import settings
from src.models import ProspectInput
from src.pipeline import run_pipeline
from src.repository import RunRepository, create_repository
from src.review import update_review


st.set_page_config(
    page_title="SignalDraft",
    page_icon="🎯",
    layout="wide",
)


@st.cache_resource
def repository() -> RunRepository:
    return create_repository(settings)


def render_run(run) -> None:
    st.subheader(f"Run for {run.prospect.full_name} · {run.prospect.company_name}")
    st.caption(f"Run ID: {run.id} · Outcome: {run.outcome.replace('_', ' ').title()}")
    for item in run.stages:
        message = f"**{item.name}:** {item.detail}"
        if item.status == "failed":
            st.error(message)
        elif item.status == "needs_attention":
            st.warning(message)
        else:
            st.success(message)
    if run.error:
        st.info(run.error)

    if run.identity:
        st.markdown(f"**Identity:** `{run.identity.status}` — {run.identity.rationale}")
    if run.selected_signal:
        st.markdown("#### Selected business signal")
        st.write(run.selected_signal.evidence_claim)
        st.caption(
            f"Heuristic score {run.selected_signal.score}/100 · "
            f"{run.selected_signal.rationale}"
        )
    if run.evidence:
        with st.expander("Extracted evidence"):
            for item in run.evidence:
                st.markdown(f"**{item.claim}**")
                st.write(f"> {item.quote}")
                st.caption(f"Source: {item.source_id} · Event date: {item.event_date or 'Not established'}")
    if run.sources:
        with st.expander(f"Research sources ({len(run.sources)})"):
            for source in run.sources:
                st.markdown(f"- [{source.title}]({source.url})")
                st.caption(f"Source ID: {source.id} · Published: {source.published_date or 'Not provided'}")

    if run.draft:
        st.markdown("#### Email draft · human review required")
        st.text_input("Subject", value=run.draft.subject, key=f"subject-{run.id}", disabled=True)
        st.text_area("Body", value=run.draft.body, key=f"body-{run.id}", height=220, disabled=True)
        st.caption("SignalDraft never sends email.")


st.title("SignalDraft")
st.caption("Personalised outreach — from prospect to evidence-backed draft")

with st.sidebar:
    st.header("Configuration")
    st.write("Gemini:", "Ready" if settings.gemini_api_key else "API key missing")
    st.write("Tavily:", "Ready" if settings.tavily_api_key else "API key missing")
    st.write(
        "Persistence:",
        "Supabase" if settings.supabase_configured else "Local SQLite",
    )
    if not settings.supabase_configured:
        st.caption(
            "SQLite is suitable for local development. Hosted instances may have "
            "ephemeral storage; configure Supabase for durable deployment."
        )

new_run_tab, dashboard_tab = st.tabs(["New research run", "Dashboard & review"])

with new_run_tab:
    st.markdown(
        "Research public sources, verify prospect identity, select a supported "
        "business signal, and prepare a draft for a person to review."
    )
    with st.form("prospect-form"):
        full_name = st.text_input("Prospect full name", placeholder="Jane Smith")
        company_name = st.text_input("Company name", placeholder="Acme Corporation")
        company_domain = st.text_input("Company domain (optional)", placeholder="acme.com")
        job_title = st.text_input("Job title (optional)", placeholder="VP of Operations")
        submitted = st.form_submit_button("Research prospect", type="primary")

    if submitted:
        try:
            prospect = ProspectInput(
                full_name=full_name,
                company_name=company_name,
                company_domain=company_domain,
                job_title=job_title,
            )
        except ValidationError as exc:
            st.error("Please check the prospect details.")
            for error in exc.errors():
                st.write(f"- {error['msg']}")
        else:
            with st.status("Running research pipeline…", expanded=True) as status:
                st.write("Searching and extracting public sources.")
                run = run_pipeline(prospect)
                st.write("Saving run for review.")
                try:
                    repository().save(run)
                except Exception as exc:
                    status.update(label="Run completed, but could not be saved.", state="error")
                    st.error(f"Persistence failed: {exc}")
                else:
                    st.session_state["last_run_id"] = run.id
                    status.update(
                        label=f"Run finished: {run.outcome.replace('_', ' ')}",
                        state="complete" if run.outcome == "draft_ready" else "error",
                    )

    last_run_id = st.session_state.get("last_run_id")
    if last_run_id:
        try:
            latest_run = repository().get(last_run_id)
        except Exception as exc:
            st.error(f"Could not load the saved run: {exc}")
        else:
            if latest_run:
                render_run(latest_run)

with dashboard_tab:
    try:
        repo = repository()
        runs = repo.list_recent()
    except Exception as exc:
        st.error(f"Could not connect to the configured run database: {exc}")
        runs = []
        repo = None

    st.subheader("Research runs")
    if runs:
        draft_count = sum(run.outcome == "draft_ready" for run in runs)
        pending_count = sum(
            run.outcome == "draft_ready" and run.review_status == "pending"
            for run in runs
        )
        metric_columns = st.columns(3)
        metric_columns[0].metric("Total runs", len(runs))
        metric_columns[1].metric("Drafts ready", draft_count)
        metric_columns[2].metric("Awaiting review", pending_count)

        labels = {
            run.id: (
                f"{run.created_at.strftime('%Y-%m-%d %H:%M')} · "
                f"{run.prospect.full_name} · {run.prospect.company_name} · "
                f"{run.outcome.replace('_', ' ')}"
            )
            for run in runs
        }
        selected_id = st.selectbox(
            "Open a run",
            options=list(labels),
            format_func=lambda run_id: labels[run_id],
        )
        selected_run = repo.get(selected_id) if repo else None
        if selected_run:
            render_run(selected_run)
            if selected_run.draft:
                st.markdown("#### Review this draft")
                with st.form(f"review-{selected_run.id}"):
                    subject = st.text_input(
                        "Edit subject",
                        value=selected_run.draft.subject,
                        key=f"review-subject-{selected_run.id}",
                    )
                    body = st.text_area(
                        "Edit email body",
                        value=selected_run.draft.body,
                        height=220,
                        key=f"review-body-{selected_run.id}",
                    )
                    action_columns = st.columns(3)
                    save_edits = action_columns[0].form_submit_button("Save edits")
                    approve = action_columns[1].form_submit_button("Approve")
                    reject = action_columns[2].form_submit_button("Reject")

                action = (
                    "edited" if save_edits else
                    "approved" if approve else
                    "rejected" if reject else None
                )
                if action:
                    updated, errors = update_review(
                        selected_run, subject, body, action
                    )
                    if errors:
                        st.error("Review was not saved: " + "; ".join(errors))
                    else:
                        try:
                            repo.save(updated)
                        except Exception as exc:
                            st.error(f"Could not save the review: {exc}")
                        else:
                            st.success(
                                "Draft edits saved; prior approval cleared."
                                if action == "edited"
                                else f"Draft {action}."
                            )
                            st.rerun()
    else:
        st.info("No research runs yet. Start with a new research run.")
