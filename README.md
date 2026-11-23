# SignalDraft

SignalDraft researches a prospect and company, checks identity against public
sources, selects an evidence-backed business signal, and creates a draft for
human review. It does not send email.

## Run locally

1. Use Python 3.11 or newer.
2. Create and activate a virtual environment.
3. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and set `GEMINI_API_KEY` and
   `TAVILY_API_KEY`.
5. Start the Python API from this directory:

   ```bash
   .venv/bin/uvicorn server:app --reload --port 8000
   ```

6. In a second terminal, start the React frontend:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

Open the local URL printed by Vite, normally `http://localhost:5173`.

The previous Streamlit interface remains available as a fallback with
`streamlit run app.py`. The React frontend is now the primary interface.

The UI can open without credentials, but a live research run requires both API
keys. Missing credentials and provider failures are shown as failed stages; no
fixtures or generated sample data are substituted.

## Providers and persistence

- **Research:** Tavily Search followed by Tavily Extract. Search includes a
  dedicated public LinkedIn query when results are available, alongside general
  web and company-signal searches.
- **AI:** Google Gemini through the `google-genai` SDK. `GEMINI_MODEL` defaults
  to `gemini-3.1-flash-lite`.
- **Validation:** Pydantic input/output models plus deterministic identity,
  evidence quote, recency, source-reference, capability, and draft-length
  checks.
- **Local persistence:** SQLite at `SQLITE_PATH` (default `signaldraft.db`).
- **Hosted persistence:** Optional Supabase. Run [`sql/schema.sql`](sql/schema.sql)
  in the Supabase SQL editor, then set `SUPABASE_URL` and `SUPABASE_KEY`.
  Configured Supabase errors are surfaced; the app does not silently fall back
  to SQLite.

Streamlit Community Cloud's local filesystem is not durable across all
restarts/redeployments. Configure Supabase for durable hosted run history.
Never commit `.env` or API credentials.

## Pipeline and decision rules

1. Search for the prospect/company and company-level signals; extract pages.
2. Ask Gemini to assess identity, then apply a deterministic gate: the full
   name and supplied company must co-occur in retrieved source content.
   Ambiguous/conflicting identity requires clarification; unverified identity
   abstains.
3. Ask Gemini for source-linked claims with verbatim quotes. Claims with an
   invalid source id or quote not present in the extracted source are dropped.
4. Score eligible signals using role relevance (30%), FlowPilot offer relevance
   (30%), source quality (20%), and event freshness (20%). This is a heuristic,
   not a probability. Known signals older than one year are ineligible.
5. Generate a 70–120 word email for FlowPilot's fictional approved capabilities
   only. Deterministic validation gets one targeted repair attempt. Failure to
   validate results in abstention, not a draft.
6. A reviewer can edit, save, approve, or reject. Approval revalidates the
   edited draft; saving edits clears approval. Nothing is sent.

## Frontend architecture

- **React:** Browser interface for prospect input, execution stages, evidence,
  draft review, and run history.
- **Vite:** Local development server and production frontend build tool.
- **FastAPI:** Python HTTP API that exposes the existing SignalDraft pipeline.
- **Node.js:** Used only to run the React development/build tools; it is not the
  application backend.
- **Next.js:** Not required for this MVP because the backend and business logic
  remain in Python.

Keep Gemini, Tavily, and Supabase secret keys in the Python server's `.env`.
The React browser must never receive those secrets.

For production, set `FRONTEND_ORIGIN` on the API server to the Vercel URL. For
local development, the default allows `localhost:5173` and `127.0.0.1:5173`.

## Review and limitations

The rules are conservative but are not a guarantee of factual correctness.
Search snippets can be incomplete, names can collide, and model relevance
scores are subjective. Review the displayed sources and claims before approving
any draft. The application stores review state/history but does not contact the
prospect.

The demo walkthrough can show: a successful run and stage trace, source-backed
signal, review/edit/revalidation, then an ambiguous or sparse prospect that
does not reach drafting. Live provider integration and hosted persistence must
be smoke-tested with your own credentials and Supabase project.

## Tests

```bash
pytest
```

Tests use deterministic fixture data and mocked providers; they do not call
Gemini, Tavily, or Supabase.
