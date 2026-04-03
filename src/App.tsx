import "./index.css";
import "./landing/landing.css";
import { useEffect, useState } from "react";
import { LandingPage } from "./landing/LandingPage";
import { OrdersPlaceholderPage } from "./pages/OrdersPlaceholderPage";
import { VoiceOrderDemo } from "./VoiceOrderDemo";

function getCurrentPath(): string {
  return window.location.pathname || "/";
}

export function App() {
  const [path, setPath] = useState(getCurrentPath);

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

  switch (path) {
    case "/orders":
      return <OrdersPlaceholderPage />;
    case "/orders/create":
      return <VoiceOrderDemo />;
    default:
      return <LandingPage />;
  }
}

export default App;
