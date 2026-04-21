import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { act } from "react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setStoredSession } from "../session";
import { MarketplacePrototypePage } from "./MarketplacePrototypePage";
import { MarketplaceCheckoutSuccessPage } from "./MarketplaceCheckoutSuccessPage";
import { MarketplaceReviewPage } from "./MarketplaceReviewPage";
import {
  clearStoredMarketplaceCart,
  clearStoredMarketplaceCheckoutSuccess,
  marketplaceProducts,
  writeStoredMarketplaceCheckoutSuccess,
  writeStoredMarketplaceCart,
} from "./marketplacePrototypeData";

class MockWebSocket extends EventTarget {
  static instances: MockWebSocket[] = [];
  static OPEN = 1;
  static CLOSED = 3;

  url: string;
  readyState = 0;
  sentMessages: string[] = [];

  constructor(url: string) {
    super();
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(message: string) {
    this.sentMessages.push(message);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.dispatchEvent(new Event("close"));
  }

  open() {
    this.readyState = MockWebSocket.OPEN;
    this.dispatchEvent(new Event("open"));
  }

  emitMessage(data: unknown) {
    this.dispatchEvent(new MessageEvent("message", { data: JSON.stringify(data) }));
  }
}

class MockSpeechRecognition {
  static instances: MockSpeechRecognition[] = [];

  continuous = false;
  interimResults = false;
  lang = "";
  onstart: (() => void) | null = null;
  onresult: ((event: any) => void) | null = null;
  onerror: ((event: any) => void) | null = null;
  onend: (() => void) | null = null;

  constructor() {
    MockSpeechRecognition.instances.push(this);
  }

  start = vi.fn(() => {
    this.onstart?.();
  });

