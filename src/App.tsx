import "./index.css";
import "./landing/landing.css";
import { useEffect, useState } from "react";
import { LandingPage } from "./landing/LandingPage";
import { InventoryPrototypePage } from "./pages/InventoryPrototypePage";
import { LoginPage } from "./pages/LoginPage";
import { MarketplacePrototypePage } from "./pages/MarketplacePrototypePage";
import { MarketplaceReviewPage } from "./pages/MarketplaceReviewPage";
import {
  OrdersAnalyticsPage,
  OrdersPage,
} from "./pages/OrdersPlaceholderPage";
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
  return match?.[1] ? decodeURIComponent(match[1]) : null;
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
    pathname === "/orders/analytics" ||
    pathname === "/orders/create" ||
    pathname === "/marketplace" ||
    pathname === "/marketplace/review" ||
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
      return <OrdersPage />;
    case "/orders/analytics":
      return <OrdersAnalyticsPage />;
    case "/orders/create":
      return <VoiceOrderDemo />;
    case "/marketplace":
      return <MarketplacePrototypePage />;
    case "/marketplace/review":
      return <MarketplaceReviewPage />;
    case "/inventory":
      return <InventoryPrototypePage />;
    default:
      return editOrderId ? <VoiceOrderDemo orderId={editOrderId} /> : <LandingPage />;
  }
}

export default App;
