import { AppHeader } from "../components/AppHeader";
import { AppLink } from "../components/AppLink";
import { useStoredSession } from "../session";

export function OrdersPlaceholderPage() {
  const session = useStoredSession();

  return (
    <div className="landing-root">
      <div className="landing-container">
        <section className="landing-stage">
          <AppHeader />
          <main className="placeholder-shell">
            <section className="placeholder-card">
              <h1>The order area is still being built.</h1>
              <p>
                The backend create flow is already live. This page is the next step for list, detail,
                and management views on top of the same API.
              </p>
              {session ? (
                <p>
                  Registered as {session.partyName} ({session.contactEmail}).
                </p>
              ) : null}
              <div className="placeholder-actions">
                <AppLink href="/orders/create" className="landing-button landing-button-primary">
                  Open create flow
                </AppLink>
                <AppLink href="/" className="landing-button landing-button-secondary">
                  Back to landing page
                </AppLink>
              </div>
            </section>
          </main>
        </section>
      </div>
    </div>
  );
}
