import { useEffect, useRef, useState } from "react";
import { AppLink, navigate } from "./components/AppLink";
import { ConfirmDialog } from "./components/ConfirmDialog";
import { VoiceAssistantDock } from "./components/VoiceAssistantDock";
import {
  draftToOrderRequest,
  emptyDelivery,
  emptyDraft,
  emptyDraftState,
  emptyLineItem,
  getDraftMissingFields,
  getBackendHttpUrl,
  getBackendWebSocketUrl,
  isDraftReadyForCommit,
  normalizeDraftState,
  getDocumentsAssistantWebSocketUrl,
  type DraftLineItem,
  type DraftState,
  type OrderDraft,
  type OrderResponse,
} from "./voiceOrder";
import { AppHeader } from "./components/AppHeader";
import {
  createOrder,
  deleteInvoice,
  deleteOrder,
  fetchEditableOrder,
  fetchInvoice,
  fetchInvoicePdf,
  fetchInvoiceUblXml,
  fetchOrderDespatchXml,
  fetchOrderUblXml,
  generateOrderDespatch,
  generateOrderInvoice,
  type InvoiceRecord,
  type InvoiceUpdatePayload,
  transitionInvoiceStatus,
  updateExistingOrder,
  updateInvoice,
} from "./orderApi";
import "./create-order.css";
import { useStoredSession } from "./session";
import { parseLockedOrderVoiceCommand, type AssistantActionResult } from "./voiceAssistant";

type ServerEnvelope = {
  type: string;
  payload: any;
};

type CommitBlockedError = {
  loc?: Array<string | number>;
};

type BrowserSpeechRecognition = SpeechRecognition;
type DiagnosticLevel = "info" | "warning" | "error";
type DiagnosticEntry = {
  level: DiagnosticLevel;
  text: string;
};
type LockedOrderAssistantServerEnvelope = {
  type: string;
  payload?: {
    kind?: "partial" | "final";
    text?: string;
    command?: ReturnType<typeof parseLockedOrderVoiceCommand> | null;
    message?: string | null;
  };
};

type VoiceOrderDemoProps = {
  orderId?: string;
};
type LockedOrderAssistantCommand = NonNullable<ReturnType<typeof parseLockedOrderVoiceCommand>>;

type EditableOrderMeta = {
  orderId: string;
  status: string;
  createdAt: string;
  updatedAt: string;
};

type UpdateResultState = {
  orderId: string;
  status: string;
  updatedAt: string;
  ublXml: string | null;
};

type LockedOrderState = {
  orderId: string;
  status: string;
  createdAt: string;
  updatedAt: string;
  ublXml: string | null;
};

type DespatchState = {
  adviceId: string | null;
  xml: string | null;
};

type EditLoadState = "loading" | "ready" | "locked" | "error";
const MANUAL_DRAFT_SYNC_DEBOUNCE_MS = 250;
const INVOICE_MAPPING_STORAGE_KEY = "lockedout.order-invoices";

function normalizeEmail(value: string | null | undefined): string {
  return value?.trim().toLowerCase() ?? "";
}

function findNestedInvoiceString(
  value: unknown,
  keys: string[],
  seen = new Set<unknown>(),
): string | null {
  if (typeof value === "string" && value.trim()) {
    return null;
  }

  if (!value || typeof value !== "object") {
    return null;
  }

  if (seen.has(value)) {
    return null;
  }
  seen.add(value);

  if (Array.isArray(value)) {
    for (const item of value) {
      const nested = findNestedInvoiceString(item, keys, seen);
      if (nested) {
        return nested;
      }
    }
    return null;
  }

  const record = value as Record<string, unknown>;
  for (const key of keys) {
    const candidate = record[key];
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate.trim();
    }
  }

  for (const nestedValue of Object.values(record)) {
    const nested = findNestedInvoiceString(nestedValue, keys, seen);
    if (nested) {
      return nested;
    }
  }

  return null;
}

function firstNonEmptyInvoiceString(
  invoice: InvoiceRecord | null,
  keys: string[],
): string | null {
  if (!invoice) {
    return null;
  }

  for (const key of keys) {
    const value = invoice[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }

  return findNestedInvoiceString(invoice, keys);
}

function normalizeInvoiceRecord(invoice: InvoiceRecord | null): InvoiceRecord | null {
  if (!invoice) {
    return null;
  }

  const normalized: InvoiceRecord = { ...invoice };
  const invoiceId = firstNonEmptyInvoiceString(invoice, ["invoice_id", "invoiceId", "id"]);
  const status = firstNonEmptyInvoiceString(invoice, ["status", "invoice_status"]);
  const updatedAt = firstNonEmptyInvoiceString(invoice, ["updated_at", "updatedAt", "updated"]);
  const issueDate = firstNonEmptyInvoiceString(invoice, ["issue_date", "issueDate"]);
  const currency = firstNonEmptyInvoiceString(invoice, ["currency", "currency_code"]);
  const xml = firstNonEmptyInvoiceString(invoice, ["ubl_xml", "ublXml", "xml"]);

  if (invoiceId) {
    normalized.invoice_id = invoiceId;
    normalized.invoiceId = invoiceId;
  }
  if (status) {
    normalized.status = status;
  }
  if (updatedAt) {
    normalized.updated_at = updatedAt;
    normalized.updatedAt = updatedAt;
  }
  if (issueDate) {
    normalized.issue_date = issueDate;
    normalized.issueDate = issueDate;
  }
  if (currency) {
    normalized.currency = currency;
  }
  if (xml) {
    normalized.ubl_xml = xml;
    normalized.ublXml = xml;
    normalized.xml = xml;
  }

  return normalized;
}

function extractInvoiceId(invoice: InvoiceRecord | null): string | null {
  return firstNonEmptyInvoiceString(invoice, ["invoice_id", "invoiceId", "id"]);
}

function getStoredInvoiceId(orderId: string): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const raw = window.sessionStorage.getItem(INVOICE_MAPPING_STORAGE_KEY);
    if (!raw) {
      return null;
    }

    const mapping = JSON.parse(raw) as Record<string, unknown>;
    const candidate = mapping[orderId];
    return typeof candidate === "string" && candidate.trim() ? candidate : null;
  } catch {
    return null;
  }
}

function setStoredInvoiceId(orderId: string, invoiceId: string | null) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    const raw = window.sessionStorage.getItem(INVOICE_MAPPING_STORAGE_KEY);
    const mapping = raw ? (JSON.parse(raw) as Record<string, string>) : {};
    if (invoiceId) {
      mapping[orderId] = invoiceId;
    } else {
      delete mapping[orderId];
    }
    window.sessionStorage.setItem(INVOICE_MAPPING_STORAGE_KEY, JSON.stringify(mapping));
  } catch {
    // Ignore session storage failures and keep the document session in-memory only.
  }
}

