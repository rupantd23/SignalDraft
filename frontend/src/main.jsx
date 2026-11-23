import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { supabase } from "./supabase";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}, accessToken = "") {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...(options.headers || {}),
      },
      ...options,
    });
  } catch {
    throw new Error("The SignalDraft service is temporarily unavailable. Please wait a moment and try again.");
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(payload.detail)
      ? payload.detail.join("; ")
      : payload.detail || "Request failed.";
    throw new Error(detail);
  }
  return payload;
}

function StatusPill({ value }) {
  return <span className={`pill pill-${value}`}>{value.replaceAll("_", " ")}</span>;
}

function AuthScreen() {
  const [mode, setMode] = useState("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (!supabase) {
      setError("Authentication is not configured for this deployment.");
      return;
    }
    setLoading(true);
    setError("");
    setMessage("");
    const result = mode === "signin"
      ? await supabase.auth.signInWithPassword({ email, password })
      : await supabase.auth.signUp({ email, password });
    setLoading(false);
    if (result.error) {
      setError(result.error.message);
    } else if (mode === "signup" && !result.data.session) {
      setMessage("Account created. Check your email to confirm your account, then sign in.");
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <p className="eyebrow">Private workspace</p>
        <h1>SignalDraft</h1>
        <p className="subtitle">Sign in to keep your prospect research and drafts private to your account.</p>
        {error && <div className="alert error">{error}</div>}
        {message && <div className="alert info">{message}</div>}
        <form onSubmit={submit}>
          <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
          <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength="6" required /></label>
          <button className="primary-button auth-button" disabled={loading}>
            {loading ? "Working…" : mode === "signin" ? "Sign in" : "Create account"}
          </button>
        </form>
        <button className="link-button auth-switch" onClick={() => { setMode(mode === "signin" ? "signup" : "signin"); setError(""); setMessage(""); }}>
          {mode === "signin" ? "Need an account? Sign up" : "Already have an account? Sign in"}
        </button>
      </section>
    </main>
  );
}

function FailureNotice({ message }) {
  const temporary = message.toLowerCase().includes("temporarily busy");
  return (
    <div className={`failure-notice ${temporary ? "temporary" : "general"}`}>
      <div className="failure-icon" aria-hidden="true">{temporary ? "◌" : "!"}</div>
      <div>
        <strong>{temporary ? "Gemini is temporarily busy" : "The run could not finish"}</strong>
        <p>{temporary ? "The AI service is handling high demand. Your research sources are safe. Please wait a moment, then try again." : message}</p>
      </div>
    </div>
  );
}

