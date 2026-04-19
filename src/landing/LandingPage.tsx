import {
  ChevronRight,
  Gift,
  Package2,
  Search,
  Shirt,
  ShoppingBag,
  Sparkles,
} from "lucide-react";
import { AppLink } from "../components/AppLink";
import { AppHeader } from "../components/AppHeader";
import { useStoredSession } from "../session";

const highlights = [
  {
    icon: Search,
    title: "Browse a seller marketplace",
    description: "Move from product discovery into order building without switching tools.",
  },
  {
    icon: ShoppingBag,
    title: "Build cleaner orders",
    description: "Cart-style quantities and delivery details stay ahead of the XML generation flow.",
  },
  {
    icon: Package2,
    title: "Manage inventory in one place",
    description: "Launch products, track stock, and keep seller-facing work in the same app.",
  },
];

const previewListings = [
  {
    name: "Handmade ceramic mug",
    price: "$34",
    meta: "Sydney seller",
    icon: Gift,
  },
  {
    name: "Vintage denim jacket",
    price: "$62",
    meta: "3 left",
    icon: Shirt,
  },
  {
    name: "Natural soy candle set",
    price: "$28",
    meta: "Ready to ship",
    icon: Sparkles,
  },
];

function buildActionHref(session: ReturnType<typeof useStoredSession>, destination: string): string {
  if (session) {
    return destination;
  }

  return `/login?next=${encodeURIComponent(destination)}`;
}

export function LandingPage() {
  const session = useStoredSession();
  const marketplaceHref = buildActionHref(session, "/marketplace");
  const inventoryHref = buildActionHref(session, "/inventory");

  return (
    <div className="landing-root">
      <div className="landing-container">
        <section className="landing-stage">
          <AppHeader />

          <main className="landing-main">
            <section className="landing-hero" aria-labelledby="landing-title">
              <div className="landing-hero-layout">
                <div className="landing-hero-copy">
                  <h1 id="landing-title">Browse products. Build orders. Manage inventory.</h1>
                  <div className="landing-actions landing-actions-stacked">
                    <AppLink
                      href={marketplaceHref}
                      className="landing-action-card landing-action-card-primary"
                    >
                      <span className="landing-action-card-icon" aria-hidden="true">
                        <ShoppingBag size={18} strokeWidth={2.1} />
                      </span>
                      <span className="landing-action-card-copy">
                        <strong>Browse marketplace</strong>
                        <span>Shop listings, choose quantities, and move into order review.</span>
                      </span>
                      <span className="landing-action-card-arrow" aria-hidden="true">
                        <ChevronRight size={18} strokeWidth={2.2} />
                      </span>
                    </AppLink>
                    <AppLink
                      href={inventoryHref}
                      className="landing-action-card landing-action-card-secondary"
                    >
                      <span className="landing-action-card-icon" aria-hidden="true">
                        <Package2 size={18} strokeWidth={2.1} />
                      </span>
                      <span className="landing-action-card-copy">
                        <strong>Manage inventory</strong>
                        <span>Control listings, stock, and launch dates from one workspace.</span>
                      </span>
                      <span className="landing-action-card-arrow" aria-hidden="true">
                        <ChevronRight size={18} strokeWidth={2.2} />
                      </span>
                    </AppLink>
                  </div>

                  <div className="landing-quick-points" aria-label="Product direction">
                    <span>Minimal marketplace flow</span>
                    <span>Shared buyer and seller workspace</span>
                    <span>Existing XML pipeline preserved</span>
                  </div>
                </div>

                <div className="landing-market-preview" aria-label="Marketplace preview">
                  <div className="landing-preview-shell">
                    <div className="landing-preview-header">
                      <div>
                        <p>Featured this week</p>
                        <strong>Marketplace preview</strong>
                      </div>
                      <span className="landing-preview-pill">
                        <Sparkles size={14} strokeWidth={2.1} />
                        Curated
                      </span>
                    </div>

                    <div className="landing-preview-list">
                      {previewListings.map(listing => {
                        const Icon = listing.icon;
                        return (
                        <article key={listing.name} className="landing-preview-card">
                          <div className="landing-preview-image" aria-hidden="true">
                            <Icon size={22} strokeWidth={2} />
                          </div>
                          <div className="landing-preview-copy">
                            <strong>{listing.name}</strong>
                            <span>{listing.meta}</span>
                          </div>
                          <span className="landing-preview-price">{listing.price}</span>
                        </article>
                        );
                      })}
                    </div>

                    <div className="landing-preview-order">
                      <div className="landing-preview-order-header">
                        <strong>Cart summary</strong>
                        <span>2 items</span>
                      </div>
                      <div className="landing-preview-order-line">
                        <span>Ceramic mug × 2</span>
                        <strong>$68</strong>
                      </div>
                      <div className="landing-preview-order-line">
                        <span>Delivery</span>
                        <strong>$12</strong>
                      </div>
                      <div className="landing-preview-order-total">
                        <span>Total</span>
                        <strong>$80</strong>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section className="landing-support" aria-labelledby="support-title">
              <h2 id="support-title" className="sr-only">
                Marketplace highlights
              </h2>
              <div className="landing-support-grid">
                {highlights.map(item => {
                  const Icon = item.icon;
                  return (
                    <article key={item.title} className="landing-support-card">
                      <span className="landing-support-icon" aria-hidden="true">
                        <Icon size={18} strokeWidth={2.1} />
                      </span>
                      <h3>{item.title}</h3>
                      <p>{item.description}</p>
                    </article>
                  );
                })}
              </div>
            </section>
          </main>
        </section>
      </div>
    </div>
  );
}
