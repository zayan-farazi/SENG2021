import { useState } from "react";
import {
  ChartColumn,
  FileText,
  Globe as GlobeIcon,
  Menu,
  Mic,
  ScrollText,
  ShieldCheck,
  X,
} from "lucide-react";
import { motion } from "motion/react";
import { AppLink } from "../components/AppLink";
import { Globe } from "./Globe";

const features = [
  {
    icon: FileText,
    title: "Create UBL 2.1 orders",
    description:
      "Create standards-compliant orders from buyer, seller, delivery, notes, and line-item input.",
  },
  {
    icon: ShieldCheck,
    title: "Protect access with app keys",
    description:
      "Register a party once and use the issued app key for protected order and analytics routes.",
  },
  {
    icon: Mic,
    title: "Use voice-assisted drafting",
    description:
      "Build draft orders from browser speech recognition over the live draft websocket session.",
  },
  {
    icon: GlobeIcon,
    title: "Convert transcripts into drafts",
    description:
      "Turn transcript text into a structured order payload before committing the final order.",
  },
  {
    icon: ScrollText,
    title: "Retrieve JSON and XML",
    description:
      "Fetch order metadata as JSON and retrieve the persisted UBL XML from a dedicated endpoint.",
  },
  {
    icon: ChartColumn,
    title: "Review order analytics",
    description:
      "Inspect buyer, seller, and combined-role analytics across a selected date range.",
  },
];

const stats = [
  { value: "10+", label: "API routes" },
  { value: "2", label: "Draft input paths" },
  { value: "1", label: "Live websocket flow" },
  { value: "24/7", label: "Hosted backend" },
];

const workflow = [
  {
    title: "Register a party",
    description:
      "Create a buyer or seller identity and receive the app key used by the protected routes.",
  },
  {
    title: "Prepare the order",
    description:
      "Use manual entry, transcript conversion, or voice-assisted drafting to build the order payload.",
  },
  {
    title: "Retrieve the result",
    description:
      "Read the order in JSON form, fetch the UBL XML, or review analytics for the same party.",
  },
];

export function LandingPage() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const closeMenu = () => {
    setMobileMenuOpen(false);
  };

  return (
    <div className="landing-root">
      <div className="landing-container">
        <section className="landing-stage">
          <header className="landing-topbar">
            <div className="landing-topbar-inner">
              <AppLink href="/" className="landing-logo" onClick={closeMenu}>
                <span className="landing-logo-mark" aria-hidden="true">
                  <FileText size={16} strokeWidth={2.1} />
                </span>
                <span className="landing-logo-text">LockedOut</span>
              </AppLink>

              <div className="landing-toolbar">
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

          <main className="landing-main">
            <section className="landing-hero" aria-labelledby="landing-title">
              <div className="landing-hero-layout">
                <motion.div
                  className="landing-hero-copy"
                  initial={{ opacity: 0, y: 18 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.45, ease: "easeOut" }}
                >
                  <h1 id="landing-title">
                    Create and manage
                    <span className="landing-hero-accent"> UBL 2.1 orders </span>
                    in one place.
                  </h1>
                  <p>
                    LockedOut gives you a web interface on top of the deployed API so you can
                    register parties, build orders, retrieve UBL XML, and review analytics without
                    falling back to Swagger for every step.
                  </p>
                  <motion.div
                    className="landing-actions landing-actions-centered"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, delay: 0.08, ease: "easeOut" }}
                  >
                    <AppLink href="/orders/create" className="landing-button landing-button-primary">
                      Create order
                    </AppLink>
                    <AppLink href="/orders" className="landing-button landing-button-secondary">
                      View orders
                    </AppLink>
                  </motion.div>
                </motion.div>

                <motion.div
                  className="landing-hero-visual"
                  initial={{ opacity: 0, scale: 0.96 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.6, delay: 0.12, ease: "easeOut" }}
                >
                  <div className="landing-hero-visual-glow" aria-hidden="true" />
                  <Globe />
                </motion.div>
              </div>
            </section>
          </main>
        </section>

        <main className="landing-lower">
          <section className="landing-stats" aria-label="Platform summary">
            <dl className="landing-stats-grid">
              {stats.map(stat => (
                <div key={stat.label} className="landing-stat">
                  <dt>{stat.label}</dt>
                  <dd>{stat.value}</dd>
                </div>
              ))}
            </dl>
          </section>

          <section id="features" className="landing-section" aria-labelledby="features-title">
            <h2 id="features-title" className="landing-section-title">
              What the platform supports
            </h2>
            <div className="landing-feature-grid">
              {features.map(feature => {
                const Icon = feature.icon;
                return (
                  <article key={feature.title} className="landing-feature-card">
                    <div className="landing-feature-row">
                      <Icon size={18} strokeWidth={2.1} />
                      <h3>{feature.title}</h3>
                    </div>
                    <p>{feature.description}</p>
                  </article>
                );
              })}
            </div>
          </section>

          <section id="workflow" className="landing-section" aria-labelledby="workflow-title">
            <h2 id="workflow-title" className="landing-section-title">
              How it works
            </h2>
            <ol className="landing-workflow-list">
              {workflow.map((step, index) => (
                <li key={step.title} className="landing-workflow-item">
                  <span className="landing-workflow-index">{index + 1}</span>
                  <div>
                    <h3>{step.title}</h3>
                    <p>{step.description}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          <section className="landing-section" aria-labelledby="cta-title">
            <div className="landing-cta">
              <div>
                <h2 id="cta-title" className="landing-section-title">
                  Start with the existing draft flow
                </h2>
                <p>
                  The create route and voice-assisted draft flow are already live. The orders area can
                  expand from the same frontend foundation next.
                </p>
              </div>
              <div className="landing-actions landing-actions-inline">
                <AppLink href="/orders/create" className="landing-button landing-button-primary">
                  Open create flow
                </AppLink>
                <AppLink href="/orders" className="landing-button landing-button-secondary">
                  Open orders area
                </AppLink>
              </div>
            </div>
          </section>
        </main>
      </div>

      <footer id="footer" className="landing-footer">
        <div className="landing-container landing-footer-inner">
          <div className="landing-footer-brand">
            <span className="landing-logo-mark" aria-hidden="true">
              <FileText size={14} strokeWidth={2.1} />
            </span>
            <span>LockedOut</span>
          </div>
          <p>University project. Frontend and API for UBL order workflows.</p>
        </div>
      </footer>
    </div>
  );
}