  stop = vi.fn(() => {
    this.onend?.();
  });
}

function installSpeechRecognition() {
  Object.defineProperty(window, "SpeechRecognition", {
    configurable: true,
    writable: true,
    value: MockSpeechRecognition,
  });
  Object.defineProperty(globalThis, "SpeechRecognition", {
    configurable: true,
    writable: true,
    value: MockSpeechRecognition,
  });
  delete (window as any).webkitSpeechRecognition;
}

function emitTranscript(text: string) {
  const recognition = MockSpeechRecognition.instances.at(-1);
  if (!recognition) {
    throw new Error("No speech recognition instance was created.");
  }

  act(() => {
    recognition.onresult?.({
      resultIndex: 0,
      results: [{ isFinal: true, 0: { transcript: text } }],
    });
    recognition.onend?.();
  });
}

function openAssistantSocket() {
  const socket = MockWebSocket.instances.at(-1);
  if (!socket) {
    throw new Error("No marketplace assistant websocket was created.");
  }

  act(() => {
    socket.open();
  });

  return socket;
}

function buildMarketplaceCatalogueResponse() {
  return {
    items: [
      {
        prod_id: 101,
        party_id: "orders@harbourstudio.example",
        name: "Handmade ceramic mug",
        price: 34,
        unit: "EA",
        description: "Handmade ceramic mug",
        category: "Homeware",
        release_date: "2026-04-20",
        available_units: 9,
        is_visible: true,
        show_soldout: true,
        image_url: "https://example.test/mug.webp",
      },
      {
        prod_id: 102,
        party_id: "sales@northlanevintage.example",
        name: "Vintage denim jacket",
        price: 62,
        unit: "EA",
        description: "Vintage denim jacket",
        category: "Fashion",
        release_date: "2026-04-20",
        available_units: 3,
        is_visible: true,
        show_soldout: true,
        image_url: "https://example.test/jacket.webp",
      },
      {
        prod_id: 103,
        party_id: "dispatch@softlight.example",
        name: "Natural soy candle set",
        price: 28,
        unit: "EA",
        description: "Natural soy candle set",
        category: "Homeware",
        release_date: "2026-04-20",
        available_units: 12,
        is_visible: true,
        show_soldout: true,
        image_url: "https://example.test/candle.webp",
      },
      {
        prod_id: 104,
        party_id: "orders@bloomassembly.example",
        name: "Self-care gift box",
        price: 48,
        unit: "EA",
        description: "Self-care gift box",
        category: "Gifts",
        release_date: "2026-03-20",
        available_units: 6,
        is_visible: true,
        show_soldout: true,
        image_url: "https://example.test/gift.webp",
      },
      {
        prod_id: 105,
        party_id: "studio@lineformpress.example",
        name: "Abstract wall print",
        price: 46,
        unit: "EA",
        description: "Abstract wall print",
        category: "Art",
        release_date: "2026-03-20",
        available_units: 14,
        is_visible: true,
        show_soldout: true,
        image_url: "https://example.test/print.webp",
      },
      {
        prod_id: 106,
        party_id: "hello@fieldnotesgoods.example",
        name: "Weekend tote bag",
        price: 31,
        unit: "EA",
        description: "Weekend tote bag",
        category: "Fashion",
        release_date: "2026-03-20",
        available_units: 18,
        is_visible: true,
        show_soldout: true,
        image_url: "https://example.test/tote.webp",
      },
    ],
    page: {
      limit: 100,
      offset: 0,
      hasMore: false,
      total: marketplaceProducts.length,
    },
  };
}

describe("MarketplacePrototypePage", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    MockSpeechRecognition.instances = [];
    installSpeechRecognition();
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => buildMarketplaceCatalogueResponse(),
      }),
    );
  });

  afterEach(() => {
    cleanup();
    window.localStorage.clear();
    clearStoredMarketplaceCart();
    clearStoredMarketplaceCheckoutSuccess();
    window.history.replaceState({}, "", "/");
    vi.unstubAllGlobals();
  });

  it("renders search, filters, products, and cart summary", async () => {
    render(<MarketplacePrototypePage />);

    expect(screen.getByRole("heading", { name: /^marketplace$/i })).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: /search products or sellers/i })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /filter by category/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /cart summary/i })).toBeInTheDocument();
    expect(await screen.findByText("Handmade ceramic mug")).toBeInTheDocument();
  });

  it("updates the cart when quantities change", async () => {
    const user = userEvent.setup();

    render(<MarketplacePrototypePage />);
    await screen.findByText("Handmade ceramic mug");
    await user.click(screen.getByRole("button", { name: /increase handmade ceramic mug/i }));

    expect(screen.getByText(/1 items/i)).toBeInTheDocument();
    const cart = screen.getByRole("heading", { name: /cart summary/i }).closest("aside");
    expect(cart).not.toBeNull();
    expect(within(cart as HTMLElement).getByText("Handmade ceramic mug")).toBeInTheDocument();
    expect(within(cart as HTMLElement).getByText("$34")).toBeInTheDocument();
  });

  it("caps incrementing at the available stock count", async () => {
    const user = userEvent.setup();

    render(<MarketplacePrototypePage />);
    await screen.findByText("Vintage denim jacket");
    const increaseButton = screen.getByRole("button", { name: /increase vintage denim jacket/i });

    await user.click(increaseButton);
    await user.click(increaseButton);
    await user.click(increaseButton);

    expect(increaseButton).toBeDisabled();
    expect(screen.getByText(/3 items/i)).toBeInTheDocument();
  });

  it("shows a no-results state when filters remove every listing", async () => {
    const user = userEvent.setup();

    render(<MarketplacePrototypePage />);
    await screen.findByText("Handmade ceramic mug");
    await user.type(screen.getByRole("searchbox", { name: /search products or sellers/i }), "zzzz");

    expect(screen.getByText(/no listings match these filters/i)).toBeInTheDocument();
    expect(screen.queryByText("Handmade ceramic mug")).not.toBeInTheDocument();
  });

  it("navigates to the review route when the cart has items", async () => {
    const user = userEvent.setup();

    render(<MarketplacePrototypePage />);
    await screen.findByText("Handmade ceramic mug");
    await user.click(screen.getByRole("button", { name: /increase handmade ceramic mug/i }));
    await user.click(screen.getByRole("button", { name: /review order/i }));

    expect(window.location.pathname).toBe("/marketplace/review");
  });

  it("applies marketplace voice search commands through the assistant dock", async () => {
    const user = userEvent.setup();

    render(<MarketplacePrototypePage />);
    await screen.findByText("Handmade ceramic mug");
    const socket = openAssistantSocket();
    await user.click(screen.getByRole("button", { name: /^start$/i }));
    emitTranscript("search candle");
    act(() => {
      socket.emitMessage({
        type: "assistant.command",
        payload: {
          command: { kind: "search", query: "candle" },
        },
      });
    });

    await waitFor(() => {
      expect(screen.getByRole("searchbox", { name: /search products or sellers/i })).toHaveValue(
        "candle",
      );
    });
    expect(screen.getByText(/updated search to candle/i)).toBeInTheDocument();
  });

  it("adds marketplace items via voice commands", async () => {
    const user = userEvent.setup();

    render(<MarketplacePrototypePage />);
    await screen.findByText("Handmade ceramic mug");
    const socket = openAssistantSocket();
    await user.click(screen.getByRole("button", { name: /^start$/i }));
    emitTranscript("add two ceramic mugs");
    act(() => {
      socket.emitMessage({
        type: "assistant.command",
        payload: {
          command: { kind: "change_quantity", productId: "product-101", quantityDelta: 2 },
        },
      });
    });

    await waitFor(() => {
      expect(screen.getByText(/2 items selected/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/added 2 handmade ceramic mug to the cart/i)).toBeInTheDocument();
  });
});

