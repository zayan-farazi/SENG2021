import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { act } from "react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { InventoryPrototypePage } from "./InventoryPrototypePage";
import { setStoredSession } from "../session";

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
    throw new Error("No inventory assistant websocket was created.");
  }

  act(() => {
    socket.open();
  });

  return socket;
}

function inventoryResponse() {
  return {
    items: [
      {
        prod_id: 1,
        party_id: "seller@example.com",
        name: "Ceramic mug",
        price: 34,
        unit: "EA",
        description: "Handmade mug",
        category: "Handcrafted",
        release_date: "2026-04-08T00:00:00Z",
        available_units: 40,
        is_visible: true,
        show_soldout: true,
        image_url: "https://example.com/mug.png",
      },
      {
        prod_id: 2,
        party_id: "seller@example.com",
        name: "Vintage denim jacket",
        price: 62,
        unit: "EA",
        description: "Vintage denim",
        category: "Fashion",
        release_date: "2026-04-14T00:00:00Z",
        available_units: 12,
        is_visible: true,
        show_soldout: true,
        image_url: "https://example.com/jacket.png",
      },
      {
        prod_id: 3,
        party_id: "seller@example.com",
        name: "Abstract wall print",
        price: 46,
        unit: "EA",
        description: "Print",
        category: "Arts & Crafts",
        release_date: "2099-04-22T00:00:00Z",
        available_units: 40,
        is_visible: false,
        show_soldout: true,
        image_url: "https://example.com/print.png",
      },
    ],
    page: {
      limit: 100,
      offset: 0,
      hasMore: false,
      total: 3,
    },
  };
}

describe("InventoryPrototypePage", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    MockSpeechRecognition.instances = [];
    installSpeechRecognition();
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
    setStoredSession({
      partyId: "seller@example.com",
      partyName: "Seller Co",
      contactEmail: "seller@example.com",
      credential: "super-secure-password",
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => inventoryResponse(),
      }),
    );
  });

  afterEach(() => {
    cleanup();
    window.localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("renders launched and draft listing sections", async () => {
    render(<InventoryPrototypePage />);

    expect(await screen.findByRole("heading", { name: /^inventory$/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^launched$/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^draft listings$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^add product$/i })).toBeInTheDocument();
  });

  it("opens the shared editor in add mode", async () => {
    const user = userEvent.setup();

    render(<InventoryPrototypePage />);
    await screen.findByText("Ceramic mug");
    await user.click(screen.getByRole("button", { name: /^add product$/i }));

    expect(screen.getByRole("heading", { name: /^add product$/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/product name/i)).toHaveValue("");
  });

  it("opens the shared editor in edit mode from a product card", async () => {
    const user = userEvent.setup();

    render(<InventoryPrototypePage />);
    await screen.findByText("Ceramic mug");
    await user.click(screen.getByRole("button", { name: /edit ceramic mug/i }));

    expect(screen.getByRole("heading", { name: /^edit product$/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/product name/i)).toHaveValue("Ceramic mug");
  });

  it("filters cards from the search input", async () => {
    const user = userEvent.setup();

    render(<InventoryPrototypePage />);
    await screen.findByText("Ceramic mug");
    await user.type(screen.getByRole("searchbox", { name: /search products/i }), "mug");

    expect(screen.getByText("Ceramic mug")).toBeInTheDocument();
    expect(screen.queryByText("Vintage denim jacket")).not.toBeInTheDocument();
  });

  it("creates a product from an inventory voice command", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/v2/inventory/add")) {
        return {
          ok: true,
          json: async () => ({
            prod_id: 9,
            party_id: "seller@example.com",
            name: "Linen tote",
            price: 31,
            unit: "EA",
            description: "",
            category: "Fashion",
            release_date: null,
            available_units: 8,
            is_visible: true,
            show_soldout: true,
            image_url: "https://example.com/tote.png",
          }),
        } as Response;
      }

      return {
        ok: true,
        json: async () => inventoryResponse(),
      } as Response;
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InventoryPrototypePage />);
    await screen.findByText("Ceramic mug");
    const socket = openAssistantSocket();

    await user.click(screen.getByRole("button", { name: /^start$/i }));
    emitTranscript("create a product called linen tote priced at 31 with 8 in stock in Fashion");
    act(() => {
      socket.emitMessage({
        type: "assistant.command",
        payload: {
          command: {
            kind: "create_product",
            name: "Linen tote",
            price: 31,
            stock: 8,
            category: "Fashion",
            unitCode: "EA",
            isVisible: true,
          },
        },
      });
    });

    expect(
      await screen.findByText(/create linen tote in fashion for \$31\.00 with 8 in stock/i),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /create product/i }));

    await waitFor(() => {
      expect(screen.getByText("Linen tote")).toBeInTheDocument();
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/v2/inventory/add"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("deletes a product from an inventory voice command", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/v2/inventory/1") && init?.method === "DELETE") {
        return {
          ok: true,
          json: async () => ({}),
        } as Response;
      }

      return {
        ok: true,
        json: async () => inventoryResponse(),
      } as Response;
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InventoryPrototypePage />);
    await screen.findByText("Ceramic mug");
    const socket = openAssistantSocket();

    await user.click(screen.getByRole("button", { name: /^start$/i }));
    emitTranscript("delete ceramic mug");
    act(() => {
      socket.emitMessage({
        type: "assistant.command",
        payload: {
          command: {
            kind: "delete_product",
            productId: "1",
            productName: "Ceramic mug",
          },
        },
      });
    });

    expect(await screen.findByText(/delete ceramic mug from inventory/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /delete product/i }));

    await waitFor(() => {
      expect(screen.queryByText("Ceramic mug")).not.toBeInTheDocument();
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/v2/inventory/1"),
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
