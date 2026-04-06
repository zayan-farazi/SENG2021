import { AppLink } from "../components/AppLink";

export function OrdersPlaceholderPage() {
  return (
    <main className="placeholder-shell">
      <section className="placeholder-card">
        <h1>The order area is still being built.</h1>
        <p>
          The backend create flow is already live. This page is the next step for list, detail, and
          management views on top of the same API.
        </p>
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
  );
}