describe("MarketplaceReviewPage", () => {
  beforeEach(() => {
    MockSpeechRecognition.instances = [];
    installSpeechRecognition();
  });

  afterEach(() => {
    cleanup();
    window.localStorage.clear();
    clearStoredMarketplaceCart();
    clearStoredMarketplaceCheckoutSuccess();
    vi.unstubAllGlobals();
  });

  it("renders stored cart lines on the review page", () => {
    setStoredSession({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });
    writeStoredMarketplaceCart({
      lines: [
        {
          productId: "product-101",
          productRecordId: 101,
          name: "Handmade ceramic mug",
          seller: "Harbour Studio",
          sellerEmail: "orders@harbourstudio.example",
          unitPrice: 34,
          quantity: 2,
          stock: 9,
          unitCode: "EA",
          subtotal: 68,
        },
      ],
    });

    render(<MarketplaceReviewPage />);

    expect(screen.getByRole("heading", { name: /review your order/i })).toBeInTheDocument();
    expect(screen.getByText("Handmade ceramic mug")).toBeInTheDocument();
    expect(screen.getAllByText(/\$68/).length).toBeGreaterThan(0);
    expect(screen.getByDisplayValue("buyer@example.com")).toBeInTheDocument();
  });

  it("groups cart lines by seller and submits each order before navigating to success", async () => {
    const user = userEvent.setup();
    setStoredSession({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });
    writeStoredMarketplaceCart({
      lines: [
        {
          productId: "product-101",
          productRecordId: 101,
          name: "Handmade ceramic mug",
          seller: "Harbour Studio",
          sellerEmail: "orders@harbourstudio.example",
          unitPrice: 34,
          quantity: 2,
          stock: 9,
          unitCode: "EA",
          subtotal: 68,
        },
        {
          productId: "product-105",
          productRecordId: 105,
          name: "Abstract wall print",
          seller: "Lineform Press",
          sellerEmail: "studio@lineformpress.example",
          unitPrice: 46,
          quantity: 1,
          stock: 14,
          unitCode: "EA",
          subtotal: 46,
        },
      ],
    });
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ orderId: "ord_1", status: "DRAFT", createdAt: "2026-04-21T00:00:00Z" }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ orderId: "ord_1", status: "SUBMITTED", updatedAt: "2026-04-21T00:01:00Z" }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ orderId: "ord_2", status: "DRAFT", createdAt: "2026-04-21T00:00:00Z" }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ orderId: "ord_2", status: "SUBMITTED", updatedAt: "2026-04-21T00:01:00Z" }),
        }),
    );

    render(<MarketplaceReviewPage />);

    await user.type(screen.getByLabelText(/street/i), "123 Harbour Street");
    await user.type(screen.getByLabelText(/^city$/i), "Sydney");
    await user.type(screen.getByLabelText(/^state$/i), "NSW");
    await user.type(screen.getByLabelText(/postcode/i), "2000");
    await user.clear(screen.getByLabelText(/country/i));
    await user.type(screen.getByLabelText(/country/i), "AU");
    await user.click(screen.getByRole("button", { name: /place orders/i }));

    await waitFor(() => {
      expect(window.location.pathname).toBe("/marketplace/success");
    });
    expect(window.sessionStorage.getItem("lockedout.marketplace-cart")).toBeNull();
    expect(screen.getByText("Harbour Studio")).toBeInTheDocument();
    expect(screen.getByText("Lineform Press")).toBeInTheDocument();
  });

  it("applies checkout field updates from voice transcript conversion", async () => {
    const user = userEvent.setup();
    setStoredSession({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });
    writeStoredMarketplaceCart({
      lines: [
        {
          productId: "product-101",
          productRecordId: 101,
          name: "Handmade ceramic mug",
          seller: "Harbour Studio",
          sellerEmail: "orders@harbourstudio.example",
          unitPrice: 34,
          quantity: 2,
          stock: 9,
          unitCode: "EA",
          subtotal: 68,
        },
      ],
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          payload: {
            buyerEmail: "buyer@example.com",
            buyerName: "Buyer Co",
            sellerEmail: "orders@harbourstudio.example",
            sellerName: "Harbour Studio",
            currency: "AUD",
            issueDate: "2026-04-21",
            notes: "Leave at loading dock",
            delivery: {
              street: "123 Harbour Street",
              city: "Sydney",
              state: "NSW",
              postcode: "2000",
              country: "AU",
              requestedDate: "2026-05-03",
            },
            lines: [
              {
                productName: "Handmade ceramic mug",
                quantity: 2,
                unitCode: "EA",
                unitPrice: "34.00",
              },
            ],
          },
          valid: true,
          issues: [],
          source: "transcript",
        }),
      }),
    );

    render(<MarketplaceReviewPage />);

    await user.click(screen.getByRole("button", { name: /^start$/i }));
    emitTranscript("deliver to 123 Harbour Street next Saturday and add note leave at loading dock");

    await waitFor(() => {
      expect(screen.getByLabelText(/street/i)).toHaveValue("123 Harbour Street");
    });
    expect(screen.getByLabelText(/notes/i)).toHaveValue("Leave at loading dock");
  });

  it("confirms and places checkout orders through voice commands", async () => {
    const user = userEvent.setup();
    setStoredSession({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });
    writeStoredMarketplaceCart({
      lines: [
        {
          productId: "product-101",
          productRecordId: 101,
          name: "Handmade ceramic mug",
          seller: "Harbour Studio",
          sellerEmail: "orders@harbourstudio.example",
          unitPrice: 34,
          quantity: 2,
          stock: 9,
          unitCode: "EA",
          subtotal: 68,
        },
      ],
    });
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            orderId: "ord_voice_1",
            status: "DRAFT",
            createdAt: "2026-04-21T00:00:00Z",
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            orderId: "ord_voice_1",
            status: "SUBMITTED",
            updatedAt: "2026-04-21T00:01:00Z",
          }),
        }),
    );

    render(<MarketplaceReviewPage />);

    await user.type(screen.getByLabelText(/street/i), "123 Harbour Street");
    await user.type(screen.getByLabelText(/^city$/i), "Sydney");
    await user.type(screen.getByLabelText(/^state$/i), "NSW");
    await user.type(screen.getByLabelText(/postcode/i), "2000");
    await user.clear(screen.getByLabelText(/country/i));
    await user.type(screen.getByLabelText(/country/i), "AU");

    await user.click(screen.getByRole("button", { name: /^start$/i }));
    emitTranscript("place order");

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /place order/i })).toBeInTheDocument();
    });

    await user.click(screen.getAllByRole("button", { name: /^place order$/i })[1]!);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/orders/ord_voice_1/edit");
    });
  });

  it("renders the placed-order summary page from stored checkout data", () => {
    writeStoredMarketplaceCheckoutSuccess({
      buyerName: "Buyer Co",
      orders: [
        {
          orderId: "ord_created_1",
          seller: "Harbour Studio",
          sellerEmail: "orders@harbourstudio.example",
          itemCount: 2,
          total: 68,
        },
      ],
    });

    render(<MarketplaceCheckoutSuccessPage />);

    expect(screen.getByRole("heading", { name: /checkout complete/i })).toBeInTheDocument();
    expect(screen.getByText("Harbour Studio")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open first order/i })).toHaveAttribute(
      "href",
      "/orders/ord_created_1/edit",
    );
  });
});
