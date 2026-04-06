import { useMemo, useState, type FormEvent } from "react";
import { FileText, Menu, X } from "lucide-react";
import { AppLink, navigate } from "../components/AppLink";
import { getBackendHttpUrl } from "../voiceOrder";
import { setStoredSession, type StoredSession } from "../session";
import "../register-page.css";

type PartyRegistrationResponse = {
  partyId: string;
  partyName: string;
  appKey: string;
  message: string;
};

type ValidationErrorItem = {
  path: string;
  message: string;
};

type ValidationErrorResponse = {
  message: string;
  errors?: ValidationErrorItem[];
};

export function RegisterPage() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [partyName, setPartyName] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [registration, setRegistration] = useState<(StoredSession & { message: string }) | null>(null);
  const backendUrl = useMemo(() => getBackendHttpUrl(), []);

  const closeMenu = () => {
    setMobileMenuOpen(false);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    setFieldErrors({});

    try {
      const response = await fetch(`${backendUrl}/v1/parties/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          partyName,
          contactEmail,
        }),
      });

      if (response.status === 201) {
        const body = (await response.json()) as PartyRegistrationResponse;
        const storedSession: StoredSession = {
          partyId: body.partyId,
          partyName: body.partyName,
          contactEmail: contactEmail.trim().toLowerCase(),
          appKey: body.appKey,
        };
        setStoredSession(storedSession);
        setRegistration({ ...storedSession, message: body.message });
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
          <header className="landing-topbar">
            <div className="landing-topbar-inner">
              <AppLink href="/" className="landing-logo" onClick={closeMenu}>
                <span className="landing-logo-mark" aria-hidden="true">
                  <FileText size={16} strokeWidth={2.1} />
                </span>
                <span className="landing-logo-text">LockedOut</span>
              </AppLink>

              <div className="landing-toolbar">
                <AppLink href="/register" className="landing-button landing-button-secondary">
                  Register
                </AppLink>
                <AppLink href="/orders" className="landing-button landing-button-secondary">
                  Orders
                </AppLink>
                <AppLink href="/orders/create" className="landing-button landing-button-primary">
                  Create order
                </AppLink>
              </div>

              <button
                type="button"
                className="landing-menu-button"
                onClick={() => setMobileMenuOpen(open => !open)}
                aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
                aria-expanded={mobileMenuOpen}
              >
                {mobileMenuOpen ? <X size={18} /> : <Menu size={18} />}
              </button>
            </div>

            {mobileMenuOpen ? (
              <div className="landing-mobile-nav-wrap">
                <nav className="landing-mobile-nav" aria-label="Mobile">
                  <div className="landing-mobile-actions">
                    <AppLink
                      href="/register"
                      className="landing-button landing-button-secondary"
                      onClick={closeMenu}
                    >
                      Register
                    </AppLink>
                    <AppLink
                      href="/orders"
                      className="landing-button landing-button-secondary"
                      onClick={closeMenu}
                    >
                      Orders
                    </AppLink>
                    <AppLink
                      href="/orders/create"
                      className="landing-button landing-button-primary"
                      onClick={closeMenu}
                    >
                      Create order
                    </AppLink>
                  </div>
                </nav>
              </div>
            ) : null}
          </header>

          <main className="register-page-main">
            <section className="register-page-intro">
              <div>
                <h1>Register a party and store the app key once.</h1>
                <p>
                  The frontend uses the same lightweight auth model as the backend. Register a buyer
                  or seller identity, save the returned app key locally, and continue into the
                  protected order flow.
                </p>
              </div>
            </section>

            <section className="register-page-panel">
              {registration ? (
                <div className="register-page-success">
                  <h2>Registration complete</h2>
                  <p>{registration.message}</p>
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
                    <div className="register-page-app-key">
                      <span className="register-page-label">App key</span>
                      <code>{registration.appKey}</code>
                    </div>
                  </div>
                  <p className="register-page-note">
                    This key is now stored locally in this browser. You are already signed in and
                    can continue once you have copied it down.
                  </p>
                  <div className="register-page-actions">
                    <button
                      type="button"
                      className="landing-button landing-button-primary"
                      onClick={() => navigate("/orders")}
                    >
                      Continue to orders
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

                  {submitError ? <p className="register-page-submit-error">{submitError}</p> : null}

                  <div className="register-page-actions">
                    <button
                      type="submit"
                      className="landing-button landing-button-primary"
                      disabled={submitting}
                    >
                      {submitting ? "Registering..." : "Register party"}
                    </button>
                    <AppLink href="/orders/create" className="landing-button landing-button-secondary">
                      Back to create flow
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