export function VoiceOrderDemo({ orderId }: VoiceOrderDemoProps = {}) {
  const isEditMode = Boolean(orderId);
  const [draftState, setDraftState] = useState<DraftState>(emptyDraftState);
  const [connectionStatus, setConnectionStatus] = useState("connecting");
  const [connectionMessage, setConnectionMessage] = useState("Connecting to backend draft session...");
  const [listening, setListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(true);
  const [lastOrder, setLastOrder] = useState<OrderResponse | null>(null);
  const [updatedOrder, setUpdatedOrder] = useState<UpdateResultState | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [editLoadState, setEditLoadState] = useState<EditLoadState>(
    isEditMode ? "loading" : "ready",
  );
  const [editableOrderMeta, setEditableOrderMeta] = useState<EditableOrderMeta | null>(null);
  const [initialDraftSnapshot, setInitialDraftSnapshot] = useState<OrderDraft | null>(null);
  const [lockedOrder, setLockedOrder] = useState<LockedOrderState | null>(null);
  const [despatchState, setDespatchState] = useState<DespatchState>({ adviceId: null, xml: null });
  const [despatchBusy, setDespatchBusy] = useState<"generate" | "fetch" | null>(null);
  const [despatchError, setDespatchError] = useState<string | null>(null);
  const [documentClipboardMessage, setDocumentClipboardMessage] = useState<string | null>(null);
  const [invoiceId, setInvoiceId] = useState<string | null>(null);
  const [invoiceRecord, setInvoiceRecord] = useState<InvoiceRecord | null>(null);
  const [invoiceXml, setInvoiceXml] = useState<string | null>(null);
  const [invoiceBusy, setInvoiceBusy] = useState<
    "generate" | "fetch" | "xml" | "pdf" | "update" | "status" | "delete" | null
  >(null);
  const [invoiceError, setInvoiceError] = useState<string | null>(null);
  const [invoiceUpdateDraft, setInvoiceUpdateDraft] = useState("{}");
  const [invoiceStatusDraft, setInvoiceStatusDraft] = useState("sent");
  const [invoicePaymentDateDraft, setInvoicePaymentDateDraft] = useState("");
  const [documentsAssistantLiveTranscript, setDocumentsAssistantLiveTranscript] = useState<
    string | null
  >(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletePending, setDeletePending] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [diagnostics, setDiagnostics] = useState<DiagnosticEntry[]>([
    { level: "info", text: "Awaiting websocket connection." },
  ]);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const socketSequenceRef = useRef(0);
  const seededDraftOrderIdRef = useRef<string | null>(null);
  const pendingDraftSyncTimerRef = useRef<number | null>(null);
  const pendingDraftSyncRef = useRef<OrderDraft | null>(null);
  const documentsAssistantSocketRef = useRef<WebSocket | null>(null);
  const documentsAssistantResultResolverRef = useRef<
    ((result: AssistantActionResult) => void) | null
  >(null);
  const lockedOrderIdRef = useRef<string | null>(null);
  const hasDespatchRef = useRef(false);
  const hasInvoiceRef = useRef(false);
  const invoiceStatusRef = useRef<string | null>(null);
  const viewerIsSellerRef = useRef(false);
  const websocketUrl = getBackendWebSocketUrl();
  const documentsAssistantWebSocketUrl = getDocumentsAssistantWebSocketUrl();
  const backendHttpUrl = getBackendHttpUrl();
  const storedSession = useStoredSession();

  const pushDiagnostic = (level: DiagnosticLevel, text: string) => {
    setDiagnostics(current => [...current.slice(-7), { level, text }]);
  };

  const describeApiError = (
    error: unknown,
    prefix: string,
    fallbackMessage: string,
  ) => {
    if (!(error instanceof Error) || !error.message.startsWith(prefix)) {
      return fallbackMessage;
    }

    const remainder = error.message.slice(prefix.length);
    const firstSeparatorIndex = remainder.indexOf(":");
    const detail =
      firstSeparatorIndex === -1 ? "" : remainder.slice(firstSeparatorIndex + 1).trim();
    return detail || fallbackMessage;
  };

  const copyDocumentText = async (label: string, value: string) => {
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error("clipboard unavailable");
      }
      await navigator.clipboard.writeText(value);
      setDocumentClipboardMessage(`${label} copied.`);
      pushDiagnostic("info", `${label} copied to clipboard.`);
      window.setTimeout(() => {
        setDocumentClipboardMessage(current => (current === `${label} copied.` ? null : current));
      }, 2200);
    } catch {
      setDocumentClipboardMessage(`Unable to copy ${label.toLowerCase()}.`);
      pushDiagnostic("warning", `Copy failed for ${label}.`);
    }
  };

  const downloadDocumentBlob = (filename: string, blob: Blob) => {
    const objectUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    link.click();
    window.URL.revokeObjectURL(objectUrl);
  };

  const syncInvoiceRecord = (nextInvoice: InvoiceRecord | null, orderIdentifier: string | null) => {
    const normalizedInvoice = normalizeInvoiceRecord(nextInvoice);
    const nextInvoiceId = extractInvoiceId(normalizedInvoice);
    setInvoiceRecord(normalizedInvoice);
    setInvoiceId(nextInvoiceId);
    setInvoiceUpdateDraft(normalizedInvoice ? JSON.stringify(normalizedInvoice, null, 2) : "{}");
    setInvoiceStatusDraft(
      typeof normalizedInvoice?.status === "string" && normalizedInvoice.status.trim()
        ? normalizedInvoice.status
        : "sent",
    );
    setInvoicePaymentDateDraft("");
    const nextInvoiceXml = firstNonEmptyInvoiceString(normalizedInvoice, ["ubl_xml", "ublXml", "xml"]);
    if (nextInvoiceXml) {
      setInvoiceXml(nextInvoiceXml);
    }
    if (orderIdentifier) {
      setStoredInvoiceId(orderIdentifier, nextInvoiceId);
    }
  };

  const resolveInvoiceIdentifier = (): string | null => {
    const fromRecord = extractInvoiceId(invoiceRecord);
    if (invoiceId) {
      return invoiceId;
    }
    if (fromRecord) {
      return fromRecord;
    }
    if (lockedOrderId) {
      return getStoredInvoiceId(lockedOrderId);
    }
    return null;
  };

  const describeCommitBlocked = (errors: CommitBlockedError[] | undefined) => {
    if (!Array.isArray(errors) || errors.length === 0) {
      return "The draft is missing required fields.";
    }

    const fields = errors
      .map(error => {
        const first = error.loc?.[0];
        return typeof first === "string" ? first : null;
      })
      .filter((field): field is string => field !== null);

    if (fields.length === 0) {
      return "The draft is missing required fields.";
    }

    const uniqueFields = [...new Set(fields)];
    return `Complete the required fields before creating the draft order: ${uniqueFields.join(", ")}.`;
  };

  const formatRequiredFieldLabel = (label: string) => (
    <span className="create-page-required-label">
      {label}
      <span className="create-page-required-indicator" aria-hidden="true">
        *
      </span>
    </span>
  );

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

  const applyServerState = (state: DraftState, preserveLocalDraft = false) => {
    const normalizedState = normalizeDraftState(state);
    setDraftState(current =>
      preserveLocalDraft ? { ...normalizedState, draft: current.draft } : normalizedState,
    );
    setConnectionStatus(state.connectionStatus || "connected");
  };

  const clearPendingDraftSync = () => {
    if (pendingDraftSyncTimerRef.current !== null) {
      window.clearTimeout(pendingDraftSyncTimerRef.current);
      pendingDraftSyncTimerRef.current = null;
    }
  };

  const flushPendingDraftSync = () => {
    const nextDraft = pendingDraftSyncRef.current;
    clearPendingDraftSync();
    pendingDraftSyncRef.current = null;
    if (nextDraft) {
      sendSocketEvent("draft.patch", { draft: nextDraft });
    }
  };

  const queueDraftSync = (nextDraft: OrderDraft) => {
    pendingDraftSyncRef.current = nextDraft;
    clearPendingDraftSync();
    pendingDraftSyncTimerRef.current = window.setTimeout(() => {
      flushPendingDraftSync();
    }, MANUAL_DRAFT_SYNC_DEBOUNCE_MS);
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
          applyServerState(
            envelope.payload.state as DraftState,
            pendingDraftSyncTimerRef.current !== null,
          );
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
          setErrorMessage(describeCommitBlocked(envelope.payload.errors as CommitBlockedError[]));
          pushDiagnostic("warning", "Commit blocked by backend validation.");
          return;
        case "order.created":
          applyServerState(envelope.payload.state as DraftState);
          setLastOrder(envelope.payload.order as OrderResponse);
          setConnectionMessage("Draft order created successfully.");
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

      clearPendingDraftSync();
      pendingDraftSyncRef.current = null;
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
        if (!result) {
          continue;
        }
        const alternative = result?.[0];
        if (!alternative?.transcript) {
          continue;
        }
        const transcript = alternative.transcript.trim();

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
    if (!isEditMode || !orderId || !storedSession) {
      return;
    }

    let cancelled = false;
    setEditLoadState("loading");
    setErrorMessage(null);
    setLockedOrder(null);

    void fetchEditableOrder(storedSession, orderId)
      .then(async response => {
        if (cancelled) {
          return;
        }

        const normalizedDraft = normalizeDraftState({
          ...emptyDraftState(),
          draft: response.payload,
          connectionStatus: "connected",
        }).draft;

        setEditableOrderMeta({
          orderId: response.orderId,
          status: response.status,
          createdAt: response.createdAt,
          updatedAt: response.updatedAt,
        });
        setInitialDraftSnapshot(normalizedDraft);
        setDraftState(current => ({ ...current, draft: normalizedDraft }));
        setUpdatedOrder(null);
        seededDraftOrderIdRef.current = null;

        if (response.status !== "DRAFT") {
          const ublXml = await fetchOrderUblXml(storedSession, response.orderId).catch(() => null);
          if (cancelled) {
            return;
          }

          setLockedOrder({
            orderId: response.orderId,
            status: response.status,
            createdAt: response.createdAt,
            updatedAt: response.updatedAt,
            ublXml,
          });
          setEditLoadState("locked");
          setConnectionMessage("This order is locked and can no longer be updated.");
          pushDiagnostic("warning", `Loaded locked order ${response.orderId}.`);
          return;
        }

        setEditLoadState("ready");
        setConnectionMessage("Loaded persisted order draft.");
        pushDiagnostic("info", `Loaded order ${response.orderId} for editing.`);
      })
      .catch((error: Error) => {
        if (cancelled) {
          return;
        }

        setEditLoadState("error");
        if (error.message === "order-payload:404") {
          setErrorMessage("The order could not be found.");
        } else if (error.message === "order-payload:403") {
          setErrorMessage("You do not have access to this order.");
        } else {
          setErrorMessage("The order could not be loaded.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isEditMode, orderId, storedSession]);

  const lockedOrderId = lockedOrder?.orderId ?? editableOrderMeta?.orderId ?? orderId ?? null;
  const viewerEmail = normalizeEmail(storedSession?.contactEmail);
  const sellerEmail = normalizeEmail(draftState.draft.sellerEmail);
  const viewerIsSeller = Boolean(viewerEmail && sellerEmail && viewerEmail === sellerEmail);

  useEffect(() => {
    if (!isEditMode || editLoadState !== "locked" || !lockedOrderId) {
      setDespatchState({ adviceId: null, xml: null });
      setDespatchBusy(null);
      setDespatchError(null);
      setDocumentClipboardMessage(null);
      setInvoiceXml(null);
      setInvoiceBusy(null);
      setInvoiceError(null);
      syncInvoiceRecord(null, null);
      return;
    }

    setDespatchState({ adviceId: null, xml: null });
    setDespatchBusy(null);
    setDespatchError(null);
    setDocumentClipboardMessage(null);
    setInvoiceXml(null);
    setInvoiceBusy(null);
    setInvoiceError(null);

    const rememberedInvoiceId = getStoredInvoiceId(lockedOrderId);
    if (!rememberedInvoiceId || !storedSession) {
      syncInvoiceRecord(null, lockedOrderId);
      return;
    }

    let cancelled = false;
    setInvoiceBusy("fetch");

    void fetchInvoice(storedSession, rememberedInvoiceId)
      .then(invoice => {
        if (cancelled) {
          return;
        }
        syncInvoiceRecord(invoice, lockedOrderId);
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        syncInvoiceRecord(null, lockedOrderId);
      })
      .finally(() => {
        if (!cancelled) {
          setInvoiceBusy(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [editLoadState, isEditMode, lockedOrderId, storedSession]);

  useEffect(() => {
    if (
      isEditMode ||
      connectionStatus !== "connected" ||
      !storedSession?.contactEmail ||
      draftState.draft.buyerEmail ||
      draftState.draft.sellerEmail
    ) {
      return;
    }

    patchDraft(
      {
        ...draftState.draft,
        buyerEmail: storedSession.contactEmail,
      },
      "immediate",
    );
  }, [
    connectionStatus,
    draftState.draft,
    draftState.draft.buyerEmail,
    draftState.draft.sellerEmail,
    isEditMode,
    storedSession?.contactEmail,
  ]);

  useEffect(() => {
    if (
      !isEditMode ||
      !orderId ||
      editLoadState !== "ready" ||
      connectionStatus !== "connected" ||
      !initialDraftSnapshot ||
      seededDraftOrderIdRef.current === orderId
    ) {
      return;
    }

    patchDraft(initialDraftSnapshot, "immediate");
    seededDraftOrderIdRef.current = orderId;
    pushDiagnostic("info", "Seeded the websocket draft with the stored order.");
  }, [connectionStatus, editLoadState, initialDraftSnapshot, isEditMode, orderId]);

  const fetchExistingDespatch = async (): Promise<boolean> => {
    if (!storedSession || !lockedOrderId) {
      return false;
    }

    setDespatchBusy("fetch");
    setDespatchError(null);

    try {
      const xml = await fetchOrderDespatchXml(storedSession, lockedOrderId);
      setDespatchState(current => ({ ...current, xml }));
      pushDiagnostic("info", `Fetched despatch XML for ${lockedOrderId}.`);
      return true;
    } catch (error) {
      const message = describeApiError(
        error,
        "order-despatch:",
        "Unable to load the existing despatch advice.",
      );
      setDespatchError(message);
      pushDiagnostic("error", `Despatch fetch failed: ${message}`);
      return false;
    } finally {
      setDespatchBusy(null);
    }
  };

  const createDespatchDocument = async (): Promise<boolean> => {
    if (!storedSession || !lockedOrderId) {
      return false;
    }

    setDespatchBusy("generate");
    setDespatchError(null);

    try {
      const result = await generateOrderDespatch(storedSession, lockedOrderId);
      setDespatchState({
        adviceId: result.despatch.adviceId,
        xml: result.despatch.xml,
      });
      pushDiagnostic("info", `Generated despatch advice for ${lockedOrderId}.`);
      return true;
    } catch (error) {
      const message = describeApiError(
        error,
        "order-despatch-create:",
        "Unable to generate the despatch advice.",
      );
      setDespatchError(message);
      pushDiagnostic("error", `Despatch generation failed: ${message}`);
      return false;
    } finally {
      setDespatchBusy(null);
    }
  };

  const refreshInvoiceRecord = async (
    nextInvoiceId = resolveInvoiceIdentifier(),
  ): Promise<boolean> => {
    if (!storedSession || !lockedOrderId || !nextInvoiceId) {
      return false;
    }

    setInvoiceBusy("fetch");
    setInvoiceError(null);

    try {
      const invoice = await fetchInvoice(storedSession, nextInvoiceId);
      syncInvoiceRecord(invoice, lockedOrderId);
      pushDiagnostic("info", `Fetched invoice ${nextInvoiceId}.`);
      return true;
    } catch (error) {
      const message = describeApiError(
        error,
        "invoice-fetch:",
        "Unable to load the invoice details.",
      );
      setInvoiceError(message);
      pushDiagnostic("error", `Invoice fetch failed: ${message}`);
      return false;
    } finally {
      setInvoiceBusy(null);
    }
  };

  const createInvoiceDocument = async (): Promise<boolean> => {
    if (!storedSession || !lockedOrderId) {
      return false;
    }

    setInvoiceBusy("generate");
    setInvoiceError(null);

    try {
      const result = await generateOrderInvoice(storedSession, lockedOrderId);
      const normalizedInvoice = normalizeInvoiceRecord(result.invoice);
      const nextInvoiceId = extractInvoiceId(normalizedInvoice);
      syncInvoiceRecord(normalizedInvoice, lockedOrderId);
      if (nextInvoiceId) {
        try {
          const xml = await fetchInvoiceUblXml(storedSession, nextInvoiceId);
          setInvoiceXml(xml);
        } catch {
          // Leave invoice generation successful even if the XML fetch needs a later retry.
        }
      } else {
        setInvoiceXml(null);
      }
      pushDiagnostic("info", `Generated invoice for ${lockedOrderId}.`);
      return true;
    } catch (error) {
      const message = describeApiError(
        error,
        "order-invoice-create:",
        "Unable to generate the invoice.",
      );
      setInvoiceError(message);
      pushDiagnostic("error", `Invoice generation failed: ${message}`);
      return false;
    } finally {
      setInvoiceBusy(null);
    }
  };

  const loadInvoiceXml = async (): Promise<boolean> => {
    const activeInvoiceId = resolveInvoiceIdentifier();
    if (!storedSession || !activeInvoiceId) {
      return false;
    }

    setInvoiceBusy("xml");
    setInvoiceError(null);

    try {
      const xml = await fetchInvoiceUblXml(storedSession, activeInvoiceId);
      setInvoiceXml(xml);
      pushDiagnostic("info", `Fetched invoice XML for ${activeInvoiceId}.`);
      return true;
    } catch (error) {
      const message = describeApiError(error, "invoice-ubl:", "Unable to load the invoice XML.");
      setInvoiceError(message);
      pushDiagnostic("error", `Invoice XML fetch failed: ${message}`);
      return false;
    } finally {
      setInvoiceBusy(null);
    }
  };

  const downloadInvoicePdfFile = async (): Promise<boolean> => {
    const activeInvoiceId = resolveInvoiceIdentifier();
    if (!storedSession || !activeInvoiceId) {
      return false;
    }

    setInvoiceBusy("pdf");
    setInvoiceError(null);

    try {
      const pdfBlob = await fetchInvoicePdf(storedSession, activeInvoiceId);
      downloadDocumentBlob(`${activeInvoiceId}.pdf`, pdfBlob);
      pushDiagnostic("info", `Downloaded invoice PDF for ${activeInvoiceId}.`);
      return true;
    } catch (error) {
      const message = describeApiError(
        error,
        "invoice-pdf:",
        "Unable to download the invoice PDF.",
      );
      setInvoiceError(message);
      pushDiagnostic("error", `Invoice PDF download failed: ${message}`);
      return false;
    } finally {
      setInvoiceBusy(null);
    }
  };

  const submitInvoiceStatusUpdate = async (
    statusOverride?: string,
    paymentDateOverride?: string,
  ): Promise<boolean> => {
    const activeInvoiceId = resolveInvoiceIdentifier();
    if (!storedSession || !activeInvoiceId) {
      return false;
    }

    setInvoiceBusy("status");
    setInvoiceError(null);

    try {
      await transitionInvoiceStatus(storedSession, activeInvoiceId, {
        status: statusOverride ?? invoiceStatusDraft,
        payment_date: (paymentDateOverride ?? invoicePaymentDateDraft).trim() || null,
      });
      await refreshInvoiceRecord(activeInvoiceId);
      pushDiagnostic("info", `Updated invoice status for ${activeInvoiceId}.`);
      return true;
    } catch (error) {
      const message = describeApiError(
        error,
        "invoice-status:",
        "Unable to update the invoice status.",
      );
      setInvoiceError(message);
      pushDiagnostic("error", `Invoice status update failed: ${message}`);
      return false;
    } finally {
      setInvoiceBusy(null);
    }
  };

  const submitInvoiceUpdate = async () => {
    const activeInvoiceId = resolveInvoiceIdentifier();
    if (!storedSession || !activeInvoiceId) {
      return;
    }

    let parsedPayload: InvoiceUpdatePayload;
    try {
      parsedPayload = JSON.parse(invoiceUpdateDraft) as InvoiceUpdatePayload;
    } catch {
      setInvoiceError("Invoice updates must be valid JSON.");
      pushDiagnostic("warning", "Invoice update blocked by invalid JSON.");
      return;
    }

    setInvoiceBusy("update");
    setInvoiceError(null);

    try {
      await updateInvoice(storedSession, activeInvoiceId, parsedPayload);
      await refreshInvoiceRecord(activeInvoiceId);
      pushDiagnostic("info", `Updated invoice ${activeInvoiceId}.`);
    } catch (error) {
      const message = describeApiError(
        error,
        "invoice-update:",
        "Unable to update the invoice.",
      );
      setInvoiceError(message);
      pushDiagnostic("error", `Invoice update failed: ${message}`);
    } finally {
      setInvoiceBusy(null);
    }
  };

  const removeInvoiceDocument = async (): Promise<boolean> => {
    const activeInvoiceId = resolveInvoiceIdentifier();
    if (!storedSession || !activeInvoiceId || !lockedOrderId) {
      return false;
    }

    setInvoiceBusy("delete");
    setInvoiceError(null);

    try {
      await deleteInvoice(storedSession, activeInvoiceId);
      syncInvoiceRecord(null, lockedOrderId);
      setInvoiceXml(null);
      pushDiagnostic("info", `Deleted invoice ${activeInvoiceId}.`);
      return true;
    } catch (error) {
      const message = describeApiError(
        error,
        "invoice-delete:",
        "Unable to delete the invoice.",
      );
      setInvoiceError(message);
      pushDiagnostic("error", `Invoice delete failed: ${message}`);
      return false;
    } finally {
      setInvoiceBusy(null);
    }
  };

  const copyDespatchXml = async (): Promise<boolean> => {
    let xml = despatchState.xml;
    if (!xml) {
      if (!storedSession || !lockedOrderId) {
        return false;
      }
      try {
        xml = await fetchOrderDespatchXml(storedSession, lockedOrderId);
        setDespatchState(current => ({ ...current, xml }));
      } catch (error) {
        const message = describeApiError(
          error,
          "order-despatch:",
          "Unable to load the existing despatch advice.",
        );
        setDespatchError(message);
        pushDiagnostic("error", `Despatch fetch failed: ${message}`);
        return false;
      }
    }

    if (!xml) {
      setDespatchError("Unable to load the despatch XML.");
      return false;
    }

    await copyDocumentText("Despatch XML", xml);
    return true;
  };

  const downloadDespatchXmlFile = async (): Promise<boolean> => {
    let xml = despatchState.xml;
    if (!xml) {
      if (!storedSession || !lockedOrderId) {
        return false;
      }
      try {
        xml = await fetchOrderDespatchXml(storedSession, lockedOrderId);
        setDespatchState(current => ({ ...current, xml }));
      } catch (error) {
        const message = describeApiError(
          error,
          "order-despatch:",
          "Unable to load the existing despatch advice.",
        );
        setDespatchError(message);
        pushDiagnostic("error", `Despatch fetch failed: ${message}`);
        return false;
      }
    }

    if (!xml) {
      setDespatchError("Unable to load the despatch XML.");
      return false;
    }

    downloadDocumentBlob(
      `${lockedOrderId ?? "order"}-despatch.xml`,
      new Blob([xml], { type: "application/xml" }),
    );
    return true;
  };

  const copyInvoiceXml = async (): Promise<boolean> => {
    let xml = invoiceXml;
    if (!xml) {
      const activeInvoiceId = resolveInvoiceIdentifier();
      if (!storedSession || !activeInvoiceId) {
        return false;
      }
      try {
        xml = await fetchInvoiceUblXml(storedSession, activeInvoiceId);
        setInvoiceXml(xml);
        pushDiagnostic("info", `Fetched invoice XML for ${activeInvoiceId}.`);
      } catch (error) {
        const message = describeApiError(error, "invoice-ubl:", "Unable to load the invoice XML.");
        setInvoiceError(message);
        pushDiagnostic("error", `Invoice XML fetch failed: ${message}`);
        return false;
      }
    }

    if (!xml) {
      setInvoiceError("Unable to load the invoice XML.");
      return false;
    }

    await copyDocumentText("Invoice XML", xml);
    return true;
  };

  const buildLockedOrderVoiceConfirmation = (
    command: Exclude<
      LockedOrderAssistantCommand,
      { kind: "fetch_despatch" }
      | { kind: "copy_despatch_xml" }
      | { kind: "download_despatch_xml" }
      | { kind: "refresh_invoice" }
      | { kind: "fetch_invoice_xml" }
      | { kind: "copy_invoice_xml" }
      | { kind: "download_invoice_pdf" }
    >,
  ): AssistantActionResult => {
    if (command.kind === "generate_despatch") {
      return {
        kind: "confirm",
        message: "Generate the despatch advice for this locked order?",
        confirmLabel: "Generate despatch",
        execute: async () => {
          const success = await createDespatchDocument();
          return {
            kind: success ? "applied" : "rejected",
            message: success
              ? "Generated the despatch advice."
              : "Unable to generate the despatch advice.",
          };
        },
      };
    }

    if (command.kind === "generate_invoice") {
      return {
        kind: "confirm",
        message: "Generate the invoice for this locked order?",
        confirmLabel: "Generate invoice",
        execute: async () => {
          const success = await createInvoiceDocument();
          return {
            kind: success ? "applied" : "rejected",
            message: success ? "Generated the invoice." : "Unable to generate the invoice.",
          };
        },
      };
    }

    if (command.kind === "set_invoice_status") {
      return {
        kind: "confirm",
        message: `Set the invoice status to ${command.status}?`,
        confirmLabel: "Update status",
        execute: async () => {
          const success = await submitInvoiceStatusUpdate(
            command.status,
            command.paymentDate ?? undefined,
          );
          return {
            kind: success ? "applied" : "rejected",
            message: success
              ? `Updated the invoice status to ${command.status}.`
              : "Unable to update the invoice status.",
          };
        },
      };
    }

    return {
      kind: "confirm",
      message: "Delete the invoice for this order?",
      confirmLabel: "Delete invoice",
      execute: async () => {
        const success = await removeInvoiceDocument();
        return {
          kind: success ? "applied" : "rejected",
          message: success ? "Deleted the invoice." : "Unable to delete the invoice.",
        };
      },
    };
  };

  const executeLockedOrderVoiceCommand = async (
    command: LockedOrderAssistantCommand,
  ): Promise<AssistantActionResult> => {
    if (command.kind === "fetch_despatch") {
      const success = await fetchExistingDespatch();
      return {
        kind: success ? "applied" : "rejected",
        message: success ? "Loaded the despatch XML." : "Unable to load the despatch XML.",
      };
    }

    if (command.kind === "copy_despatch_xml") {
      const success = await copyDespatchXml();
      return {
        kind: success ? "applied" : "rejected",
        message: success ? "Copied the despatch XML." : "Unable to copy the despatch XML.",
      };
    }

    if (command.kind === "download_despatch_xml") {
      const success = await downloadDespatchXmlFile();
      return {
        kind: success ? "applied" : "rejected",
        message: success
          ? "Downloaded the despatch XML."
          : "Unable to download the despatch XML.",
      };
    }

    if (command.kind === "refresh_invoice") {
      const success = await refreshInvoiceRecord();
      return {
        kind: success ? "applied" : "rejected",
        message: success
          ? "Refreshed the invoice details."
          : "Unable to refresh the invoice details.",
      };
    }

    if (command.kind === "fetch_invoice_xml") {
      const success = await loadInvoiceXml();
      return {
        kind: success ? "applied" : "rejected",
        message: success ? "Loaded the invoice XML." : "Unable to load the invoice XML.",
      };
    }

    if (command.kind === "copy_invoice_xml") {
      const success = await copyInvoiceXml();
      return {
        kind: success ? "applied" : "rejected",
        message: success ? "Copied the invoice XML." : "Unable to copy the invoice XML.",
      };
    }

    if (command.kind === "download_invoice_pdf") {
      const success = await downloadInvoicePdfFile();
      return {
        kind: success ? "applied" : "rejected",
        message: success ? "Downloaded the invoice PDF." : "Unable to download the invoice PDF.",
      };
    }

    return buildLockedOrderVoiceConfirmation(command);
  };

  const startLockedOrderAssistantRequest = (transcript: string) => {
    const socket = documentsAssistantSocketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return null;
    }

    const activeInvoiceId = resolveInvoiceIdentifier();
    socket.send(
      JSON.stringify({
        type: "context.patch",
        payload: {
          orderId: lockedOrderId,
          hasDespatch: Boolean(despatchState.adviceId || despatchState.xml),
          hasInvoice: Boolean(activeInvoiceId),
          invoiceStatus:
            typeof invoiceRecord?.status === "string" && invoiceRecord.status.trim()
              ? invoiceRecord.status.trim()
              : null,
          viewerIsSeller,
        },
      }),
    );

    return new Promise<AssistantActionResult>(resolve => {
      const timeoutId = window.setTimeout(() => {
        if (documentsAssistantResultResolverRef.current) {
          documentsAssistantResultResolverRef.current = null;
          resolve({
            kind: "rejected",
            message: "The documents assistant timed out.",
          });
        }
      }, 12000);

      documentsAssistantResultResolverRef.current = resolve;
      socket.send(JSON.stringify({ type: "transcript.final", payload: { text: transcript } }));

      documentsAssistantResultResolverRef.current = result => {
        window.clearTimeout(timeoutId);
        resolve(result);
      };
    });
  };

  useEffect(() => {
    lockedOrderIdRef.current = lockedOrderId;
    hasDespatchRef.current = Boolean(despatchState.adviceId || despatchState.xml);
    hasInvoiceRef.current = Boolean(invoiceId);
    invoiceStatusRef.current =
      typeof invoiceRecord?.status === "string" && invoiceRecord.status.trim()
        ? invoiceRecord.status.trim()
        : null;
    viewerIsSellerRef.current = viewerIsSeller;
  }, [despatchState.adviceId, despatchState.xml, invoiceId, invoiceRecord?.status, lockedOrderId, viewerIsSeller]);

  useEffect(() => {
    const socket = new WebSocket(documentsAssistantWebSocketUrl);
    documentsAssistantSocketRef.current = socket;

    const sendContext = (type: "session.start" | "context.patch") => {
      if (socket.readyState !== WebSocket.OPEN) {
        return;
      }

      socket.send(
        JSON.stringify({
          type,
          payload: {
            orderId: lockedOrderIdRef.current,
            hasDespatch: hasDespatchRef.current,
            hasInvoice: hasInvoiceRef.current,
            invoiceStatus: invoiceStatusRef.current,
            viewerIsSeller: viewerIsSellerRef.current,
          },
        }),
      );
    };

    const handleOpen = () => {
      sendContext("session.start");
    };

    const handleMessage = async (event: MessageEvent<string>) => {
      const envelope = JSON.parse(event.data) as LockedOrderAssistantServerEnvelope;
      if (envelope.type === "transcript.echo") {
        if (envelope.payload?.kind === "partial") {
          setDocumentsAssistantLiveTranscript(envelope.payload.text ?? null);
        }
        if (envelope.payload?.kind === "final") {
          setDocumentsAssistantLiveTranscript(null);
        }
        return;
      }

      if (envelope.type === "assistant.command") {
        const resolver = documentsAssistantResultResolverRef.current;
        documentsAssistantResultResolverRef.current = null;
        const command = envelope.payload?.command;
        const result = command
          ? await executeLockedOrderVoiceCommand(command)
          : {
              kind: "rejected" as const,
              message: envelope.payload?.message ?? "I could not map that to a document action.",
            };
        resolver?.(result);
        return;
      }

      if (envelope.type === "error") {
        const resolver = documentsAssistantResultResolverRef.current;
        documentsAssistantResultResolverRef.current = null;
        resolver?.({
          kind: "rejected",
          message: envelope.payload?.message ?? "The documents assistant could not respond.",
        });
      }
    };

    const handleClose = () => {
      setDocumentsAssistantLiveTranscript(null);
      const resolver = documentsAssistantResultResolverRef.current;
      documentsAssistantResultResolverRef.current = null;
      resolver?.({
        kind: "rejected",
        message: "The documents assistant disconnected.",
      });
    };

    socket.addEventListener("open", handleOpen);
    socket.addEventListener("message", handleMessage);
    socket.addEventListener("close", handleClose);

    return () => {
      socket.removeEventListener("open", handleOpen);
      socket.removeEventListener("message", handleMessage);
      socket.removeEventListener("close", handleClose);
      documentsAssistantSocketRef.current = null;
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close();
      }
    };
  }, [documentsAssistantWebSocketUrl]);

  useEffect(() => {
    const socket = documentsAssistantSocketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return;
    }

    socket.send(
      JSON.stringify({
        type: "context.patch",
        payload: {
          orderId: lockedOrderIdRef.current,
          hasDespatch: hasDespatchRef.current,
          hasInvoice: hasInvoiceRef.current,
          invoiceStatus: invoiceStatusRef.current,
          viewerIsSeller: viewerIsSellerRef.current,
        },
      }),
    );
  }, [despatchState.adviceId, despatchState.xml, invoiceId, invoiceRecord?.status, lockedOrderId, viewerIsSeller]);

  const handleLockedOrderVoiceTranscript = async (
    transcript: string,
  ): Promise<AssistantActionResult> => {
    setDocumentsAssistantLiveTranscript(null);
    const streamedResult = await startLockedOrderAssistantRequest(transcript);
    if (streamedResult) {
      if (streamedResult.kind === "confirm" && streamedResult.message.startsWith("Internal error:")) {
        return {
          kind: "rejected",
          message: "The documents assistant could not complete that command.",
        };
      }
      if (streamedResult.kind === "confirm") {
        return streamedResult;
      }
      if (streamedResult.kind === "applied" || streamedResult.kind === "rejected") {
        return streamedResult;
      }
    }

    const command = parseLockedOrderVoiceCommand(transcript);
    if (!command) {
      return {
        kind: "rejected",
        message: "I could not map that to a document action.",
      };
    }

    return executeLockedOrderVoiceCommand(command);
  };

  const handleLockedOrderVoicePartialTranscript = (transcript: string) => {
    const socket = documentsAssistantSocketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setDocumentsAssistantLiveTranscript(transcript);
      return;
    }

    socket.send(JSON.stringify({ type: "transcript.partial", payload: { text: transcript } }));
  };

  const patchDraft = (nextDraft: OrderDraft, syncMode: "debounced" | "immediate" = "debounced") => {
    setDraftState(current => ({ ...current, draft: nextDraft }));
    if (syncMode === "immediate") {
      pendingDraftSyncRef.current = null;
      clearPendingDraftSync();
      sendSocketEvent("draft.patch", { draft: nextDraft });
      return;
    }
    queueDraftSync(nextDraft);
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
    if (
      !recognitionRef.current ||
      connectionStatus !== "connected" ||
      (isEditMode && editLoadState !== "ready")
    ) {
      pushDiagnostic("warning", "Microphone start blocked until the websocket is connected.");
      return;
    }

    setErrorMessage(null);
    flushPendingDraftSync();
    pushDiagnostic("info", "Microphone start requested.");
    recognitionRef.current.start();
    setListening(true);
  };

  const stopListening = () => {
    recognitionRef.current?.stop();
    setListening(false);
    pushDiagnostic("info", "Microphone stop requested.");
  };

  const commitDraft = async () => {
    if (!storedSession?.credential || !storedSession.contactEmail) {
      const message = "Log in or register a party first before creating a draft order.";
      setErrorMessage(message);
      pushDiagnostic("warning", "Commit blocked until credentials are stored locally.");
      return;
    }

    const payload = draftToOrderRequest(draftState.draft);
    if (!payload) {
      const message = "Complete the required fields before creating the draft order.";
      setErrorMessage(message);
      pushDiagnostic("warning", "Create blocked until the draft is complete.");
      return;
    }

    setErrorMessage(null);
    setConnectionMessage("Creating draft order...");

    try {
      const result = await createOrder(storedSession, payload);
      const ublXml = await fetchOrderUblXml(storedSession, result.orderId).catch(() => "");
      setLastOrder({
        orderId: result.orderId,
        status: result.status,
        createdAt: result.createdAt,
        ublXml,
        warnings: [],
      });
      setConnectionMessage("Draft order created successfully.");
      pushDiagnostic("info", `Created draft order ${result.orderId}.`);
    } catch (error) {
      const message =
        error instanceof Error && error.message.startsWith("order-create:403:")
          ? error.message.slice("order-create:403:".length) ||
            "You do not have permission to create this draft order."
          : error instanceof Error && error.message.startsWith("order-create:401:")
            ? "Log in or register a party first before creating a draft order."
            : "Unable to create the draft order.";
      setErrorMessage(message);
      pushDiagnostic("error", `Draft order create failed: ${message}`);
    }
  };

  const updateOrder = async () => {
    if (!storedSession || !orderId) {
      return;
    }

    const payload = draftToOrderRequest(draftState.draft);
    if (!payload) {
      const message = "Complete the required fields before saving the draft.";
      setErrorMessage(message);
      pushDiagnostic("warning", "Update blocked until the draft is complete.");
      return;
    }

    setErrorMessage(null);
    setConnectionMessage("Saving draft...");

    try {
      const result = await updateExistingOrder(storedSession, orderId, payload);
      const ublXml = await fetchOrderUblXml(storedSession, orderId).catch(() => null);
      const normalizedDraft = normalizeDraftState({
        ...emptyDraftState(),
        draft: payload,
        connectionStatus: draftState.connectionStatus,
      }).draft;

      setEditableOrderMeta(current =>
        current
          ? {
              ...current,
              status: result.status,
              updatedAt: result.updatedAt,
            }
          : current,
      );
      setInitialDraftSnapshot(normalizedDraft);
      setUpdatedOrder({
        orderId: result.orderId,
        status: result.status,
        updatedAt: result.updatedAt,
        ublXml,
      });
      setConnectionMessage("Draft updated successfully.");
      pushDiagnostic("info", `Updated draft ${result.orderId}.`);
    } catch (error) {
      const message =
        error instanceof Error && error.message.startsWith("order-update:409:")
          ? error.message.slice("order-update:409:".length) || "Draft can no longer be updated."
          : error instanceof Error && error.message === "order-update:404:"
            ? "The draft order could not be found."
            : "Unable to save the draft.";
      setErrorMessage(message);
      pushDiagnostic("error", `Draft save failed: ${message}`);
    }
  };

  const resetDraft = () => {
    if (isEditMode && initialDraftSnapshot) {
      setUpdatedOrder(null);
      setErrorMessage(null);
      setDraftState(current => ({
        ...current,
        draft: initialDraftSnapshot,
        transcriptLog: [],
        warnings: [],
        unresolved: [],
        currentPartial: "",
      }));
      sendSocketEvent("session.reset");
      pendingDraftSyncRef.current = null;
      clearPendingDraftSync();
      sendSocketEvent("draft.patch", { draft: initialDraftSnapshot });
      pushDiagnostic("info", "Reset the draft back to the stored order snapshot.");
      return;
    }

    setLastOrder(null);
    sendSocketEvent("session.reset");
  };

  const deleteCurrentOrder = async () => {
    if (!storedSession || !orderId) {
      return;
    }

    setDeletePending(true);
    setDeleteError(null);

    try {
      await deleteOrder(storedSession, orderId);
      pushDiagnostic("info", `Deleted order ${orderId}.`);
      navigate(`/orders?deleted=${encodeURIComponent(orderId)}`);
    } catch (error) {
      if (!(error instanceof Error)) {
        setDeleteError("The order could not be deleted.");
        setDeletePending(false);
        return;
      }

      if (error.message.startsWith("order-delete:404:")) {
        pushDiagnostic("warning", `Delete reported missing order ${orderId}.`);
        navigate("/orders");
        return;
      }

      if (
        error.message.startsWith("order-delete:401:") ||
        error.message.startsWith("order-delete:403:")
      ) {
        setDeleteError("You do not have permission to delete this order.");
      } else {
        setDeleteError("The order could not be deleted.");
      }
    } finally {
      setDeletePending(false);
    }
  };

  const requestPayload = draftToOrderRequest(draftState.draft);
  const missingRequiredFields = getDraftMissingFields(draftState.draft);
  const invoiceStatusValue =
    firstNonEmptyInvoiceString(invoiceRecord, ["status", "invoice_status"]) || "Not generated";
  const invoiceUpdatedAtValue =
    firstNonEmptyInvoiceString(invoiceRecord, ["updated_at", "updatedAt", "updated"]) || "Unknown";
  const invoiceIssueDateValue =
    firstNonEmptyInvoiceString(invoiceRecord, ["issue_date", "issueDate"]) || "Unknown";
  const invoiceCurrencyValue =
    firstNonEmptyInvoiceString(invoiceRecord, ["currency", "currency_code"]) ||
    draftState.draft.currency ||
    "Unknown";
  const pageTitle = isEditMode
    ? "Edit the order. Keep the live draft in sync."
    : "Speak the order. Watch the draft settle in real time.";
  const pageDescription = isEditMode
    ? "Use live transcript input or manual edits to refine the existing draft order, then save the updated draft back to the backend."
    : "Use browser speech recognition or manual edits to build the draft order and keep it in sync with the websocket session before saving it.";
  const primaryActionLabel = isEditMode ? "Save draft" : "Create draft order";
  const resetActionLabel = isEditMode ? "Reset changes" : "Reset draft";
  const resultTitle = isEditMode ? "Updated draft" : "Created draft";
  const resultEmptyCopy = isEditMode
    ? "Save the draft to update the stored draft order."
    : "Create the draft order once the required fields are complete.";
  const introStatusNote = editableOrderMeta
    ? `Order ${editableOrderMeta.orderId} · ${editableOrderMeta.status}`
    : null;
  const isLockedView = isEditMode && editLoadState === "locked";

  return (
    <div className="landing-root create-page-root">
      <div className="landing-container">
        <section className="landing-stage create-page-stage">
          <AppHeader />

          <main className={`create-page-main${isLockedView ? " create-page-main-locked" : ""}`}>
            <section className="create-page-intro" aria-labelledby="create-page-title">
              <div className="create-page-intro-copy">
                <h1 id="create-page-title">{pageTitle}</h1>
                {!isLockedView ? <p>{pageDescription}</p> : null}
              </div>
              <div className="create-page-runtime">
                <div className="create-page-runtime-state">
                  <span className={`create-page-state-dot create-page-state-${connectionStatus}`} />
                  <span className="create-page-runtime-label">{connectionStatus}</span>
                </div>
                <p>{connectionMessage}</p>
                <p className="create-page-backend">Backend: {backendHttpUrl}</p>
                {introStatusNote ? <p className="create-page-session-note">{introStatusNote}</p> : null}
                {storedSession ? (
                  <p className="create-page-session-note">
                    Registered as {storedSession.partyName} ({storedSession.contactEmail})
                  </p>
                ) : null}
              </div>
            </section>

            {(!isEditMode || editLoadState === "ready") && (
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
                onClick={isEditMode ? () => void updateOrder() : commitDraft}
                disabled={
                  isEditMode
                    ? editLoadState !== "ready" || requestPayload === null
                    : !isDraftReadyForCommit(draftState.draft)
                }
              >
                {primaryActionLabel}
              </button>
              <button
                type="button"
                className="landing-button landing-button-secondary"
                onClick={resetDraft}
              >
                {resetActionLabel}
              </button>
              {isEditMode ? (
                <button
                  type="button"
                  className="landing-button landing-button-danger"
                  onClick={() => {
                    setDeleteError(null);
                    setDeleteDialogOpen(true);
                  }}
                >
                  Delete order
                </button>
              ) : null}
            </section>
            )}

            {!speechSupported ? (
              <section className="create-page-banner create-page-banner-warning" role="status">
                This browser does not expose the Web Speech API. You can still edit the draft
                manually, but microphone controls are disabled.
              </section>
            ) : null}

            {errorMessage ? (
              <section className="create-page-banner create-page-banner-error" role="alert">
                {errorMessage}
              </section>
            ) : null}

            {(!isEditMode || editLoadState === "ready") && missingRequiredFields.length > 0 ? (
              <section
                className="create-page-banner create-page-banner-warning"
                aria-live="polite"
              >
                <p className="create-page-required-summary">
                  Fields marked * are required before {isEditMode ? "saving" : "creating"} the
                  draft order.
                </p>
                <ul className="create-page-required-list">
                  {missingRequiredFields.map(field => (
                    <li key={field}>{field}</li>
                  ))}
                </ul>
              </section>
            ) : null}

            {isEditMode && editLoadState === "loading" ? (
              <section className="create-page-panel create-page-state-panel">
                <h2>Loading order</h2>
                <p className="create-page-empty-copy">Fetching the stored order payload.</p>
              </section>
            ) : null}

            {isEditMode && editLoadState === "error" ? (
              <section className="create-page-panel create-page-state-panel" role="alert">
                <h2>Order unavailable</h2>
                <p className="create-page-empty-copy">
                  {errorMessage ?? "The order could not be loaded."}
                </p>
                <AppLink href="/orders" className="landing-button landing-button-secondary">
                  Back to dashboard
                </AppLink>
              </section>
            ) : null}

            {isEditMode && editLoadState === "locked" ? (
              <section className="create-page-locked-view">
                <article className="create-page-panel create-page-state-panel">
                  <h2>Order locked</h2>
                  <p className="create-page-empty-copy">
                    This order is no longer editable and is now view-only.
                  </p>
                  <AppLink href="/orders" className="landing-button landing-button-secondary">
                    Back to dashboard
                  </AppLink>
                </article>

                <section className="create-page-workspace create-page-workspace-readonly">
                  <div className="create-page-column">
                    <article className="create-page-panel">
                      <header className="create-page-panel-header">
                        <div>
                          <h2>Order details</h2>
                        </div>
                      </header>

                      <div className="create-page-subsection create-page-subsection-compact">
                        <div className="create-page-subsection-header">
                          <h3>Participants</h3>
                        </div>
                        <div className="create-page-form-grid">
                          <label>
                            Buyer email
                            <input readOnly value={draftState.draft.buyerEmail ?? ""} />
                          </label>
                          <label>
                            Seller email
                            <input readOnly value={draftState.draft.sellerEmail ?? ""} />
                          </label>
                        </div>
                      </div>

                      <div className="create-page-form-grid">
                        <label>
                          Buyer name
                          <input readOnly value={draftState.draft.buyerName ?? ""} />
                        </label>
                        <label>
                          Seller name
                          <input readOnly value={draftState.draft.sellerName ?? ""} />
                        </label>
                        <label>
                          Currency
                          <input readOnly value={draftState.draft.currency ?? ""} />
                        </label>
                        <label>
                          Issue date
                          <input readOnly value={draftState.draft.issueDate ?? ""} />
                        </label>
                        <label className="create-page-full-width">
                          Notes
                          <textarea readOnly value={draftState.draft.notes ?? ""} />
                        </label>
                      </div>

                      <section className="create-page-subsection">
                        <div className="create-page-subsection-header">
                          <h3>Delivery</h3>
                        </div>
                        <div className="create-page-form-grid">
                          <label>
                            Street
                            <input readOnly value={draftState.draft.delivery?.street ?? ""} />
                          </label>
                          <label>
                            City
                            <input readOnly value={draftState.draft.delivery?.city ?? ""} />
                          </label>
                          <label>
                            State
                            <input readOnly value={draftState.draft.delivery?.state ?? ""} />
                          </label>
                          <label>
                            Postcode
                            <input readOnly value={draftState.draft.delivery?.postcode ?? ""} />
                          </label>
                          <label>
                            Country
                            <input readOnly value={draftState.draft.delivery?.country ?? ""} />
                          </label>
                          <label>
                            Requested date
                            <input readOnly value={draftState.draft.delivery?.requestedDate ?? ""} />
                          </label>
                        </div>
                      </section>

                      <section className="create-page-subsection">
                        <div className="create-page-subsection-header">
                          <h3>Line items</h3>
                        </div>
                        {draftState.draft.lines.length === 0 ? (
                          <p className="create-page-empty-copy">No line items.</p>
                        ) : (
                          <div className="create-page-line-items">
                            {draftState.draft.lines.map((line, index) => (
                              <div className="create-page-line-item-card" key={`locked-line-${index}`}>
                                <label>
                                  Product
                                  <input readOnly value={line.productName ?? ""} />
                                </label>
                                <label>
                                  Quantity
                                  <input readOnly value={line.quantity ?? ""} />
                                </label>
                                <label>
                                  Unit code
                                  <input readOnly value={line.unitCode ?? ""} />
                                </label>
                                <label>
                                  Unit price
                                  <input readOnly value={line.unitPrice ?? ""} />
                                </label>
                              </div>
                            ))}
                          </div>
                        )}
                      </section>
                    </article>
                  </div>

                  <div className="create-page-column">
                    <article className="create-page-panel">
                      <header className="create-page-panel-header">
                        <div>
                          <h2>Order XML</h2>
                        </div>
                      </header>
                      <div className="create-page-result-grid">
                        <p>
                          <span className="create-page-label">Order ID</span>
                          {lockedOrder?.orderId ?? editableOrderMeta?.orderId ?? orderId}
                        </p>
                        <p>
                          <span className="create-page-label">Status</span>
                          {lockedOrder?.status ?? editableOrderMeta?.status ?? "Unknown"}
                        </p>
                        <p>
                          <span className="create-page-label">Updated</span>
                          {lockedOrder?.updatedAt ?? editableOrderMeta?.updatedAt ?? "Unknown"}
                        </p>
                        <p>
                          <span className="create-page-label">Created</span>
                          {lockedOrder?.createdAt ?? editableOrderMeta?.createdAt ?? "Unknown"}
                        </p>
                        <label className="create-page-full-width">
                          UBL XML
                          <textarea readOnly value={lockedOrder?.ublXml ?? ""} />
                        </label>
                      </div>
                    </article>

                    <article className="create-page-panel">
                      <header className="create-page-panel-header">
                        <div>
                          <h2>Documents</h2>
                        </div>
                      </header>

                      <div className="create-page-documents-assistant">
                        <VoiceAssistantDock
                          context="locked_order"
                          hint="Try “copy the invoice XML”, “download it as a PDF”, or “delete that invoice”."
                          disabledReason={
                            !lockedOrderId ? "Load a locked order before using document voice actions." : null
                          }
                          liveTranscript={documentsAssistantLiveTranscript}
                          streaming
                          onPartialTranscript={handleLockedOrderVoicePartialTranscript}
                          onTranscript={handleLockedOrderVoiceTranscript}
                        />
                      </div>

                      {documentClipboardMessage ? (
                        <div className="create-page-banner">{documentClipboardMessage}</div>
                      ) : null}

                      <section className="create-page-subsection create-page-subsection-compact">
                        <div className="create-page-subsection-header">
                          <div>
                            <h3>Despatch</h3>
                          </div>
                          <div className="create-page-inline-actions">
                            <button
                              type="button"
                              className="landing-button landing-button-primary create-page-compact-button"
                              onClick={() => {
                                void createDespatchDocument();
                              }}
                              disabled={!viewerIsSeller || despatchBusy !== null}
                              title={
                                viewerIsSeller
                                  ? undefined
                                  : "Only the seller on the order can generate a despatch advice."
                              }
                            >
                              {despatchBusy === "generate" ? "Generating..." : "Generate despatch"}
                            </button>
                            <button
                              type="button"
                              className="landing-button landing-button-secondary create-page-compact-button"
                              onClick={() => {
                                void fetchExistingDespatch();
                              }}
                              disabled={!lockedOrderId || despatchBusy !== null}
                            >
                              {despatchBusy === "fetch" ? "Loading..." : "Load existing XML"}
                            </button>
                          </div>
                        </div>

                        {!viewerIsSeller ? (
                          <p className="create-page-empty-copy">
                            You can only generate a despatch advice when logged in as the seller on this
                            order.
                          </p>
                        ) : null}
                        {despatchError ? (
                          <div className="create-page-banner create-page-banner-error" role="alert">
                            {despatchError}
                          </div>
                        ) : null}

                        <div className="create-page-result-grid">
                          <p>
                            <span className="create-page-label">Advice ID</span>
                            {despatchState.adviceId ?? "Not available"}
                          </p>
                          <p>
                            <span className="create-page-label">Access</span>
                            {viewerIsSeller ? "Seller can generate and view" : "View-only until created"}
                          </p>
                          <p>
                            <span className="create-page-label">XML state</span>
                            {despatchState.xml ? "Loaded" : "Not loaded"}
                          </p>
                          <label className="create-page-full-width">
                            Despatch XML
                            <textarea
                              readOnly
                              value={despatchState.xml ?? ""}
                              placeholder="Generate or load a despatch advice to view the XML."
                            />
                          </label>
                        </div>

                        <div className="create-page-inline-actions">
                          <button
                            type="button"
                            className="landing-button landing-button-secondary create-page-compact-button"
                            onClick={() => {
                              if (despatchState.xml) {
                                void copyDocumentText("Despatch XML", despatchState.xml);
                              }
                            }}
                            disabled={!despatchState.xml}
                          >
                            Copy XML
                          </button>
                          <button
                            type="button"
                            className="landing-button landing-button-secondary create-page-compact-button"
                            onClick={() => {
                              if (despatchState.xml) {
                                downloadDocumentBlob(
                                  `${lockedOrderId ?? "order"}-despatch.xml`,
                                  new Blob([despatchState.xml], { type: "application/xml" }),
                                );
                              }
                            }}
                            disabled={!despatchState.xml}
                          >
                            Download XML
                          </button>
                        </div>
                      </section>

                      <section className="create-page-subsection">
                        <div className="create-page-subsection-header">
                          <div>
                            <h3>Invoice</h3>
                          </div>
                          <div className="create-page-inline-actions">
                            <button
                              type="button"
                              className="landing-button landing-button-primary create-page-compact-button"
                              onClick={() => {
                                void createInvoiceDocument();
                              }}
                              disabled={invoiceBusy !== null}
                            >
                              {invoiceBusy === "generate" ? "Generating..." : "Generate invoice"}
                            </button>
                            <button
                              type="button"
                              className="landing-button landing-button-secondary create-page-compact-button"
                              onClick={() => {
                                void refreshInvoiceRecord();
                              }}
                              disabled={!invoiceId || invoiceBusy !== null}
                            >
                              {invoiceBusy === "fetch" ? "Refreshing..." : "Refresh invoice"}
                            </button>
                          </div>
                        </div>

                        {invoiceError ? (
                          <div className="create-page-banner create-page-banner-error" role="alert">
                            {invoiceError}
                          </div>
                        ) : null}

                        <div className="create-page-result-grid">
                          <p>
                            <span className="create-page-label">Invoice ID</span>
                            {invoiceId ?? "Not generated"}
                          </p>
                          <p>
                            <span className="create-page-label">Status</span>
                            {invoiceStatusValue}
                          </p>
                          <p>
                            <span className="create-page-label">Updated</span>
                            {invoiceUpdatedAtValue}
                          </p>
                          <p>
                            <span className="create-page-label">Issue date</span>
                            {invoiceIssueDateValue}
                          </p>
                          <p>
                            <span className="create-page-label">Currency</span>
                            {invoiceCurrencyValue}
                          </p>
                          <p>
                            <span className="create-page-label">Persistence</span>
                            {invoiceId
                              ? "Stored for this order in this browser session"
                              : "No local invoice mapping stored"}
                          </p>
                          <label className="create-page-full-width">
                            Invoice XML
                            <textarea
                              readOnly
                              value={invoiceXml ?? ""}
                              placeholder="Load the invoice XML once an invoice exists."
                            />
                          </label>
                          <label className="create-page-full-width">
                            Invoice JSON
                            <textarea
                              readOnly
                              value={invoiceRecord ? JSON.stringify(invoiceRecord, null, 2) : ""}
                              placeholder="Invoice metadata appears here after generation or refresh."
                            />
                          </label>
                        </div>

                        <div className="create-page-inline-actions">
                          <button
                            type="button"
                            className="landing-button landing-button-secondary create-page-compact-button"
                            onClick={() => {
                              void loadInvoiceXml();
                            }}
                            disabled={!invoiceId || invoiceBusy !== null}
                          >
                            {invoiceBusy === "xml" ? "Loading XML..." : "Load XML"}
                          </button>
                          <button
                            type="button"
                            className="landing-button landing-button-secondary create-page-compact-button"
                            onClick={() => {
                              void downloadInvoicePdfFile();
                            }}
                            disabled={!invoiceId || invoiceBusy !== null}
                          >
                            {invoiceBusy === "pdf" ? "Downloading..." : "Download PDF"}
                          </button>
                          <button
                            type="button"
                            className="landing-button landing-button-secondary create-page-compact-button"
                            onClick={() => {
                              if (invoiceXml) {
                                void copyDocumentText("Invoice XML", invoiceXml);
                              }
                            }}
                            disabled={!invoiceXml}
                          >
                            Copy XML
                          </button>
                          <button
                            type="button"
                            className="landing-button landing-button-danger create-page-compact-button"
                            onClick={() => {
                              void removeInvoiceDocument();
                            }}
                            disabled={!invoiceId || invoiceBusy !== null}
                          >
                            {invoiceBusy === "delete" ? "Deleting..." : "Delete invoice"}
                          </button>
                        </div>

                        <div className="create-page-form-grid">
                          <label>
                            Next status
                            <input
                              value={invoiceStatusDraft}
                              onChange={event => {
                                setInvoiceStatusDraft(event.target.value);
                              }}
                              placeholder="sent"
                              disabled={!invoiceId || invoiceBusy !== null}
                            />
                          </label>
                          <label>
                            Payment date
                            <input
                              type="date"
                              value={invoicePaymentDateDraft}
                              onChange={event => {
                                setInvoicePaymentDateDraft(event.target.value);
                              }}
                              disabled={!invoiceId || invoiceBusy !== null}
                            />
                          </label>
                          <label className="create-page-full-width">
                            Update invoice JSON
                            <textarea
                              value={invoiceUpdateDraft}
                              onChange={event => {
                                setInvoiceUpdateDraft(event.target.value);
                              }}
                              disabled={!invoiceId || invoiceBusy !== null}
                            />
                          </label>
                        </div>

                        <div className="create-page-inline-actions">
                          <button
                            type="button"
                            className="landing-button landing-button-secondary create-page-compact-button"
                            onClick={() => {
                              void submitInvoiceStatusUpdate();
                            }}
                            disabled={!invoiceId || invoiceBusy !== null}
                          >
                            {invoiceBusy === "status" ? "Updating status..." : "Update status"}
                          </button>
                          <button
                            type="button"
                            className="landing-button landing-button-secondary create-page-compact-button"
                            onClick={() => {
                              void submitInvoiceUpdate();
                            }}
                            disabled={!invoiceId || invoiceBusy !== null}
                          >
                            {invoiceBusy === "update" ? "Saving invoice..." : "Save invoice update"}
                          </button>
                        </div>
                      </section>
                    </article>
                  </div>
                </section>
              </section>
            ) : null}

            {(!isEditMode || editLoadState === "ready") && (
              <>
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
                  <section className="create-page-subsection create-page-subsection-compact">
                    <div className="create-page-subsection-header">
                      <div>
                        <h3>Participants</h3>
                        <p>Fields marked * are required.</p>
                      </div>
                    </div>
                    <div className="create-page-form-grid">
                      <label>
                        {formatRequiredFieldLabel("Buyer email")}
                        <input
                          aria-label="Buyer email"
                          aria-required="true"
                          aria-invalid={!draftState.draft.buyerEmail?.trim()}
                          readOnly={isEditMode}
                          value={draftState.draft.buyerEmail ?? ""}
                          onChange={event =>
                            updateDraftField("buyerEmail", nullableText(event.target.value))
                          }
                        />
                      </label>
                      <label>
                        {formatRequiredFieldLabel("Seller email")}
                        <input
                          aria-label="Seller email"
                          aria-required="true"
                          aria-invalid={!draftState.draft.sellerEmail?.trim()}
                          readOnly={isEditMode}
                          value={draftState.draft.sellerEmail ?? ""}
                          onChange={event =>
                            updateDraftField("sellerEmail", nullableText(event.target.value))
                          }
                        />
                      </label>
                    </div>
                  </section>
                  <div className="create-page-form-grid">
                    <label>
                      {formatRequiredFieldLabel("Buyer name")}
                      <input
                        aria-label="Buyer name"
                        aria-required="true"
                        aria-invalid={!draftState.draft.buyerName?.trim()}
                        value={draftState.draft.buyerName ?? ""}
                        onChange={event => updateDraftField("buyerName", nullableText(event.target.value))}
                      />
                    </label>
                    <label>
                      {formatRequiredFieldLabel("Seller name")}
                      <input
                        aria-label="Seller name"
                        aria-required="true"
                        aria-invalid={!draftState.draft.sellerName?.trim()}
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
                              {formatRequiredFieldLabel("Product")}
                              <input
                                aria-label={`Line ${index + 1} product`}
                                aria-required="true"
                                aria-invalid={!line.productName?.trim()}
                                value={line.productName ?? ""}
                                onChange={event =>
                                  updateLineItem(index, {
                                    productName: nullableText(event.target.value),
                                  })
                                }
                              />
                            </label>
                            <label>
                              {formatRequiredFieldLabel("Quantity")}
                              <input
                                aria-label={`Line ${index + 1} quantity`}
                                aria-required="true"
                                aria-invalid={(line.quantity ?? 0) <= 0}
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
                      <h2>{resultTitle}</h2>
                      <p>
                        {isEditMode
                          ? "The saved update response and refreshed UBL XML land here."
                          : "The REST order creation response and persisted UBL XML land here."}
                      </p>
                    </div>
                  </header>
                  {isEditMode && updatedOrder ? (
                    <div className="create-page-result-grid">
                      <p>
                        <span className="create-page-label">Order ID</span>
                        {updatedOrder.orderId}
                      </p>
                      <p>
                        <span className="create-page-label">Status</span>
                        {updatedOrder.status}
                      </p>
                      <p>
                        <span className="create-page-label">Updated</span>
                        {updatedOrder.updatedAt}
                      </p>
                      {updatedOrder.ublXml ? (
                        <label className="create-page-full-width">
                          UBL XML
                          <textarea readOnly value={updatedOrder.ublXml} />
                        </label>
                      ) : null}
                    </div>
                  ) : !isEditMode && lastOrder ? (
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
                    <p className="create-page-empty-copy">{resultEmptyCopy}</p>
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
              </>
            )}
          </main>
        </section>
      </div>

      <ConfirmDialog
        open={isEditMode && editLoadState === "ready" && deleteDialogOpen}
        title="Delete order?"
        description="This will permanently remove the draft order."
        confirmLabel="Delete order"
        loading={deletePending}
        errorMessage={deleteError}
        onClose={() => {
          if (deletePending) {
            return;
          }
          setDeleteError(null);
          setDeleteDialogOpen(false);
        }}
        onConfirm={() => void deleteCurrentOrder()}
      >
        Order ID: {editableOrderMeta?.orderId ?? orderId ?? ""}
      </ConfirmDialog>
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
