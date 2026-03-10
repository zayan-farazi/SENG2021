import { useEffect, useRef, useState } from "react";
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
  const [diagnostics, setDiagnostics] = useState<DiagnosticEntry[]>([
    { level: "info", text: "Awaiting websocket connection." },
  ]);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const socketSequenceRef = useRef(0);
  const websocketUrl = getBackendWebSocketUrl();
  const backendHttpUrl = getBackendHttpUrl();

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
    sendSocketEvent("session.commit");
  };

  const resetDraft = () => {
    setLastOrder(null);
    sendSocketEvent("session.reset");
  };

  return (
    <main className="voice-app">
      <section className="hero">
        <div>
          <p className="eyebrow">DigitalBook voice order draft</p>
          <h1>Speak the order. Watch the draft settle in real time.</h1>
          <p className="lede">
            Browser transcription streams finalized phrases to the backend websocket, which keeps the
            draft authoritative until you confirm and create the order.
          </p>
        </div>
        <div className="status-card">
          <span className={`status-pill status-${connectionStatus}`}>{connectionStatus}</span>
          <p>{connectionMessage}</p>
          <p className="backend-label">Backend: {backendHttpUrl}</p>
        </div>
      </section>

      <section className="control-bar">
        <button
          type="button"
          className="primary-button"
          onClick={startListening}
          disabled={!speechSupported || listening || connectionStatus !== "connected"}
        >
          Start microphone
        </button>
        <button type="button" className="secondary-button" onClick={stopListening} disabled={!listening}>
          Stop microphone
        </button>
        <button
          type="button"
          className="primary-button"
          onClick={commitDraft}
          disabled={!isDraftReadyForCommit(draftState.draft) || connectionStatus !== "connected"}
        >
          Confirm order
        </button>
        <button type="button" className="secondary-button" onClick={resetDraft}>
          Reset draft
        </button>
      </section>

      {!speechSupported ? (
        <section className="banner warning-banner" role="status">
          This browser does not expose the Web Speech API. You can still edit the draft manually, but
          microphone controls are disabled.
        </section>
      ) : null}

      {errorMessage ? (
        <section className="banner error-banner" role="alert">
          {errorMessage}
        </section>
      ) : null}

      <section className="panel-grid">
        <article className="panel transcript-panel">
          <header className="panel-header">
            <h2>Live transcript</h2>
            <span className={listening ? "recording-live" : "recording-idle"}>
              {listening ? "Listening" : "Idle"}
            </span>
          </header>
          <div className="transcript-current">
            <p className="subtle-label">Current partial</p>
            <p>{draftState.currentPartial || "Waiting for speech…"}</p>
          </div>
          <div className="transcript-history">
            <p className="subtle-label">Finalized transcript history</p>
            {draftState.transcriptLog.length === 0 ? (
              <p className="empty-copy">Finalized phrases will appear here.</p>
            ) : (
              <ul>
                {draftState.transcriptLog.map((entry, index) => (
                  <li key={`${entry.kind}-${index}`}>{entry.text}</li>
                ))}
              </ul>
            )}
          </div>
        </article>

        <article className="panel insights-panel">
          <header className="panel-header">
            <h2>Diagnostics</h2>
            <span className="subtle-label">Websocket and speech runtime events</span>
          </header>
          <div className="diagnostics-list" aria-label="Diagnostics log">
            {diagnostics.map((entry, index) => (
              <p key={`${entry.level}-${index}`} className={`diagnostic-entry diagnostic-${entry.level}`}>
                {entry.text}
              </p>
            ))}
          </div>
        </article>

        <article className="panel draft-panel">
          <header className="panel-header">
            <h2>Draft form</h2>
            <span className="subtle-label">Manual edits sync through the websocket too</span>
          </header>
          <div className="form-grid">
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
            <label className="full-width">
              Notes
              <textarea
                aria-label="Notes"
                value={draftState.draft.notes ?? ""}
                onChange={event => updateDraftField("notes", nullableText(event.target.value))}
              />
            </label>
          </div>

          <div className="subsection">
            <div className="subsection-header">
              <h3>Delivery</h3>
            </div>
            <div className="form-grid">
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
                  onChange={event => updateDeliveryField("requestedDate", nullableText(event.target.value))}
                />
              </label>
            </div>
          </div>

          <div className="subsection">
            <div className="subsection-header">
              <h3>Line items</h3>
              <button type="button" className="secondary-button compact-button" onClick={addLineItem}>
                Add line item
              </button>
            </div>
            {draftState.draft.lines.length === 0 ? (
              <p className="empty-copy">Voice commands like “I want 2 oranges” will populate this list.</p>
            ) : (
              <div className="line-items">
                {draftState.draft.lines.map((line, index) => (
                  <div className="line-item-card" key={`line-${index}`}>
                    <label>
                      Product
                      <input
                        aria-label={`Line ${index + 1} product`}
                        value={line.productName ?? ""}
                        onChange={event =>
                          updateLineItem(index, { productName: nullableText(event.target.value) })
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
                          updateLineItem(index, { quantity: nullableInteger(event.target.value) })
                        }
                      />
                    </label>
                    <label>
                      Unit code
                      <input
                        aria-label={`Line ${index + 1} unit code`}
                        value={line.unitCode ?? ""}
                        onChange={event => updateLineItem(index, { unitCode: nullableCode(event.target.value) })}
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
                          updateLineItem(index, { unitPrice: nullableDecimal(event.target.value) })
                        }
                      />
                    </label>
                    <button
                      type="button"
                      className="secondary-button compact-button"
                      onClick={() => removeLineItem(index)}
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </article>

        <article className="panel insights-panel">
          <header className="panel-header">
            <h2>Warnings and unresolved</h2>
            <span className="subtle-label">Unsafe or unsupported phrases land here</span>
          </header>
          <div className="annotation-columns">
            <section>
              <h3>Warnings</h3>
              {draftState.warnings.length === 0 ? (
                <p className="empty-copy">No warnings yet.</p>
              ) : (
                <ul>
                  {draftState.warnings.map((warning, index) => (
                    <li key={`warning-${index}`}>
                      <strong>{warning.message}</strong>
                      <span>{warning.transcript}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section>
              <h3>Unresolved phrases</h3>
              {draftState.unresolved.length === 0 ? (
                <p className="empty-copy">The parser has understood everything so far.</p>
              ) : (
                <ul>
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

        <article className="panel result-panel">
          <header className="panel-header">
            <h2>Created order</h2>
            <span className="subtle-label">The existing REST order creation response lands here</span>
          </header>
          {lastOrder ? (
            <div className="result-grid">
              <p>
                <span className="subtle-label">Order ID</span>
                {lastOrder.orderId}
              </p>
              <p>
                <span className="subtle-label">Status</span>
                {lastOrder.status}
              </p>
              <p>
                <span className="subtle-label">Created</span>
                {lastOrder.createdAt}
              </p>
              <label className="full-width">
                UBL XML
                <textarea readOnly value={lastOrder.ublXml} />
              </label>
            </div>
          ) : (
            <p className="empty-copy">Confirm the draft to create an order.</p>
          )}
        </article>
      </section>
    </main>
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
