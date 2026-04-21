import { AppHeader } from "../components/AppHeader";
import { AppLink } from "../components/AppLink";
import { readStoredMarketplaceCheckoutSuccess } from "./marketplacePrototypeData";
import "./marketplace-prototype.css";

function formatPrice(value: number): string {
  return `$${value.toFixed(0)}`;
}

export function MarketplaceCheckoutSuccessPage() {
  const summary = readStoredMarketplaceCheckoutSuccess();

  return (
    <div className="landing-root">
      <div className="landing-container">
        <section className="landing-stage">
          <AppHeader />

          <main className="marketplace-page marketplace-review-page">
            <section className="marketplace-review-shell" aria-labelledby="marketplace-success-title">
              <div className="marketplace-review-header">
                <div>
                  <p className="marketplace-review-eyebrow">Orders placed</p>
                  <h1 id="marketplace-success-title">Checkout complete</h1>
                  <p>
                    {summary
                      ? `${summary.orders.length} seller orders were created and submitted for ${summary.buyerName}.`
                      : "The checkout summary is no longer stored in this browser session."}
                  </p>
                </div>
              </div>

              {!summary ? (
                <div className="marketplace-empty-state">
                  <strong>No placed-order summary is available.</strong>
                  <span>Return to the marketplace or open the orders dashboard to continue.</span>
                </div>
              ) : (
                <div className="marketplace-review-lines">
                  {summary.orders.map(order => (
                    <article key={order.orderId} className="marketplace-review-line">
                      <div>
                        <strong>{order.seller}</strong>
                        <span>
                          {order.itemCount} items · {formatPrice(order.total)}
                        </span>
                      </div>
                      <AppLink
                        href={`/orders/${order.orderId}/edit`}
                        className="marketplace-inline-link"
                      >
                        Open order
                      </AppLink>
                    </article>
                  ))}
                </div>
              )}

              <div className="marketplace-review-actions">
                <AppLink href="/orders" className="marketplace-secondary-action">
                  Open orders dashboard
                </AppLink>
                <AppLink
                  href={summary?.orders[0] ? `/orders/${summary.orders[0].orderId}/edit` : "/marketplace"}
                  className="marketplace-primary-link"
                >
                  {summary?.orders[0] ? "Open first order" : "Return to marketplace"}
                </AppLink>
              </div>
            </section>
          </main>
        </section>
      </div>
    </div>
  );
}
