import { AppHeader } from "../components/AppHeader";
import { AppLink } from "../components/AppLink";
import {
  calculateCartTotal,
  readStoredMarketplaceCart,
} from "./marketplacePrototypeData";
import "./marketplace-prototype.css";

function formatPrice(value: number): string {
  return `$${value.toFixed(0)}`;
}

export function MarketplaceReviewPage() {
  const cart = readStoredMarketplaceCart();
  const total = calculateCartTotal(cart.lines);

  return (
    <div className="landing-root">
      <div className="landing-container">
        <section className="landing-stage">
          <AppHeader />

          <main className="marketplace-page marketplace-review-page">
            <section className="marketplace-review-shell" aria-labelledby="marketplace-review-title">
              <div className="marketplace-review-header">
                <div>
                  <p className="marketplace-review-eyebrow">Marketplace review</p>
                  <h1 id="marketplace-review-title">Review your order</h1>
                  <p>
                    This prototype stops after cart review. Delivery details and real order creation
                    come next.
                  </p>
                </div>
              </div>

              {cart.lines.length === 0 ? (
                <div className="marketplace-empty-state">
                  <strong>No items are ready for review.</strong>
                  <span>Add products in the marketplace before moving to this step.</span>
                </div>
              ) : (
                <div className="marketplace-review-lines">
                  {cart.lines.map(line => (
                    <article key={line.productId} className="marketplace-review-line">
                      <div>
                        <strong>{line.name}</strong>
                        <span>
                          {line.seller} · {line.quantity} × {formatPrice(line.unitPrice)}
                        </span>
                      </div>
                      <strong>{formatPrice(line.subtotal)}</strong>
                    </article>
                  ))}

                  <div className="marketplace-review-total">
                    <span>Total</span>
                    <strong>{formatPrice(total)}</strong>
                  </div>
                </div>
              )}

              <div className="marketplace-review-actions">
                <AppLink href="/marketplace" className="marketplace-secondary-action">
                  Back to marketplace
                </AppLink>
                <AppLink href="/orders" className="marketplace-secondary-action">
                  Open orders dashboard
                </AppLink>
              </div>
            </section>
          </main>
        </section>
      </div>
    </div>
  );
}
