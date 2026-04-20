import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setStoredSession } from "./session";
import {
  clearStoredMarketplaceCart,
  writeStoredMarketplaceCart,
} from "./pages/marketplacePrototypeData";

vi.mock("cobe", () => ({
  default: () => ({
    destroy() {},
  }),
}));

import { App } from "./App";

class MockWebSocket extends EventTarget {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;

  constructor(public readonly url: string) {
    super();
  }

  send() {}

  close() {
    this.readyState = MockWebSocket.CLOSED;
  }
}

class MockIntersectionObserver {
  constructor(private readonly callback: IntersectionObserverCallback) {}

  observe(target: Element) {
    this.callback(
      [
        {
          isIntersecting: true,
          target,
          intersectionRatio: 1,
          boundingClientRect: target.getBoundingClientRect(),
          intersectionRect: target.getBoundingClientRect(),
          rootBounds: null,
          time: performance.now(),
        } as IntersectionObserverEntry,
      ],
      this as unknown as IntersectionObserver,
    );
  }

  unobserve() {}

  disconnect() {}

  takeRecords() {
    return [];
  }
}

class MockResizeObserver {
  constructor(private readonly callback: ResizeObserverCallback) {}

  observe(target: Element) {
    this.callback(
      [
        {
          target,
          contentRect: target.getBoundingClientRect(),
          borderBoxSize: [],
          contentBoxSize: [],
          devicePixelContentBoxSize: [],
        } as ResizeObserverEntry,
      ],
      this as unknown as ResizeObserver,
    );
  }

  unobserve() {}

  disconnect() {}
}

