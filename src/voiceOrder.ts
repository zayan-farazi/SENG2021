export type TranscriptEntry = {
  kind: "final";
  text: string;
};

export type TranscriptAnnotation = {
  transcript: string;
  message: string;
};

export type DraftLineItem = {
  productName: string | null;
  quantity: number | null;
  unitCode: string | null;
  unitPrice: string | null;
};

export type DraftDelivery = {
  street: string | null;
  city: string | null;
  state: string | null;
  postcode: string | null;
  country: string | null;
  requestedDate: string | null;
};

export type OrderDraft = {
  buyerName: string | null;
  sellerName: string | null;
  currency: string | null;
  issueDate: string | null;
  notes: string | null;
  delivery: DraftDelivery | null;
  lines: DraftLineItem[];
};

export type DraftState = {
  draft: OrderDraft;
  transcriptLog: TranscriptEntry[];
  warnings: TranscriptAnnotation[];
  unresolved: TranscriptAnnotation[];
  currentPartial: string;
  connectionStatus: string;
};

export type OrderResponse = {
  orderId: string;
  status: string;
  createdAt: string;
  ublXml: string;
  warnings: string[];
};

export const emptyLineItem = (): DraftLineItem => ({
  productName: null,
  quantity: null,
  unitCode: "EA",
  unitPrice: null,
});

export const emptyDraft = (): OrderDraft => ({
  buyerName: null,
  sellerName: null,
  currency: null,
  issueDate: null,
  notes: null,
  delivery: null,
  lines: [],
});

export const emptyDraftState = (): DraftState => ({
  draft: emptyDraft(),
  transcriptLog: [],
  warnings: [],
  unresolved: [],
  currentPartial: "",
  connectionStatus: "connecting",
});

export function isDraftReadyForCommit(draft: OrderDraft): boolean {
  if (!draft.buyerName || !draft.sellerName || draft.lines.length === 0) {
    return false;
  }

  return draft.lines.every(line => Boolean(line.productName?.trim()) && (line.quantity ?? 0) > 0);
}

function getConfiguredBackendUrl(): string | undefined {
  const processEnv = typeof process !== "undefined" ? process.env : undefined;
  return processEnv?.BUN_PUBLIC_BACKEND_URL;
}

export function getBackendHttpUrl(): string {
  const configured = getConfiguredBackendUrl();
  if (configured) {
    return configured.replace(/\/$/, "");
  }

  const protocol = window.location.protocol === "https:" ? "https:" : "http:";
  const hostname = window.location.hostname || "127.0.0.1";
  return `${protocol}//${hostname}:8000`;
}

export function getBackendWebSocketUrl(): string {
  return getBackendHttpUrl().replace(/^http/, "ws") + "/v1/order/draft/ws";
}

export function normalizeDraftState(state: DraftState): DraftState {
  return {
    ...state,
    draft: {
      ...emptyDraft(),
      ...state.draft,
      delivery: state.draft.delivery ? { ...emptyDelivery(), ...state.draft.delivery } : null,
      lines: state.draft.lines.length > 0 ? state.draft.lines.map(line => ({ ...emptyLineItem(), ...line })) : [],
    },
  };
}

export function emptyDelivery(): DraftDelivery {
  return {
    street: null,
    city: null,
    state: null,
    postcode: null,
    country: null,
    requestedDate: null,
  };
}
