import { AppHeader } from "../components/AppHeader";
import { AppLink } from "../components/AppLink";
import "../landing/landing.css";

type ExperiencePlaceholderPageProps = {
  eyebrow: string;
  title: string;
  description: string;
  primaryHref: string;
  primaryLabel: string;
  secondaryHref: string;
  secondaryLabel: string;
};

export function ExperiencePlaceholderPage({
  eyebrow,
  title,
  description,
  primaryHref,
  primaryLabel,
  secondaryHref,
  secondaryLabel,
}: ExperiencePlaceholderPageProps) {
  return (
    <div className="landing-root">
      <div className="landing-container">
        <section className="landing-stage">
          <AppHeader />

          <main className="landing-main landing-main-placeholder">
            <section className="landing-placeholder-shell" aria-labelledby="placeholder-title">
              <p className="landing-placeholder-eyebrow">{eyebrow}</p>
              <h1 id="placeholder-title">{title}</h1>
              <p className="landing-placeholder-copy">{description}</p>
              <div className="landing-actions landing-actions-centered">
                <AppLink href={primaryHref} className="landing-button landing-button-primary">
                  {primaryLabel}
                </AppLink>
                <AppLink href={secondaryHref} className="landing-button landing-button-secondary">
                  {secondaryLabel}
                </AppLink>
              </div>
            </section>
          </main>
        </section>
      </div>
    </div>
  );
}
