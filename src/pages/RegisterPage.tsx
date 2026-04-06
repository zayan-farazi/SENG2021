import { useMemo, useState, type FormEvent } from "react";
import { AppLink, navigate } from "../components/AppLink";
import { AppHeader } from "../components/AppHeader";
import { getBackendHttpUrl } from "../voiceOrder";
import { clearStoredSession, setStoredSession, type StoredSession, useStoredSession } from "../session";
import "../register-page.css";

type PartyRegistrationResponse = {
  partyId: string;
  partyName: string;
  contactEmail: string;
};

type ValidationErrorItem = {
  path: string;
  message: string;
};

type ValidationErrorResponse = {
  message: string;
  errors?: ValidationErrorItem[];
};

function getNextPath(): string {
  const params = new URLSearchParams(window.location.search);
  const next = params.get("next");

  if (!next || !next.startsWith("/") || next.startsWith("//")) {
    return "/orders";
  }

  return next;
}

export function RegisterPage() {
  const [partyName, setPartyName] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [registration, setRegistration] = useState<StoredSession | null>(null);
  const backendUrl = useMemo(() => getBackendHttpUrl(), []);
  const session = useStoredSession();
  const nextPath = useMemo(() => getNextPath(), []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    setFieldErrors({});

    if (password !== confirmPassword) {
      setFieldErrors({ confirmPassword: "Passwords must match." });
      setSubmitting(false);
      return;
    }

    try {
      const response = await fetch(`${backendUrl}/v2/parties/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          partyName,
          contactEmail,
          password,
        }),
      });

      if (response.status === 201) {
        const body = (await response.json()) as PartyRegistrationResponse;
        const storedSession: StoredSession = {
          partyId: body.partyId,
          partyName: body.partyName,
          contactEmail: body.contactEmail.trim().toLowerCase(),
          credential: password,
        };
        setStoredSession(storedSession);
        setRegistration(storedSession);
        return;
      }

      if (response.status === 409) {
        const body = (await response.json()) as { detail?: string };
        setSubmitError(body.detail ?? "That contact email is already registered.");
        return;
      }

      if (response.status === 422) {
        const body = (await response.json()) as ValidationErrorResponse;
        const nextErrors: Record<string, string> = {};
        for (const error of body.errors ?? []) {
          nextErrors[error.path] = error.message;
        }
        setFieldErrors(nextErrors);
        setSubmitError(body.message);
        return;
      }

      const body = (await response.json().catch(() => ({ detail: null }))) as { detail?: string };
      setSubmitError(body.detail ?? "Unable to register party.");
    } catch {
      setSubmitError("Unable to reach the backend registration endpoint.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="landing-root register-page-root">
      <div className="landing-container">
        <section className="landing-stage register-page-stage">
          <AppHeader />

          <main className="register-page-main">
            <section className="register-page-intro">
              <div>
                <h1>Register a party with an email and password.</h1>
                <p>
                  Register a buyer or seller identity, store the password-backed session locally in
                  this browser, and continue into the protected order flow.
                </p>
              </div>
            </section>

            <section className="register-page-panel">
              {registration ? (
                <div className="register-page-success">
                  <h2>Registration complete</h2>
                  <p>Your party has been registered and this browser is now signed in.</p>
                  <div className="register-page-credentials">
                    <div>
                      <span className="register-page-label">Party ID</span>
                      <strong>{registration.partyId}</strong>
                    </div>
                    <div>
                      <span className="register-page-label">Party name</span>
                      <strong>{registration.partyName}</strong>
                    </div>
                    <div>
                      <span className="register-page-label">Contact email</span>
                      <strong>{registration.contactEmail}</strong>
                    </div>
                  </div>
                  <p className="register-page-note">
                    Your credential is stored locally in this browser. You are already signed in and
                    can continue into the protected order flow.
                  </p>
                  <div className="register-page-actions">
                    <button
                      type="button"
                      className="landing-button landing-button-primary"
                      onClick={() => navigate(nextPath)}
                    >
                      Continue
                    </button>
                  </div>
                </div>
              ) : session ? (
                <div className="register-page-success">
                  <h2>Already signed in</h2>
                  <p>
                    You already have a valid local session for this browser. You can continue into the
                    orders area or log out to register a different party.
                  </p>
                  <div className="register-page-credentials">
                    <div>
                      <span className="register-page-label">Party ID</span>
                      <strong>{session.partyId}</strong>
                    </div>
                    <div>
                      <span className="register-page-label">Party name</span>
                      <strong>{session.partyName}</strong>
                    </div>
                    <div>
                      <span className="register-page-label">Contact email</span>
                      <strong>{session.contactEmail}</strong>
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
                      onClick={() => clearStoredSession()}
                    >
                      Log out
                    </button>
                  </div>
                </div>
              ) : (
                <form className="register-page-form" onSubmit={handleSubmit} noValidate>
                  <div className="register-page-field-group">
                    <label htmlFor="partyName">Party name</label>
                    <input
                      id="partyName"
                      name="partyName"
                      value={partyName}
                      onChange={event => setPartyName(event.target.value)}
                      aria-invalid={fieldErrors.partyName ? "true" : "false"}
                      aria-describedby={fieldErrors.partyName ? "partyName-error" : undefined}
                    />
                    {fieldErrors.partyName ? (
                      <p id="partyName-error" className="register-page-field-error">
                        {fieldErrors.partyName}
                      </p>
                    ) : null}
                  </div>

                  <div className="register-page-field-group">
                    <label htmlFor="contactEmail">Contact email</label>
                    <input
                      id="contactEmail"
                      name="contactEmail"
                      type="email"
                      value={contactEmail}
                      onChange={event => setContactEmail(event.target.value)}
                      aria-invalid={fieldErrors.contactEmail ? "true" : "false"}
                      aria-describedby={fieldErrors.contactEmail ? "contactEmail-error" : undefined}
                    />
                    {fieldErrors.contactEmail ? (
                      <p id="contactEmail-error" className="register-page-field-error">
                        {fieldErrors.contactEmail}
                      </p>
                    ) : null}
                  </div>
                  <div className="register-page-field-group">
                    <label htmlFor="password">Password</label>
                    <input
                      id="password"
                      name="password"
                      type="password"
                      value={password}
                      onChange={event => setPassword(event.target.value)}
                      aria-invalid={fieldErrors.password ? "true" : "false"}
                      aria-describedby={fieldErrors.password ? "password-error" : undefined}
                      autoComplete="new-password"
                    />
                    {fieldErrors.password ? (
                      <p id="password-error" className="register-page-field-error">
                        {fieldErrors.password}
                      </p>
                    ) : null}
                  </div>
                  <div className="register-page-field-group">
                    <label htmlFor="confirmPassword">Confirm password</label>
                    <input
                      id="confirmPassword"
                      name="confirmPassword"
                      type="password"
                      value={confirmPassword}
                      onChange={event => setConfirmPassword(event.target.value)}
                      aria-invalid={fieldErrors.confirmPassword ? "true" : "false"}
                      aria-describedby={
                        fieldErrors.confirmPassword ? "confirmPassword-error" : undefined
                      }
                      autoComplete="new-password"
                    />
                    {fieldErrors.confirmPassword ? (
                      <p id="confirmPassword-error" className="register-page-field-error">
                        {fieldErrors.confirmPassword}
                      </p>
                    ) : null}
                  </div>

                  {submitError ? <p className="register-page-submit-error">{submitError}</p> : null}

                  <div className="register-page-actions">
                    <button
                      type="submit"
                      className="landing-button landing-button-primary"
                      disabled={
                        submitting ||
                        !partyName.trim() ||
                        !contactEmail.trim() ||
                        !password.trim() ||
                        !confirmPassword.trim()
                      }
                    >
                      {submitting ? "Registering..." : "Register party"}
                    </button>
                    <AppLink
                      href={`/login?next=${encodeURIComponent(nextPath)}`}
                      className="landing-button landing-button-secondary"
                    >
                      Log in instead
                    </AppLink>
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
