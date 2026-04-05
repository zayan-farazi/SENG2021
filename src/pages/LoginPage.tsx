import { useMemo, useState, type FormEvent } from "react";
import { AppHeader } from "../components/AppHeader";
import { navigate } from "../components/AppLink";
import { getBackendHttpUrl } from "../voiceOrder";
import { clearStoredSession, setStoredSession, type StoredSession, useStoredSession } from "../session";
import "../register-page.css";

type PartyAuthV2Response = {
  partyId: string;
  partyName: string;
  contactEmail: string;
};

function getNextPath(): string {
  const params = new URLSearchParams(window.location.search);
  const next = params.get("next");

  if (!next || !next.startsWith("/") || next.startsWith("//")) {
    return "/orders";
  }

  return next;
}

export function LoginPage() {
  const [contactEmail, setContactEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [loginResult, setLoginResult] = useState<StoredSession | null>(null);
  const backendUrl = useMemo(() => getBackendHttpUrl(), []);
  const session = useStoredSession();
  const nextPath = useMemo(() => getNextPath(), []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setSubmitError(null);

    try {
      const response = await fetch(`${backendUrl}/v2/parties/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          contactEmail,
          password,
        }),
      });

      if (response.status === 200) {
        const body = (await response.json()) as PartyAuthV2Response;
        const storedSession: StoredSession = {
          partyId: body.partyId,
          partyName: body.partyName,
          contactEmail: body.contactEmail.trim().toLowerCase(),
          credential: password,
        };
        setStoredSession(storedSession);
        setLoginResult(storedSession);
        navigate(nextPath);
        return;
      }

      if (response.status === 401) {
        setSubmitError("That email and password combination was not recognized.");
        return;
      }

      const body = (await response.json().catch(() => ({ detail: null }))) as { detail?: string };
      setSubmitError(body.detail ?? "Unable to log in with these credentials.");
    } catch {
      setSubmitError("Unable to reach the backend login endpoint.");
    } finally {
      setSubmitting(false);
    }
  };

  const activeSession = loginResult ?? session;

  return (
    <div className="landing-root register-page-root">
      <div className="landing-container">
        <section className="landing-stage register-page-stage">
          <AppHeader />

          <main className="register-page-main">
            <section className="register-page-intro">
              <div>
                <h1>Log back in with your email and password.</h1>
                <p>
                  Use the same contact email and password you registered with to restore the local
                  session for this browser and continue using the protected order flow.
                </p>
              </div>
            </section>

            <section className="register-page-panel">
              {activeSession ? (
                <div className="register-page-success">
                  <h2>{loginResult ? "Login complete" : "Already signed in"}</h2>
                  <p>
                    {loginResult
                      ? "Your password has been accepted and the local session has been restored."
                      : "You already have a valid local session for this browser."}
                  </p>
                  <div className="register-page-credentials">
                    <div>
                      <span className="register-page-label">Party ID</span>
                      <strong>{activeSession.partyId}</strong>
                    </div>
                    <div>
                      <span className="register-page-label">Party name</span>
                      <strong>{activeSession.partyName}</strong>
                    </div>
                    <div>
                      <span className="register-page-label">Contact email</span>
                      <strong>{activeSession.contactEmail}</strong>
                    </div>
                  </div>
                  <div className="register-page-actions">
                    <button
                      type="button"
                      className="landing-button landing-button-primary"
                      onClick={() => navigate(nextPath)}
                    >
                      Continue
                    </button>
                    <button
                      type="button"
                      className="landing-button landing-button-secondary landing-button-reset"
                      onClick={() => {
                        clearStoredSession();
                        setLoginResult(null);
                      }}
                    >
                      Log out
                    </button>
                  </div>
                </div>
              ) : (
                <form className="register-page-form" onSubmit={handleSubmit} noValidate>
                  <div className="register-page-field-group">
                    <label htmlFor="contactEmail">Contact email</label>
                    <input
                      id="contactEmail"
                      name="contactEmail"
                      type="email"
                      value={contactEmail}
                      onChange={event => setContactEmail(event.target.value)}
                      autoComplete="email"
                    />
                  </div>
                  <div className="register-page-field-group">
                    <label htmlFor="password">Password</label>
                    <input
                      id="password"
                      name="password"
                      type="password"
                      value={password}
                      onChange={event => setPassword(event.target.value)}
                      autoComplete="current-password"
                    />
                  </div>

                  {submitError ? <p className="register-page-submit-error">{submitError}</p> : null}

                  <div className="register-page-actions">
                    <button
                      type="submit"
                      className="landing-button landing-button-primary"
                      disabled={submitting || !contactEmail.trim() || !password.trim()}
                    >
                      {submitting ? "Logging in..." : "Log in"}
                    </button>
                    <button
                      type="button"
                      className="landing-button landing-button-secondary landing-button-reset"
                      onClick={() => navigate(`/register?next=${encodeURIComponent(nextPath)}`)}
                    >
                      Register instead
                    </button>
                  </div>
                </form>
              )}
            </section>
          </main>
        </section>
      </div>
    </div>
  );
}