describe("App routing", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/");
    window.localStorage.clear();
    clearStoredMarketplaceCart();
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener() {},
      removeListener() {},
      addEventListener() {},
      removeEventListener() {},
      dispatchEvent() {
        return false;
      },
    }));
    vi.stubGlobal(
      "IntersectionObserver",
      MockIntersectionObserver as unknown as typeof IntersectionObserver,
    );
    vi.stubGlobal("ResizeObserver", MockResizeObserver as unknown as typeof ResizeObserver);
    delete (window as any).SpeechRecognition;
    delete (window as any).webkitSpeechRecognition;
    delete (globalThis as any).SpeechRecognition;
  });

  afterEach(() => {
    cleanup();
    clearStoredMarketplaceCart();
    vi.unstubAllGlobals();
  });

  it("renders the landing page at the root path", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", {
        name: /browse products\. build orders\. manage inventory\./i,
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /browse marketplace/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /manage inventory/i }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("link", { name: /create draft order/i })).not.toBeInTheDocument();
  });

  it("redirects /orders to login when no session exists", async () => {
    window.history.replaceState({}, "", "/orders");

    render(<App />);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/login");
    });
    expect(window.location.search).toBe("?next=%2Forders");
    expect(screen.getByRole("heading", { name: /log back in with your email and password/i })).toBeInTheDocument();
  });

  it("renders the dashboard for /orders when a session exists", async () => {
    setStoredSession({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });
    window.history.replaceState({}, "", "/orders");
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            items: [],
            page: { limit: 10, offset: 0, hasMore: false, total: 0 },
          }),
        }),
    );

    render(<App />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", {
          name: /orders and analytics/i,
        }),
      ).toBeInTheDocument();
    });
  });

  it("renders the registration page for /register", () => {
    window.history.replaceState({}, "", "/register");

    render(<App />);

    expect(
      screen.getByRole("heading", {
        name: /register a party with an email and password/i,
      }),
    ).toBeInTheDocument();
  });

  it("renders the login page for /login", () => {
    window.history.replaceState({}, "", "/login");

    render(<App />);

    expect(
      screen.getByRole("heading", {
        name: /log back in with your email and password/i,
      }),
    ).toBeInTheDocument();
  });

  it("navigates to the marketplace route from the landing page CTA when a session exists", async () => {
    const user = userEvent.setup();
    setStoredSession({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });

    render(<App />);

    const heroHeading = screen.getByRole("heading", {
      name: /browse products\. build orders\. manage inventory\./i,
    });
    const hero = heroHeading.closest("section");
    expect(hero).not.toBeNull();
    await user.click(within(hero as HTMLElement).getByRole("link", { name: /browse marketplace/i }));

    expect(
      screen.getByRole("heading", {
        name: /^marketplace$/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /review order/i })).toBeInTheDocument();
    expect(screen.getByText(/available listings/i)).toBeInTheDocument();
    expect(window.location.pathname).toBe("/marketplace");
  });

  it("navigates from marketplace browsing into the review route when a session exists", async () => {
    const user = userEvent.setup();
    setStoredSession({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });
    window.history.replaceState({}, "", "/marketplace");

    render(<App />);

    await user.click(screen.getByRole("button", { name: /increase handmade ceramic mug/i }));
    await user.click(screen.getByRole("button", { name: /review order/i }));

    expect(screen.getByRole("heading", { name: /review your order/i })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/marketplace/review");
  });

  it("navigates to the inventory route from the landing page CTA when a session exists", async () => {
    const user = userEvent.setup();
    setStoredSession({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });

    render(<App />);

    const heroHeading = screen.getByRole("heading", {
      name: /browse products\. build orders\. manage inventory\./i,
    });
    const hero = heroHeading.closest("section");
    expect(hero).not.toBeNull();
    await user.click(within(hero as HTMLElement).getByRole("link", { name: /manage inventory/i }));

    expect(
      screen.getByRole("heading", {
        name: /^inventory$/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/launched/i)).toBeInTheDocument();
    expect(screen.getByText(/draft listings/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add product/i })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /view all/i }).length).toBeGreaterThan(0);
    expect(window.location.pathname).toBe("/inventory");
  });

  it("opens and closes the mobile menu", async () => {
    const user = userEvent.setup();

    render(<App />);

    const menuButton = screen.getByRole("button", { name: /open account menu/i });
    expect(screen.getByText(/guest/i)).toBeInTheDocument();
    await user.click(menuButton);

    expect(screen.getByRole("button", { name: /close account menu/i })).toBeInTheDocument();
    const menuNav = screen.getByRole("navigation", { name: /main/i });
    expect(within(menuNav).getByRole("link", { name: /^home$/i })).toBeInTheDocument();
    expect(within(menuNav).getByRole("link", { name: /^register$/i })).toBeInTheDocument();
    expect(within(menuNav).getByRole("link", { name: /^log in$/i })).toBeInTheDocument();
    expect(within(menuNav).queryByRole("link", { name: /^orders dashboard$/i })).not.toBeInTheDocument();
    expect(within(menuNav).queryByRole("link", { name: /^browse marketplace$/i })).not.toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("navigation", { name: /main/i })).not.toBeInTheDocument();
  });

  it("closes the dropdown when clicking outside the header actions", async () => {
    const user = userEvent.setup();

    render(<App />);

    await user.click(screen.getByRole("button", { name: /open account menu/i }));
    expect(screen.getByRole("navigation", { name: /main/i })).toBeInTheDocument();

    await user.click(document.body);
    expect(screen.queryByRole("navigation", { name: /main/i })).not.toBeInTheDocument();
  });

  it("shows the signed-in email in the header and routes navigation through the dropdown", async () => {
    const user = userEvent.setup();
    setStoredSession({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });

    render(<App />);

    const header = screen.getByRole("banner");
    expect(within(header).getByText("buyer@example.com")).toBeInTheDocument();
    expect(within(header).queryByRole("link", { name: /^orders dashboard$/i })).not.toBeInTheDocument();
    expect(within(header).queryByRole("link", { name: /^browse marketplace$/i })).not.toBeInTheDocument();

    await user.click(within(header).getByRole("button", { name: /open account menu/i }));
    const menuNav = screen.getByRole("navigation", { name: /main/i });
    expect(within(menuNav).getByRole("link", { name: /^home$/i })).toBeInTheDocument();
    expect(within(menuNav).getByRole("link", { name: /^browse marketplace$/i })).toBeInTheDocument();
    expect(within(menuNav).getByRole("link", { name: /^manage inventory$/i })).toBeInTheDocument();
    expect(within(menuNav).getByRole("link", { name: /^orders dashboard$/i })).toBeInTheDocument();
    await user.click(within(menuNav).getByRole("button", { name: /log out/i }));

    expect(window.localStorage.getItem("lockedout.session")).toBeNull();
    expect(window.location.pathname).toBe("/");
  });

  it("redirects signed-out marketplace clicks to login with the original destination", async () => {
    const user = userEvent.setup();

    render(<App />);

    await user.click(screen.getAllByRole("link", { name: /browse marketplace/i })[0]);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/login");
    });
    expect(window.location.search).toBe("?next=%2Fmarketplace");
  });

  it("redirects signed-out inventory clicks to login with the original destination", async () => {
    const user = userEvent.setup();

    render(<App />);

    await user.click(screen.getAllByRole("link", { name: /manage inventory/i })[0]);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/login");
    });
    expect(window.location.search).toBe("?next=%2Finventory");
  });

  it("redirects /orders/create to login with the original destination when no session exists", async () => {
    window.history.replaceState({}, "", "/orders/create");

    render(<App />);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/login");
    });
    expect(window.location.search).toBe("?next=%2Forders%2Fcreate");
    expect(screen.getByRole("heading", { name: /log back in with your email and password/i })).toBeInTheDocument();
  });

  it("redirects /orders/:orderId/edit to login with the original destination when no session exists", async () => {
    window.history.replaceState({}, "", "/orders/ord_123/edit");

    render(<App />);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/login");
    });
    expect(window.location.search).toBe("?next=%2Forders%2Ford_123%2Fedit");
  });

  it("redirects /marketplace to login with the original destination when no session exists", async () => {
    window.history.replaceState({}, "", "/marketplace");

    render(<App />);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/login");
    });
    expect(window.location.search).toBe("?next=%2Fmarketplace");
  });

  it("redirects /marketplace/review to login with the original destination when no session exists", async () => {
    window.history.replaceState({}, "", "/marketplace/review");

    render(<App />);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/login");
    });
    expect(window.location.search).toBe("?next=%2Fmarketplace%2Freview");
  });

  it("renders the review route with stored marketplace selections when a session exists", () => {
    setStoredSession({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });
    writeStoredMarketplaceCart({
      lines: [
        {
          productId: "market-ceramic-mug",
          name: "Handmade ceramic mug",
          seller: "Harbour Studio",
          unitPrice: 34,
          quantity: 2,
          stock: 9,
          subtotal: 68,
        },
      ],
    });
    window.history.replaceState({}, "", "/marketplace/review");

    render(<App />);

    expect(screen.getByRole("heading", { name: /review your order/i })).toBeInTheDocument();
    expect(screen.getByText("Handmade ceramic mug")).toBeInTheDocument();
  });

  it("redirects /inventory to login with the original destination when no session exists", async () => {
    window.history.replaceState({}, "", "/inventory");

    render(<App />);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/login");
    });
    expect(window.location.search).toBe("?next=%2Finventory");
  });
});