function App() {
  const [session, setSession] = useState(null);
  const [prospect, setProspect] = useState({
    full_name: "",
    company_name: "",
    company_domain: "",
    job_title: "",
  });
  const [run, setRun] = useState(null);
  const [runs, setRuns] = useState([]);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function loadRuns(accessToken = session?.access_token) {
    if (!accessToken) return;
    try {
      setRuns(await request("/api/runs", {}, accessToken));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    if (!supabase) return undefined;
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data: listener } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (session?.access_token) loadRuns(session.access_token);
  }, [session?.access_token]);

  function updateField(event) {
    setProspect({ ...prospect, [event.target.name]: event.target.value });
  }

  async function researchProspect(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setMessage("Researching public sources and preparing the run…");
    try {
      const result = await request("/api/runs", {
        method: "POST",
        body: JSON.stringify(prospect),
      }, session.access_token);
      setRun(result);
      setSubject(result.draft?.subject || "");
      setBody(result.draft?.body || "");
      setMessage(`Run finished: ${result.outcome.replaceAll("_", " ")}.`);
      await loadRuns(session.access_token);
    } catch (err) {
      setError(err.message);
      setMessage("");
    } finally {
      setLoading(false);
    }
  }

  async function submitReview(action) {
    if (!run?.draft) return;
    setError("");
    try {
      const updated = await request(`/api/runs/${run.id}/review`, {
        method: "PATCH",
        body: JSON.stringify({ subject, body, action }),
      }, session.access_token);
      setRun(updated);
      setSubject(updated.draft?.subject || "");
      setBody(updated.draft?.body || "");
      setMessage(`Draft ${action}.`);
      await loadRuns(session.access_token);
    } catch (err) {
      setError(err.message);
    }
  }

  function openRun(selected) {
    setRun(selected);
    setSubject(selected.draft?.subject || "");
    setBody(selected.draft?.body || "");
    setMessage("");
    setError("");
  }

  async function signOut() {
    await supabase?.auth.signOut();
    setRun(null);
    setRuns([]);
  }

  if (!supabase || !session) return <AuthScreen />;

  return (
    <main className="shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Evidence-backed outreach</p>
          <h1>SignalDraft</h1>
          <p className="subtitle">
            Research a prospect, find a defensible business signal, and prepare a draft for human review.
          </p>
        </div>
        <div className="hero-actions">
          <div className="hero-note">No email is sent automatically.</div>
          <button className="link-button signout-button" onClick={signOut}>Sign out</button>
        </div>
      </header>

      {error && <div className="alert error">{error}</div>}
      {message && <div className="alert info">{message}</div>}

      <section className="grid two-column">
        <form className="card" onSubmit={researchProspect}>
          <div className="section-heading">
            <div>
              <p className="eyebrow">New run</p>
              <h2>Research a prospect</h2>
            </div>
            <span className="step">01</span>
          </div>
          <label>
            Full name
            <input name="full_name" value={prospect.full_name} onChange={updateField} placeholder="Jane Smith" required />
          </label>
          <label>
            Company
            <input name="company_name" value={prospect.company_name} onChange={updateField} placeholder="Acme Corporation" required />
          </label>
          <div className="form-row">
            <label>
              Company domain
              <input name="company_domain" value={prospect.company_domain} onChange={updateField} placeholder="acme.com" />
            </label>
            <label>
              Job title
              <input name="job_title" value={prospect.job_title} onChange={updateField} placeholder="VP of Operations" />
            </label>
          </div>
          <button className="primary-button" disabled={loading}>
            {loading ? "Researching…" : "Research prospect"}
          </button>
          <p className="helper">Research includes general web sources and LinkedIn when publicly available.</p>
        </form>

        <section className="card run-card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Execution trace</p>
              <h2>{run ? `${run.prospect.full_name} · ${run.prospect.company_name}` : "Your next run appears here"}</h2>
            </div>
            {run && <StatusPill value={run.outcome} />}
          </div>
          {!run ? (
            <div className="empty-state">Submit a prospect to see research, identity, evidence, scoring, and draft validation stages.</div>
          ) : (
            <>
              <div className="stage-list">
                {run.stages.map((stage) => (
                  <div className="stage" key={`${stage.name}-${stage.completed_at}`}>
                    <span className={`stage-dot ${stage.status}`} />
                    <div>
                      <strong>{stage.name}</strong>
                      <p>{stage.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
              {run.error && <FailureNotice message={run.error} />}
            </>
          )}
        </section>
      </section>

      {run && (
        <section className="grid two-column detail-grid">
          <section className="card">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Evidence</p>
                <h2>Why this signal was selected</h2>
              </div>
              {run.selected_signal && <span className="score">{run.selected_signal.score}/100</span>}
            </div>
            {run.identity && <p><strong>Identity:</strong> {run.identity.status} — {run.identity.rationale}</p>}
            {run.selected_signal ? (
              <>
                <p className="signal">{run.selected_signal.evidence_claim}</p>
                <p className="muted">{run.selected_signal.rationale}</p>
              </>
            ) : <div className="empty-state">No eligible signal was found.</div>}
            {run.evidence?.map((item) => (
              <blockquote key={item.id}>
                “{item.quote}”
                <cite>{item.source_id} · {item.event_date || "Event date not established"}</cite>
              </blockquote>
            ))}
            <details>
              <summary>Research sources ({run.sources.length})</summary>
              <ul className="source-list">
                {run.sources.map((source) => (
                  <li key={source.id}><a href={source.url} target="_blank" rel="noreferrer">{source.title}</a><span>{source.id}</span></li>
                ))}
              </ul>
            </details>
          </section>

          <section className="card">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Human review</p>
                <h2>Email draft</h2>
              </div>
              {run.draft && <StatusPill value={run.review_status} />}
            </div>
            {run.draft ? (
              <>
                <label>Subject<input value={subject} onChange={(event) => setSubject(event.target.value)} /></label>
                <label>Body<textarea value={body} onChange={(event) => setBody(event.target.value)} rows="11" /></label>
                <div className="button-row">
                  <button className="secondary-button" onClick={() => submitReview("edited")}>Save edits</button>
                  <button className="primary-button" onClick={() => submitReview("approved")}>Approve</button>
                  <button className="danger-button" onClick={() => submitReview("rejected")}>Reject</button>
                </div>
              </>
            ) : <div className="empty-state">No draft was generated because the run did not pass the safety gates.</div>}
          </section>
        </section>
      )}

      <section className="card history-card">
        <div className="section-heading">
          <div><p className="eyebrow">History</p><h2>Recent runs</h2></div>
          <button className="link-button" onClick={() => loadRuns(session.access_token)}>Refresh</button>
        </div>
        {runs.length === 0 ? <div className="empty-state">No saved runs yet.</div> : (
          <div className="history-list">
            {runs.map((item) => (
              <button className="history-item" key={item.id} onClick={() => openRun(item)}>
                <span>{item.prospect.full_name} · {item.prospect.company_name}</span>
                <StatusPill value={item.outcome} />
              </button>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(
  <StrictMode><App /></StrictMode>,
);
