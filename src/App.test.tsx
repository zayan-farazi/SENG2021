import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setStoredSession } from "./session";

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
    vi.unstubAllGlobals();
  });

  it("renders the landing page at the root path", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", {
        name: /create and manage ubl 2\.1 orders in one place/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /register/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /log in/i }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("link", { name: /create order/i })).not.toBeInTheDocument();
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

  it("navigates to the create route from the landing page CTA when a session exists", async () => {
    const user = userEvent.setup();
    setStoredSession({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });

    render(<App />);

    const heroHeading = screen.getByRole("heading", {
      name: /create and manage ubl 2\.1 orders in one place/i,
    });
    const hero = heroHeading.closest("section");
    expect(hero).not.toBeNull();
    await user.click(within(hero as HTMLElement).getByRole("link", { name: /create order/i }));

    expect(
      screen.getByRole("heading", {
        name: /speak the order\. watch the draft settle in real time\./i,
      }),
    ).toBeInTheDocument();
    expect(window.location.pathname).toBe("/orders/create");
  });

  it("opens and closes the mobile menu", async () => {
    const user = userEvent.setup();

    render(<App />);

    const menuButton = screen.getByRole("button", { name: /open menu/i });
    await user.click(menuButton);

    expect(screen.getByRole("button", { name: /close menu/i })).toBeInTheDocument();
    const mobileNav = screen.getByRole("navigation", { name: /mobile/i });
    expect(within(mobileNav).getByRole("link", { name: /^register$/i })).toBeInTheDocument();
    expect(within(mobileNav).getByRole("link", { name: /^log in$/i })).toBeInTheDocument();
    expect(within(mobileNav).queryByRole("link", { name: /^orders$/i })).not.toBeInTheDocument();
  });

  it("hides register and log in when a session already exists and allows logout", async () => {
    const user = userEvent.setup();
    setStoredSession({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });

    render(<App />);

    expect(screen.queryByRole("link", { name: /^register$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^log in$/i })).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /^orders$/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /^create order$/i }).length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: /log out/i }));

    expect(window.localStorage.getItem("lockedout.session")).toBeNull();
    expect(window.location.pathname).toBe("/");
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
});
