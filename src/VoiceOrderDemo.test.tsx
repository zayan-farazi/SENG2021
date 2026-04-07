import { act, StrictMode } from "react";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setStoredSession } from "./session";
import { VoiceOrderDemo } from "./VoiceOrderDemo";
import { emptyDraft, emptyDraftState } from "./voiceOrder";

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

function openSocket() {
  const socket = MockWebSocket.instances.at(-1);
  if (!socket) {
    throw new Error("No websocket instance was created.");
  }

  act(() => {
    socket.open();
  });

  return socket;
}

function draftStatePatch(patch: Partial<ReturnType<typeof emptyDraft>> = {}) {
  return {
    ...emptyDraftState(),
    connectionStatus: "connected",
    draft: { ...emptyDraft(), ...patch },
  };
}

describe("VoiceOrderDemo", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    MockSpeechRecognition.instances = [];
    window.localStorage.clear();
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
    installSpeechRecognition();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows a fallback message when browser speech recognition is unavailable", () => {
    delete (window as any).SpeechRecognition;
    delete (window as any).webkitSpeechRecognition;
    delete (globalThis as any).SpeechRecognition;

    render(<VoiceOrderDemo />);

    expect(
      screen.getByText(/this browser does not expose the web speech api/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /start microphone/i })).toBeDisabled();
  });

  it("renders without crashing when process is unavailable in the browser", () => {
    vi.stubGlobal("process", undefined);

    render(<VoiceOrderDemo />);

    expect(screen.getByText(/speak the order\. watch the draft settle in real time\./i)).toBeInTheDocument();
    expect(screen.getByText(/backend: http:\/\/localhost:8000/i)).toBeInTheDocument();
  });

  it("stays connected under strict mode remounts once the active socket is ready", () => {
    render(
      <StrictMode>
        <VoiceOrderDemo />
      </StrictMode>,
    );

    expect(MockWebSocket.instances).toHaveLength(2);

    act(() => {
      MockWebSocket.instances[1].open();
      MockWebSocket.instances[1].emitMessage({
        type: "session.ready",
        payload: draftStatePatch(),
      });
    });

    expect(screen.getByText("connected")).toBeInTheDocument();
    expect(screen.getByText(/received session\.ready/i)).toBeInTheDocument();
  });

  it("renders transcript echoes and backend annotations", () => {
    render(<VoiceOrderDemo />);
    const socket = openSocket();

    act(() => {
      socket.emitMessage({
        type: "session.ready",
        payload: draftStatePatch(),
      });
      socket.emitMessage({
        type: "transcript.echo",
        payload: { kind: "partial", text: "i want 2 oranges" },
      });
      socket.emitMessage({
        type: "draft.updated",
        payload: {
          appliedChanges: ["Added oranges with quantity 2."],
          state: {
            ...draftStatePatch({
              lines: [{ productName: "oranges", quantity: 2, unitCode: "EA", unitPrice: null }],
            }),
            currentPartial: "",
            transcriptLog: [{ kind: "final", text: "i want 2 oranges" }],
            warnings: [{ transcript: "remove apples", message: "Missing apples" }],
            unresolved: [{ transcript: "next Tuesday afternoon", message: "Unsupported phrase" }],
          },
        },
      });
    });

    expect(screen.getByText("i want 2 oranges")).toBeInTheDocument();
    expect(screen.getByText("Missing apples")).toBeInTheDocument();
    expect(screen.getByText("Unsupported phrase")).toBeInTheDocument();
  });

  it("surfaces browser speech network failures as speech-service diagnostics", () => {
    render(<VoiceOrderDemo />);
    const socket = openSocket();

    act(() => {
      socket.emitMessage({ type: "session.ready", payload: draftStatePatch() });
    });

    fireEvent.click(screen.getByRole("button", { name: /start microphone/i }));

    const recognition = MockSpeechRecognition.instances.at(-1);
    if (!recognition) {
      throw new Error("Speech recognition instance was not created.");
    }

    act(() => {
      recognition.onerror?.({ error: "network", message: "speech service unavailable" });
    });

    expect(
      screen.getByText(/browser speech recognition could not reach its speech service/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      /speech recognition error: network \(speech service unavailable\)/i,
    );
    expect(screen.getByLabelText(/diagnostics log/i)).toHaveTextContent(
      /speech recognition error: network \(speech service unavailable\)/i,
    );
  });

  it("keeps create draft disabled until the draft is valid", () => {
    setStoredSession({
      partyId: "buyer-party",
      partyName: "Acme Books",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });

    render(<VoiceOrderDemo />);
    const socket = openSocket();
    const confirm = screen.getByRole("button", { name: /create draft order/i });

    act(() => {
      socket.emitMessage({ type: "session.ready", payload: draftStatePatch() });
    });
    expect(confirm).toBeDisabled();

    act(() => {
      socket.emitMessage({
        type: "draft.updated",
        payload: {
          appliedChanges: ["Draft updated from form."],
          state: draftStatePatch({
            buyerEmail: "buyer@example.com",
            buyerName: "Acme Books",
            sellerEmail: "seller@example.com",
            sellerName: "Digital Book Supply",
            lines: [{ productName: "oranges", quantity: 2, unitCode: "EA", unitPrice: null }],
          }),
        },
      });
    });

    expect(confirm).toBeEnabled();
  });

  it("shows required field guidance and allows a fully manual draft to become creatable", async () => {
    setStoredSession({
      partyId: "buyer-party",
      partyName: "Acme Books",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });

    render(<VoiceOrderDemo />);
    const socket = openSocket();

    act(() => {
      socket.emitMessage({ type: "session.ready", payload: draftStatePatch() });
    });

    expect(
      screen.getByText(/fields marked \* are required before creating the draft order/i),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/^Seller email$/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByLabelText(/^Buyer email$/i)).toHaveValue("buyer@example.com");
    });

    const confirm = screen.getByRole("button", { name: /create draft order/i });
    expect(confirm).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/^Seller email$/i), {
      target: { value: "seller@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/^Buyer name$/i), {
      target: { value: "Acme Books" },
    });
    fireEvent.change(screen.getByLabelText(/^Seller name$/i), {
      target: { value: "Digital Book Supply" },
    });
    fireEvent.click(screen.getByRole("button", { name: /add line item/i }));
    fireEvent.change(screen.getByLabelText(/line 1 product/i), {
      target: { value: "Oranges" },
    });
    fireEvent.change(screen.getByLabelText(/line 1 quantity/i), {
      target: { value: "2" },
    });

    await waitFor(() => {
      expect(confirm).toBeEnabled();
    });
  });

  it("creates draft orders through the REST endpoint and renders created draft details", async () => {
    setStoredSession({
      partyId: "buyer-party",
      partyName: "Acme Books",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          orderId: "ord_demo1234567890",
          status: "DRAFT",
          createdAt: "2026-03-07T00:00:00Z",
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        text: async () => "<Order />",
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<VoiceOrderDemo />);
    const socket = openSocket();

    act(() => {
      socket.emitMessage({
        type: "session.ready",
        payload: draftStatePatch({
          buyerEmail: "buyer@example.com",
          buyerName: "Acme Books",
          sellerEmail: "seller@example.com",
          sellerName: "Digital Book Supply",
          lines: [{ productName: "oranges", quantity: 2, unitCode: "EA", unitPrice: null }],
        }),
      });
    });

    fireEvent.click(screen.getByRole("button", { name: /create draft order/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        "http://localhost:8000/v1/order/create",
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            Authorization: "Bearer super-secure-password",
            "X-Party-Email": "buyer@example.com",
            "Content-Type": "application/json",
          }),
        }),
      );
    });

    expect(socket.sentMessages.some(message => message.includes("session.commit"))).toBe(false);
    expect(screen.getByRole("heading", { name: /created draft/i })).toBeInTheDocument();
    expect(screen.getByText("ord_demo1234567890")).toBeInTheDocument();
    expect(screen.getByDisplayValue("<Order />")).toBeInTheDocument();
  });

  it("blocks commit when no stored credentials exist", () => {
    render(<VoiceOrderDemo />);
    const socket = openSocket();

    act(() => {
      socket.emitMessage({
        type: "session.ready",
        payload: draftStatePatch({
          buyerEmail: "buyer@example.com",
          buyerName: "Acme Books",
          sellerEmail: "seller@example.com",
          sellerName: "Digital Book Supply",
          lines: [{ productName: "oranges", quantity: 2, unitCode: "EA", unitPrice: null }],
        }),
      });
    });

    fireEvent.click(screen.getByRole("button", { name: /create draft order/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      /log in or register a party first/i,
    );
    expect(socket.sentMessages.some(message => message.includes("session.commit"))).toBe(false);
  });

  it("shows a useful error when the backend blocks draft creation validation", () => {
    setStoredSession({
      partyId: "buyer-party",
      partyName: "Acme Books",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });

    render(<VoiceOrderDemo />);
    const socket = openSocket();

    act(() => {
      socket.emitMessage({
        type: "session.ready",
        payload: draftStatePatch({
          buyerEmail: "buyer@example.com",
          buyerName: "Acme Books",
          sellerName: "Digital Book Supply",
          lines: [{ productName: "oranges", quantity: 2, unitCode: "EA", unitPrice: null }],
        }),
      });
    });

    act(() => {
      socket.emitMessage({
        type: "commit.blocked",
        payload: {
          errors: [{ loc: ["sellerEmail"] }],
          state: draftStatePatch({
            buyerEmail: "buyer@example.com",
            buyerName: "Acme Books",
            sellerName: "Digital Book Supply",
            lines: [{ productName: "oranges", quantity: 2, unitCode: "EA", unitPrice: null }],
          }),
        },
      });
    });

    expect(screen.getByRole("alert")).toHaveTextContent(
      /complete the required fields before creating the draft order: sellerEmail/i,
    );
  });

  it("pushes manual draft edits back through the websocket", () => {
    render(<VoiceOrderDemo />);
    const socket = openSocket();

    act(() => {
      socket.emitMessage({ type: "session.ready", payload: draftStatePatch() });
    });

    fireEvent.change(screen.getByLabelText(/^Buyer name$/i), { target: { value: "Acme Books" } });

    expect(JSON.parse(socket.sentMessages.at(-1) ?? "{}")).toEqual({
      type: "draft.patch",
      payload: {
        draft: {
          buyerEmail: null,
          buyerName: "Acme Books",
          sellerEmail: null,
          sellerName: null,
          currency: null,
          issueDate: null,
          notes: null,
          delivery: null,
          lines: [],
        },
      },
    });
  });

  it("loads an editable order, seeds the websocket draft, and saves updates through REST", async () => {
    setStoredSession({
      partyId: "buyer-party",
      partyName: "Acme Books",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          orderId: "ord_edit123",
          status: "DRAFT",
          createdAt: "2026-03-07T00:00:00Z",
          updatedAt: "2026-03-08T00:00:00Z",
          payload: {
            buyerEmail: "buyer@example.com",
            buyerName: "Acme Books",
            sellerEmail: "seller@example.com",
            sellerName: "Digital Book Supply",
            currency: "AUD",
            issueDate: "2026-03-07",
            notes: "Leave at loading dock",
            delivery: {
              street: "123 Test St",
              city: "Sydney",
              state: "NSW",
              postcode: "2000",
              country: "AU",
              requestedDate: "2026-03-10",
            },
            lines: [
              {
                productName: "Oranges",
                quantity: 2,
                unitCode: "EA",
                unitPrice: "12.50",
              },
            ],
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          orderId: "ord_edit123",
          status: "DRAFT",
          updatedAt: "2026-03-09T00:00:00Z",
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        text: async () => "<Order />",
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<VoiceOrderDemo orderId="ord_edit123" />);
    const socket = openSocket();

    act(() => {
      socket.emitMessage({
        type: "session.ready",
        payload: draftStatePatch(),
      });
    });

    await waitFor(() => {
      expect(screen.getByDisplayValue("buyer@example.com")).toBeInTheDocument();
    });

    expect(socket.sentMessages.some(message => message.includes('"type":"draft.patch"'))).toBe(true);

    fireEvent.change(screen.getByLabelText(/^Buyer name$/i), {
      target: { value: "Updated Buyer" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save draft/i }));

    await waitFor(() => {
      expect(screen.getByText("2026-03-09T00:00:00Z")).toBeInTheDocument();
      expect(screen.getByDisplayValue("<Order />")).toBeInTheDocument();
    });

    const updateRequest = fetchMock.mock.calls[1];
    expect(updateRequest?.[0]).toBe("http://localhost:8000/v1/order/ord_edit123");
    expect(updateRequest?.[1]).toMatchObject({
      method: "PUT",
      headers: {
        Authorization: "Bearer super-secure-password",
        "Content-Type": "application/json",
        "X-Party-Email": "buyer@example.com",
      },
    });
    expect(JSON.parse(String(updateRequest?.[1]?.body))).toMatchObject({
      buyerEmail: "buyer@example.com",
      sellerEmail: "seller@example.com",
      buyerName: "Updated Buyer",
    });
  });

  it("deletes a draft order from edit mode and returns to the dashboard", async () => {
    setStoredSession({
      partyId: "buyer-party",
      partyName: "Acme Books",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          orderId: "ord_delete123",
          status: "DRAFT",
          createdAt: "2026-03-07T00:00:00Z",
          updatedAt: "2026-03-08T00:00:00Z",
          payload: {
            buyerEmail: "buyer@example.com",
            buyerName: "Acme Books",
            sellerEmail: "seller@example.com",
            sellerName: "Digital Book Supply",
            currency: "AUD",
            issueDate: "2026-03-07",
            notes: null,
            delivery: null,
            lines: [
              {
                productName: "Oranges",
                quantity: 2,
                unitCode: "EA",
                unitPrice: "12.50",
              },
            ],
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
      });
    vi.stubGlobal("fetch", fetchMock);
    window.history.replaceState({}, "", "/orders/ord_delete123/edit");

    render(<VoiceOrderDemo orderId="ord_delete123" />);
    const socket = openSocket();

    act(() => {
      socket.emitMessage({
        type: "session.ready",
        payload: draftStatePatch(),
      });
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /delete order/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /delete order/i }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent(/order id: ord_delete123/i);

    fireEvent.click(within(dialog).getByRole("button", { name: /^delete order$/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenNthCalledWith(
        2,
        "http://localhost:8000/v1/order/ord_delete123",
        {
          method: "DELETE",
          headers: {
            Authorization: "Bearer super-secure-password",
            "X-Party-Email": "buyer@example.com",
          },
        },
      );
      expect(window.location.pathname).toBe("/orders");
      expect(window.location.search).toBe("?deleted=ord_delete123");
    });
  });

  it("shows a locked state for non-draft orders in edit mode", async () => {
    setStoredSession({
      partyId: "buyer-party",
      partyName: "Acme Books",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });

    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            orderId: "ord_locked123",
            status: "SUBMITTED",
            createdAt: "2026-03-07T00:00:00Z",
            updatedAt: "2026-03-08T00:00:00Z",
            payload: {
              buyerEmail: "buyer@example.com",
              buyerName: "Acme Books",
              sellerEmail: "seller@example.com",
              sellerName: "Digital Book Supply",
              currency: "AUD",
              issueDate: "2026-03-07",
              notes: "Leave at loading dock",
              delivery: null,
              lines: [
                {
                  productName: "Oranges",
                  quantity: 2,
                  unitCode: "EA",
                  unitPrice: "12.50",
                },
              ],
            },
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          text: async () => "<LockedOrder />",
        }),
    );

    render(<VoiceOrderDemo orderId="ord_locked123" />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /order locked/i })).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: /update order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /delete order/i })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /order details/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /order xml/i })).toBeInTheDocument();
    expect(screen.getByDisplayValue("buyer@example.com")).toBeInTheDocument();
    expect(screen.getByDisplayValue("<LockedOrder />")).toBeInTheDocument();
  });
});
