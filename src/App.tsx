import "./index.css";
import "./landing/landing.css";
import { useEffect, useState } from "react";
import { LandingPage } from "./landing/LandingPage";
import { ExperiencePlaceholderPage } from "./pages/ExperiencePlaceholderPage";
import { InventoryPrototypePage } from "./pages/InventoryPrototypePage";
import { LoginPage } from "./pages/LoginPage";
import { OrdersPlaceholderPage } from "./pages/OrdersPlaceholderPage";
import { RegisterPage } from "./pages/RegisterPage";
import { VoiceOrderDemo } from "./VoiceOrderDemo";
import { navigate } from "./components/AppLink";
import { useStoredSession } from "./session";

function getCurrentPath(): string {
  return `${window.location.pathname || "/"}${window.location.search || ""}`;
}

function buildLoginRedirect(pathname: string, search: string): string {
  const requestedPath = `${pathname}${search}`;
  return `/login?next=${encodeURIComponent(requestedPath)}`;
}

function getEditOrderId(pathname: string): string | null {
  const match = pathname.match(/^\/orders\/([^/]+)\/edit$/);
  return match ? decodeURIComponent(match[1]) : null;
}

export function App() {
  const [path, setPath] = useState(getCurrentPath);
  const session = useStoredSession();
  const currentUrl = new URL(path, window.location.origin);
  const pathname = currentUrl.pathname;
  const search = currentUrl.search;
  const editOrderId = getEditOrderId(pathname);
  const isProtectedRoute =
    pathname === "/orders" ||
    pathname === "/orders/create" ||
    pathname === "/marketplace" ||
    pathname === "/inventory" ||
    editOrderId !== null;

  useEffect(() => {
    const handleLocationChange = () => {
      setPath(getCurrentPath());
    };

    window.addEventListener("popstate", handleLocationChange);
    window.addEventListener("app:navigate", handleLocationChange);

    return () => {
      window.removeEventListener("popstate", handleLocationChange);
      window.removeEventListener("app:navigate", handleLocationChange);
    };
  }, []);

  useEffect(() => {
    if (!session && isProtectedRoute) {
      navigate(buildLoginRedirect(pathname, search));
    }
  }, [isProtectedRoute, pathname, search, session]);

  if (!session && isProtectedRoute) {
    return null;
  }

  switch (pathname) {
    case "/login":
      return <LoginPage />;
    case "/register":
      return <RegisterPage />;
    case "/orders":
      return <OrdersPlaceholderPage />;
    case "/orders/create":
      return <VoiceOrderDemo />;
    case "/marketplace":
      return (
        <ExperiencePlaceholderPage
          eyebrow="Marketplace"
          title="Marketplace browsing is the next build target."
          description="This route will become the shared catalogue and cart experience. For now, use the existing order flow while the marketplace UI is being built."
          primaryHref="/orders/create"
          primaryLabel="Open current order flow"
          secondaryHref="/orders"
          secondaryLabel="Open orders dashboard"
        />
      );
    case "/inventory":
      return <InventoryPrototypePage />;
    default:
      return editOrderId ? <VoiceOrderDemo orderId={editOrderId} /> : <LandingPage />;
  }
}

export default App;
