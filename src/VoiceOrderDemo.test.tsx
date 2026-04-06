import { act, StrictMode } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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

  it("keeps confirm disabled until the draft is valid", () => {
    render(<VoiceOrderDemo />);
    const socket = openSocket();
    const confirm = screen.getByRole("button", { name: /confirm order/i });

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
            buyerName: "Acme Books",
            sellerName: "Digital Book Supply",
            lines: [{ productName: "oranges", quantity: 2, unitCode: "EA", unitPrice: null }],
          }),
        },
      });
    });

    expect(confirm).toBeEnabled();
  });

  it("sends websocket commit requests and renders created order details", () => {
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
          buyerName: "Acme Books",
          sellerName: "Digital Book Supply",
          lines: [{ productName: "oranges", quantity: 2, unitCode: "EA", unitPrice: null }],
        }),
      });
    });

    fireEvent.click(screen.getByRole("button", { name: /confirm order/i }));

    expect(JSON.parse(socket.sentMessages.at(-1) ?? "{}")).toEqual({
      type: "session.commit",
      payload: {
        contactEmail: "buyer@example.com",
        credential: "super-secure-password",
      },
    });

    act(() => {
      socket.emitMessage({
        type: "order.created",
        payload: {
          state: draftStatePatch({
            buyerName: "Acme Books",
            sellerName: "Digital Book Supply",
            lines: [{ productName: "oranges", quantity: 2, unitCode: "EA", unitPrice: null }],
          }),
          order: {
            orderId: "ord_demo1234567890",
            status: "DRAFT",
            createdAt: "2026-03-07T00:00:00Z",
            ublXml: "<Order />",
            warnings: [],
          },
        },
      });
    });

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
          buyerName: "Acme Books",
          sellerName: "Digital Book Supply",
          lines: [{ productName: "oranges", quantity: 2, unitCode: "EA", unitPrice: null }],
        }),
      });
    });

    fireEvent.click(screen.getByRole("button", { name: /confirm order/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      /log in or register a party first/i,
    );
    expect(socket.sentMessages.some(message => message.includes("session.commit"))).toBe(false);
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
});
