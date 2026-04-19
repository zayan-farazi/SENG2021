import { useEffect, useId, useRef, useState } from "react";
import { ChevronDown, FileText } from "lucide-react";
import { AppLink, navigate } from "./AppLink";
import { clearStoredSession, useStoredSession } from "../session";

type AppHeaderProps = {
  onAuthAction?: () => void;
};

export function AppHeader({ onAuthAction }: AppHeaderProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const session = useStoredSession();
  const menuId = useId();
  const headerActionsRef = useRef<HTMLDivElement | null>(null);
  const currentPath = window.location.pathname;

  const closeMenu = () => {
    setMenuOpen(false);
  };

  const handleLogout = () => {
    clearStoredSession();
    closeMenu();
    onAuthAction?.();
    navigate("/");
  };

  useEffect(() => {
    if (!menuOpen) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (!headerActionsRef.current?.contains(event.target as Node)) {
        closeMenu();
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeMenu();
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [menuOpen]);

  const signedInItems = [
    { href: "/", label: "Home" },
    { href: "/marketplace", label: "Browse marketplace" },
    { href: "/inventory", label: "Manage inventory" },
    { href: "/orders", label: "Orders dashboard" },
  ];

  const signedOutItems = [
    { href: "/", label: "Home" },
    { href: "/register", label: "Register" },
    { href: "/login", label: "Log in" },
  ];

  const menuItems = session ? signedInItems : signedOutItems;

  return (
    <header className="landing-topbar">
      <div className="landing-topbar-inner">
        <AppLink href="/" className="landing-logo" onClick={closeMenu}>
          <span className="landing-logo-mark" aria-hidden="true">
            <FileText size={16} strokeWidth={2.1} />
          </span>
          <span className="landing-logo-text">LockedOut</span>
        </AppLink>

        <div className="landing-header-actions" ref={headerActionsRef}>
          <button
            type="button"
            className={session ? "landing-account-chip" : "landing-account-chip landing-account-chip-guest"}
            onClick={() => setMenuOpen(open => !open)}
            aria-label={menuOpen ? "Close account menu" : "Open account menu"}
            aria-expanded={menuOpen}
            aria-controls={menuId}
          >
            <span className="landing-account-chip-label">
              {session ? session.contactEmail : "Guest"}
            </span>
            {session ? (
              <ChevronDown
                size={14}
                aria-hidden="true"
                className={menuOpen ? "landing-account-chip-icon landing-account-chip-icon-open" : "landing-account-chip-icon"}
              />
            ) : null}
          </button>

          {menuOpen ? (
            <div className="landing-menu-panel-wrap">
              <nav id={menuId} className="landing-menu-panel" aria-label="Main">
                {session ? (
                  <div className="landing-menu-account">
                    <strong>{session.partyName}</strong>
                    <span>{session.contactEmail}</span>
                  </div>
                ) : (
                  <div className="landing-menu-account">
                    <strong>LockedOut</strong>
                    <span>Choose a route to continue</span>
                  </div>
                )}

                <div className="landing-menu-items">
                  {menuItems.map(item => (
                    <AppLink
                      key={item.href}
                      href={item.href}
                      className={`landing-menu-item${currentPath === item.href ? " landing-menu-item-active" : ""}`}
                      aria-current={currentPath === item.href ? "page" : undefined}
                      onClick={closeMenu}
                    >
                      {item.label}
                    </AppLink>
                  ))}
                  {session ? (
                    <button
                      type="button"
                      className="landing-menu-item landing-menu-item-button"
                      onClick={handleLogout}
                    >
                      Log out
                    </button>
                  ) : null}
                </div>
              </nav>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}
