import { useEffect, useRef, useState } from "react";
import { FileText, Menu, X } from "lucide-react";
import {
  emptyDelivery,
  emptyDraft,
  emptyDraftState,
  emptyLineItem,
  getBackendHttpUrl,
  getBackendWebSocketUrl,
  isDraftReadyForCommit,
  normalizeDraftState,
  type DraftLineItem,
  type DraftState,
  type OrderDraft,
  type OrderResponse,
} from "./voiceOrder";
import { AppLink } from "./components/AppLink";
import "./create-order.css";
import { getStoredSession } from "./session";

type ServerEnvelope = {
  type: string;
  payload: any;
};

type BrowserSpeechRecognition = SpeechRecognition;
type DiagnosticLevel = "info" | "warning" | "error";
type DiagnosticEntry = {
  level: DiagnosticLevel;
  text: string;
};

export function VoiceOrderDemo() {
  const [draftState, setDraftState] = useState<DraftState>(emptyDraftState);
  const [connectionStatus, setConnectionStatus] = useState("connecting");
  const [connectionMessage, setConnectionMessage] = useState("Connecting to backend draft session...");
  const [listening, setListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(true);
  const [lastOrder, setLastOrder] = useState<OrderResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [diagnostics, setDiagnostics] = useState<DiagnosticEntry[]>([
    { level: "info", text: "Awaiting websocket connection." },
  ]);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const socketSequenceRef = useRef(0);
  const websocketUrl = getBackendWebSocketUrl();
  const backendHttpUrl = getBackendHttpUrl();
  const storedSession = getStoredSession();

  const pushDiagnostic = (level: DiagnosticLevel, text: string) => {
    setDiagnostics(current => [...current.slice(-7), { level, text }]);
  };

  const sendSocketEvent = (type: string, payload: Record<string, unknown> = {}) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setErrorMessage("The backend draft websocket is not connected.");
      pushDiagnostic("warning", `Skipped ${type}: websocket is not open.`);
      return;
    }

    socket.send(JSON.stringify({ type, payload }));
    pushDiagnostic("info", `Sent ${type}.`);
  };

  const applyServerState = (state: DraftState) => {
    setDraftState(normalizeDraftState(state));
    setConnectionStatus(state.connectionStatus || "connected");
  };

  useEffect(() => {
    const socket = new WebSocket(websocketUrl);
    const socketId = socketSequenceRef.current + 1;
    socketSequenceRef.current = socketId;
    socketRef.current = socket;
    pushDiagnostic("info", `Socket ${socketId} connecting to ${websocketUrl}.`);

    const isCurrentSocket = () => socketRef.current === socket;

    const handleOpen = () => {
      if (!isCurrentSocket()) {
        return;
      }
      setConnectionStatus("connected");
      setConnectionMessage("Draft session connected.");
      setErrorMessage(null);
      pushDiagnostic("info", `Socket ${socketId} opened.`);
    };
    const handleClose = () => {
      if (!isCurrentSocket()) {
        return;
      }
      setConnectionStatus("disconnected");
      setListening(false);
      setConnectionMessage("Draft session disconnected.");
      pushDiagnostic("warning", `Socket ${socketId} closed.`);
    };
    const handleError = () => {
      if (!isCurrentSocket()) {
        return;
      }
      setErrorMessage("The backend draft websocket encountered an error.");
      pushDiagnostic("error", `Socket ${socketId} encountered an error.`);
    };
    const handleMessage = (event: MessageEvent<string>) => {
      if (!isCurrentSocket()) {
        return;
      }
      const envelope = JSON.parse(event.data) as ServerEnvelope;
      switch (envelope.type) {
        case "session.ready":
          applyServerState(envelope.payload as DraftState);
          setConnectionMessage("Draft session connected.");
          pushDiagnostic("info", "Received session.ready.");
          return;
        case "transcript.echo":
          if (envelope.payload.kind === "partial") {
            setDraftState(current => ({ ...current, currentPartial: envelope.payload.text }));
          }
          pushDiagnostic("info", `Received transcript echo (${envelope.payload.kind}).`);
          return;
        case "draft.updated":
          applyServerState(envelope.payload.state as DraftState);
          setConnectionMessage(
            envelope.payload.appliedChanges.length > 0
              ? envelope.payload.appliedChanges.join(" ")
              : "Draft synchronized.",
          );
          setErrorMessage(null);
          pushDiagnostic("info", "Received draft.updated.");
          return;
        case "commit.blocked":
          applyServerState(envelope.payload.state as DraftState);
          setConnectionMessage("The draft is missing required fields.");
          pushDiagnostic("warning", "Commit blocked by backend validation.");
          return;
        case "order.created":
          applyServerState(envelope.payload.state as DraftState);
          setLastOrder(envelope.payload.order as OrderResponse);
          setConnectionMessage("Order created successfully.");
          setErrorMessage(null);
          pushDiagnostic("info", "Received order.created.");
          return;
        case "error":
          setErrorMessage(envelope.payload.message as string);
          pushDiagnostic("error", `Backend error: ${envelope.payload.message as string}`);
          return;
        default:
          setErrorMessage(`Unknown backend event: ${envelope.type}`);
          pushDiagnostic("error", `Unknown backend event: ${envelope.type}`);
      }
    };

    socket.addEventListener("open", handleOpen);
    socket.addEventListener("close", handleClose);
    socket.addEventListener("error", handleError);
    socket.addEventListener("message", handleMessage);

    return () => {
      socket.removeEventListener("open", handleOpen);
      socket.removeEventListener("close", handleClose);
      socket.removeEventListener("error", handleError);
      socket.removeEventListener("message", handleMessage);

      if (socketRef.current === socket) {
        socketRef.current = null;
      }

      if (socket.readyState === WebSocket.CONNECTING) {
        socket.addEventListener(
          "open",
          () => {
            if (socket.readyState === WebSocket.OPEN) {
              socket.close();
            }
          },
          { once: true },
        );
        return;
      }

      if (socket.readyState === WebSocket.OPEN) {
        socket.close();
      }
    };
  }, [websocketUrl]);

  useEffect(() => {
    const SpeechRecognitionCtor = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) {
      setSpeechSupported(false);
      return;
    }

    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-AU";
    recognition.onstart = () => {
      pushDiagnostic("info", "Speech recognition started.");
    };

    recognition.onresult = event => {
      let interimTranscript = "";

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        const transcript = result[0].transcript.trim();

        if (result.isFinal) {
          sendSocketEvent("transcript.final", { text: transcript });
        } else {
          interimTranscript = transcript;
        }
      }

      if (interimTranscript) {
        sendSocketEvent("transcript.partial", { text: interimTranscript });
      }
    };
    recognition.onerror = event => {
      const details = event.message ? ` (${event.message})` : "";
      const browserHint =
        event.error === "network"
          ? " Browser speech recognition could not reach its speech service. This is usually a browser/network or permission issue rather than a backend websocket issue."
          : "";
      setErrorMessage(`Speech recognition error: ${event.error}${details}.${browserHint}`);
      pushDiagnostic("error", `Speech recognition error: ${event.error}${details}`);
      setListening(false);
    };
    recognition.onend = () => {
      setListening(false);
      pushDiagnostic("info", "Speech recognition ended.");
    };
    recognitionRef.current = recognition;

    return () => {
      recognition.stop();
      recognitionRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (
      connectionStatus !== "connected" ||
      !storedSession?.contactEmail ||
      draftState.draft.buyerEmail ||
      draftState.draft.sellerEmail
    ) {
      return;
    }

    patchDraft({
      ...draftState.draft,
      buyerEmail: storedSession.contactEmail,
    });
  }, [
    connectionStatus,
    draftState.draft,
    draftState.draft.buyerEmail,
    draftState.draft.sellerEmail,
    storedSession?.contactEmail,
  ]);

  const patchDraft = (nextDraft: OrderDraft) => {
    setDraftState(current => ({ ...current, draft: nextDraft }));
    sendSocketEvent("draft.patch", { draft: nextDraft });
  };

  const updateDraftField = (field: keyof OrderDraft, value: string | null) => {
    patchDraft({ ...draftState.draft, [field]: value });
  };

  const updateDeliveryField = (field: keyof NonNullable<OrderDraft["delivery"]>, value: string | null) => {
    const delivery = { ...(draftState.draft.delivery ?? emptyDelivery()), [field]: value };
    patchDraft({ ...draftState.draft, delivery });
  };

  const updateLineItem = (index: number, patch: Partial<DraftLineItem>) => {
    const lines = draftState.draft.lines.map((line, lineIndex) =>
      lineIndex === index ? { ...line, ...patch } : line,
    );
    patchDraft({ ...draftState.draft, lines });
  };

  const addLineItem = () => {
    patchDraft({ ...draftState.draft, lines: [...draftState.draft.lines, emptyLineItem()] });
  };

  const removeLineItem = (index: number) => {
    patchDraft({
      ...draftState.draft,
      lines: draftState.draft.lines.filter((_, lineIndex) => lineIndex !== index),
    });
  };

  const startListening = () => {
    if (!recognitionRef.current || connectionStatus !== "connected") {
      pushDiagnostic("warning", "Microphone start blocked until the websocket is connected.");
      return;
    }

    setErrorMessage(null);
    pushDiagnostic("info", "Microphone start requested.");
    recognitionRef.current.start();
    setListening(true);
  };

  const stopListening = () => {
    recognitionRef.current?.stop();
    setListening(false);
    pushDiagnostic("info", "Microphone stop requested.");
  };

  const commitDraft = () => {
    if (!storedSession?.appKey) {
      const message = "Register a party before confirming an order.";
      setErrorMessage(message);
      pushDiagnostic("warning", "Commit blocked until an app key is stored locally.");
      return;
    }

    sendSocketEvent("session.commit", { appKey: storedSession.appKey });
  };

  const resetDraft = () => {
    setLastOrder(null);
    sendSocketEvent("session.reset");
  };

  const closeMenu = () => {
    setMobileMenuOpen(false);
  };

  return (
    <div className="landing-root create-page-root">
      <div className="landing-container">
        <section className="landing-stage create-page-stage">
          <header className="landing-topbar">
            <div className="landing-topbar-inner">
              <AppLink href="/" className="landing-logo" onClick={closeMenu}>
                <span className="landing-logo-mark" aria-hidden="true">
                  <FileText size={16} strokeWidth={2.1} />
                </span>
                <span className="landing-logo-text">LockedOut</span>
              </AppLink>

              <div className="landing-toolbar">
                <AppLink href="/register" className="landing-button landing-button-secondary">
                  Register
                </AppLink>
                <AppLink href="/orders" className="landing-button landing-button-secondary">
                  Orders
                </AppLink>
                <AppLink href="/orders/create" className="landing-button landing-button-primary">
                  Create order
                </AppLink>
              </div>

              <button
                type="button"
                className="landing-menu-button"
                onClick={() => setMobileMenuOpen(open => !open)}
                aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
                aria-expanded={mobileMenuOpen}
              >
                {mobileMenuOpen ? <X size={18} /> : <Menu size={18} />}
              </button>
            </div>

            {mobileMenuOpen ? (
              <div className="landing-mobile-nav-wrap">
                <nav className="landing-mobile-nav" aria-label="Mobile">
                  <div className="landing-mobile-actions">
                    <AppLink
                      href="/register"
                      className="landing-button landing-button-secondary"
                      onClick={closeMenu}
                    >
                      Register
                    </AppLink>
                    <AppLink
                      href="/orders"
                      className="landing-button landing-button-secondary"
                      onClick={closeMenu}
                    >
                      Orders
                    </AppLink>
                    <AppLink
                      href="/orders/create"
                      className="landing-button landing-button-primary"
                      onClick={closeMenu}
                    >
                      Create order
                    </AppLink>
                  </div>
                </nav>
              </div>
            ) : null}
          </header>

          <main className="create-page-main">
            <section className="create-page-intro" aria-labelledby="create-page-title">
              <div className="create-page-intro-copy">
                <h1 id="create-page-title">Speak the order. Watch the draft settle in real time.</h1>
                <p>
                  Use browser speech recognition or manual edits to build the order draft, keep it in
                  sync with the websocket session, and confirm the final order once the required
                  fields are complete.
                </p>
              </div>
              <div className="create-page-runtime">
                <div className="create-page-runtime-state">
                  <span className={`create-page-state-dot create-page-state-${connectionStatus}`} />
                  <span className="create-page-runtime-label">{connectionStatus}</span>
                </div>
                <p>{connectionMessage}</p>
                <p className="create-page-backend">Backend: {backendHttpUrl}</p>
                {storedSession ? (
                  <p className="create-page-session-note">
                    Registered as {storedSession.partyName} ({storedSession.contactEmail})
                  </p>
                ) : null}
              </div>
            </section>

            <section className="create-page-action-bar" aria-label="Draft controls">
              <button
                type="button"
                className="landing-button landing-button-primary"
                onClick={startListening}
                disabled={!speechSupported || listening || connectionStatus !== "connected"}
              >
                Start microphone
              </button>
              <button
                type="button"
                className="landing-button landing-button-secondary"
                onClick={stopListening}
                disabled={!listening}
              >
                Stop microphone
              </button>
              <button
                type="button"
                className="landing-button landing-button-primary"
                onClick={commitDraft}
                disabled={!isDraftReadyForCommit(draftState.draft) || connectionStatus !== "connected"}
              >
                Confirm order
              </button>
              <button
                type="button"
                className="landing-button landing-button-secondary"
                onClick={resetDraft}
              >
                Reset draft
              </button>
            </section>

            {!speechSupported ? (
              <section className="create-page-banner create-page-banner-warning" role="status">
                This browser does not expose the Web Speech API. You can still edit the draft
                manually, but microphone controls are disabled.
              </section>
            ) : null}

            {!storedSession ? (
              <section className="create-page-banner create-page-banner-warning" role="status">
                Register a party first so the frontend can use the saved app key and contact email
                for protected order creation.
              </section>
            ) : null}

            {errorMessage ? (
              <section className="create-page-banner create-page-banner-error" role="alert">
                {errorMessage}
              </section>
            ) : null}

            <section className="create-page-workspace">
              <div className="create-page-column">
                <article className="create-page-panel">
                  <header className="create-page-panel-header">
                    <div>
                      <h2>Live transcript</h2>
                      <p>Speech updates appear here before they settle into the draft.</p>
                    </div>
                    <span className={listening ? "create-page-recording-live" : "create-page-recording-idle"}>
                      {listening ? "Listening" : "Idle"}
                    </span>
                  </header>
                  <div className="create-page-panel-stack">
                    <section className="create-page-block">
                      <p className="create-page-label">Current partial</p>
                      <p className="create-page-current-text">
                        {draftState.currentPartial || "Waiting for speech..."}
                      </p>
                    </section>
                    <section className="create-page-block">
                      <p className="create-page-label">Finalized transcript history</p>
                      {draftState.transcriptLog.length === 0 ? (
                        <p className="create-page-empty-copy">Finalized phrases will appear here.</p>
                      ) : (
                        <ul className="create-page-list">
                          {draftState.transcriptLog.map((entry, index) => (
                            <li key={`${entry.kind}-${index}`}>{entry.text}</li>
                          ))}
                        </ul>
                      )}
                    </section>
                  </div>
                </article>

                <article className="create-page-panel">
                  <header className="create-page-panel-header">
                    <div>
                      <h2>Diagnostics</h2>
                      <p>Websocket, browser speech, and session events appear in sequence.</p>
                    </div>
                  </header>
                  <div className="create-page-diagnostics-list" aria-label="Diagnostics log">
                    {diagnostics.map((entry, index) => (
                      <p
                        key={`${entry.level}-${index}`}
                        className={`create-page-diagnostic create-page-diagnostic-${entry.level}`}
                      >
                        {entry.text}
                      </p>
                    ))}
                  </div>
                </article>
              </div>

              <div className="create-page-column">
                <article className="create-page-panel">
                  <header className="create-page-panel-header">
                    <div>
                      <h2>Draft form</h2>
                      <p>Manual edits still sync through the websocket session while you type.</p>
                    </div>
                  </header>
                  <div className="create-page-form-grid">
                    <label>
                      Buyer name
                      <input
                        aria-label="Buyer name"
                        value={draftState.draft.buyerName ?? ""}
                        onChange={event => updateDraftField("buyerName", nullableText(event.target.value))}
                      />
                    </label>
                    <label>
                      Seller name
                      <input
                        aria-label="Seller name"
                        value={draftState.draft.sellerName ?? ""}
                        onChange={event => updateDraftField("sellerName", nullableText(event.target.value))}
                      />
                    </label>
                    <label>
                      Currency
                      <input
                        aria-label="Currency"
                        value={draftState.draft.currency ?? ""}
                        maxLength={3}
                        onChange={event => updateDraftField("currency", nullableCode(event.target.value))}
                      />
                    </label>
                    <label>
                      Issue date
                      <input
                        aria-label="Issue date"
                        type="date"
                        value={draftState.draft.issueDate ?? ""}
                        onChange={event => updateDraftField("issueDate", nullableText(event.target.value))}
                      />
                    </label>
                    <label className="create-page-full-width">
                      Notes
                      <textarea
                        aria-label="Notes"
                        value={draftState.draft.notes ?? ""}
                        onChange={event => updateDraftField("notes", nullableText(event.target.value))}
                      />
                    </label>
                  </div>

                  <section className="create-page-subsection">
                    <div className="create-page-subsection-header">
                      <h3>Delivery</h3>
                    </div>
                    <div className="create-page-form-grid">
                      <label>
                        Street
                        <input
                          aria-label="Delivery street"
                          value={draftState.draft.delivery?.street ?? ""}
                          onChange={event => updateDeliveryField("street", nullableText(event.target.value))}
                        />
                      </label>
                      <label>
                        City
                        <input
                          aria-label="Delivery city"
                          value={draftState.draft.delivery?.city ?? ""}
                          onChange={event => updateDeliveryField("city", nullableText(event.target.value))}
                        />
                      </label>
                      <label>
                        State
                        <input
                          aria-label="Delivery state"
                          value={draftState.draft.delivery?.state ?? ""}
                          onChange={event => updateDeliveryField("state", nullableText(event.target.value))}
                        />
                      </label>
                      <label>
                        Postcode
                        <input
                          aria-label="Delivery postcode"
                          value={draftState.draft.delivery?.postcode ?? ""}
                          onChange={event => updateDeliveryField("postcode", nullableText(event.target.value))}
                        />
                      </label>
                      <label>
                        Country
                        <input
                          aria-label="Delivery country"
                          value={draftState.draft.delivery?.country ?? ""}
                          onChange={event => updateDeliveryField("country", nullableText(event.target.value))}
                        />
                      </label>
                      <label>
                        Requested date
                        <input
                          aria-label="Requested delivery date"
                          type="date"
                          value={draftState.draft.delivery?.requestedDate ?? ""}
                          onChange={event =>
                            updateDeliveryField("requestedDate", nullableText(event.target.value))
                          }
                        />
                      </label>
                    </div>
                  </section>

                  <section className="create-page-subsection">
                    <div className="create-page-subsection-header">
                      <h3>Line items</h3>
                      <button
                        type="button"
                        className="landing-button landing-button-secondary create-page-compact-button"
                        onClick={addLineItem}
                      >
                        Add line item
                      </button>
                    </div>
                    {draftState.draft.lines.length === 0 ? (
                      <p className="create-page-empty-copy">
                        Voice commands like “I want 2 oranges” will populate this list.
                      </p>
                    ) : (
                      <div className="create-page-line-items">
                        {draftState.draft.lines.map((line, index) => (
                          <div className="create-page-line-item-card" key={`line-${index}`}>
                            <label>
                              Product
                              <input
                                aria-label={`Line ${index + 1} product`}
                                value={line.productName ?? ""}
                                onChange={event =>
                                  updateLineItem(index, {
                                    productName: nullableText(event.target.value),
                                  })
                                }
                              />
                            </label>
                            <label>
                              Quantity
                              <input
                                aria-label={`Line ${index + 1} quantity`}
                                type="number"
                                min="1"
                                value={line.quantity ?? ""}
                                onChange={event =>
                                  updateLineItem(index, {
                                    quantity: nullableInteger(event.target.value),
                                  })
                                }
                              />
                            </label>
                            <label>
                              Unit code
                              <input
                                aria-label={`Line ${index + 1} unit code`}
                                value={line.unitCode ?? ""}
                                onChange={event =>
                                  updateLineItem(index, {
                                    unitCode: nullableCode(event.target.value),
                                  })
                                }
                              />
                            </label>
                            <label>
                              Unit price
                              <input
                                aria-label={`Line ${index + 1} unit price`}
                                type="number"
                                min="0"
                                step="0.01"
                                value={line.unitPrice ?? ""}
                                onChange={event =>
                                  updateLineItem(index, {
                                    unitPrice: nullableDecimal(event.target.value),
                                  })
                                }
                              />
                            </label>
                            <button
                              type="button"
                              className="landing-button landing-button-secondary create-page-compact-button"
                              onClick={() => removeLineItem(index)}
                            >
                              Remove
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </section>
                </article>

                <article className="create-page-panel">
                  <header className="create-page-panel-header">
                    <div>
                      <h2>Created order</h2>
                      <p>The REST order creation response and persisted UBL XML land here.</p>
                    </div>
                  </header>
                  {lastOrder ? (
                    <div className="create-page-result-grid">
                      <p>
                        <span className="create-page-label">Order ID</span>
                        {lastOrder.orderId}
                      </p>
                      <p>
                        <span className="create-page-label">Status</span>
                        {lastOrder.status}
                      </p>
                      <p>
                        <span className="create-page-label">Created</span>
                        {lastOrder.createdAt}
                      </p>
                      <label className="create-page-full-width">
                        UBL XML
                        <textarea readOnly value={lastOrder.ublXml} />
                      </label>
                    </div>
                  ) : (
                    <p className="create-page-empty-copy">Confirm the draft to create an order.</p>
                  )}
                </article>
              </div>
            </section>

            <section className="create-page-annotations-panel">
              <article className="create-page-panel">
                <header className="create-page-panel-header">
                  <div>
                    <h2>Warnings and unresolved</h2>
                    <p>Unsafe, ambiguous, or unsupported phrases are grouped here.</p>
                  </div>
                </header>
                <div className="create-page-annotation-columns">
                  <section className="create-page-block">
                    <h3>Warnings</h3>
                    {draftState.warnings.length === 0 ? (
                      <p className="create-page-empty-copy">No warnings yet.</p>
                    ) : (
                      <ul className="create-page-list">
                        {draftState.warnings.map((warning, index) => (
                          <li key={`warning-${index}`}>
                            <strong>{warning.message}</strong>
                            <span>{warning.transcript}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </section>
                  <section className="create-page-block">
                    <h3>Unresolved phrases</h3>
                    {draftState.unresolved.length === 0 ? (
                      <p className="create-page-empty-copy">
                        The parser has understood everything so far.
                      </p>
                    ) : (
                      <ul className="create-page-list">
                        {draftState.unresolved.map((item, index) => (
                          <li key={`unresolved-${index}`}>
                            <strong>{item.message}</strong>
                            <span>{item.transcript}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </section>
                </div>
              </article>
            </section>
          </main>
        </section>
      </div>
    </div>
  );
}

function nullableText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function nullableCode(value: string): string | null {
  const trimmed = value.trim().toUpperCase();
  return trimmed ? trimmed : null;
}

function nullableInteger(value: string): number | null {
  if (!value.trim()) {
    return null;
  }

  return Number.parseInt(value, 10);
}

function nullableDecimal(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}
