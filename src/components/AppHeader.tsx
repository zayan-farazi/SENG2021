import { useState } from "react";
import { FileText, Menu, X } from "lucide-react";
import { AppLink, navigate } from "./AppLink";
import { clearStoredSession, useStoredSession } from "../session";

type AppHeaderProps = {
  onAuthAction?: () => void;
};

export function AppHeader({ onAuthAction }: AppHeaderProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const session = useStoredSession();

  const closeMenu = () => {
    setMobileMenuOpen(false);
  };

  const handleLogout = () => {
    clearStoredSession();
    closeMenu();
    onAuthAction?.();
    navigate("/");
  };

  return (
    <header className="landing-topbar">
      <div className="landing-topbar-inner">
        <AppLink href="/" className="landing-logo" onClick={closeMenu}>
          <span className="landing-logo-mark" aria-hidden="true">
            <FileText size={16} strokeWidth={2.1} />
          </span>
          <span className="landing-logo-text">LockedOut</span>
        </AppLink>

        <div className="landing-toolbar">
          {!session ? (
            <>
              <AppLink href="/register" className="landing-button landing-button-secondary">
                Register
              </AppLink>
              <AppLink href="/login" className="landing-button landing-button-secondary">
                Log in
              </AppLink>
            </>
          ) : null}
          {session ? (
            <>
              <AppLink href="/orders" className="landing-button landing-button-secondary">
                Orders
              </AppLink>
              <AppLink href="/orders/create" className="landing-button landing-button-primary">
                Create order
              </AppLink>
              <button
                type="button"
                className="landing-button landing-button-secondary landing-button-reset"
                onClick={handleLogout}
              >
                Log out
              </button>
            </>
          ) : null}
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
              {!session ? (
                <>
                  <AppLink
                    href="/register"
                    className="landing-button landing-button-secondary"
                    onClick={closeMenu}
                  >
                    Register
                  </AppLink>
                  <AppLink
                    href="/login"
                    className="landing-button landing-button-secondary"
                    onClick={closeMenu}
                    >
                      Log in
                    </AppLink>
                </>
              ) : null}
              {session ? (
                <>
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
                  <button
                    type="button"
                    className="landing-button landing-button-secondary landing-button-reset"
                    onClick={handleLogout}
                  >
                    Log out
                  </button>
                </>
              ) : null}
            </div>
          </nav>
        </div>
      ) : null}
    </header>
  );
}
