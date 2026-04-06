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
  buyerEmail: string | null;
  buyerName: string | null;
  sellerEmail: string | null;
  sellerName: string | null;
  currency: string | null;
  issueDate: string | null;
  notes: string | null;
  delivery: DraftDelivery | null;
  lines: DraftLineItem[];
};

export type OrderRequestPayload = {
  buyerEmail: string;
  buyerName: string;
  sellerEmail: string;
  sellerName: string;
  currency: string | null;
  issueDate: string | null;
  notes: string | null;
  delivery: DraftDelivery | null;
  lines: {
    productName: string;
    quantity: number;
    unitCode: string | null;
    unitPrice: string | null;
  }[];
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

type EnvImportMeta = ImportMeta & {
  env?: Record<string, string | undefined>;
};

function getConfiguredBackendUrl(): string | undefined {
  const importMetaEnv = (import.meta as EnvImportMeta).env;
  const fromImportMeta = importMetaEnv?.BUN_PUBLIC_BACKEND_URL;
  if (typeof fromImportMeta === "string" && fromImportMeta.trim()) {
    return fromImportMeta;
  }

  if (typeof process !== "undefined" && typeof process.env?.BUN_PUBLIC_BACKEND_URL === "string") {
    return process.env.BUN_PUBLIC_BACKEND_URL;
  }

  return undefined;
}

const CONFIGURED_BACKEND_URL = getConfiguredBackendUrl();

export const emptyLineItem = (): DraftLineItem => ({
  productName: null,
  quantity: null,
  unitCode: "EA",
  unitPrice: null,
});

export const emptyDraft = (): OrderDraft => ({
  buyerEmail: null,
  buyerName: null,
  sellerEmail: null,
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

export function draftToOrderRequest(draft: OrderDraft): OrderRequestPayload | null {
  if (
    !draft.buyerEmail?.trim() ||
    !draft.buyerName?.trim() ||
    !draft.sellerEmail?.trim() ||
    !draft.sellerName?.trim() ||
    draft.lines.length === 0
  ) {
    return null;
  }

  const lines = draft.lines.map(line => {
    if (!line.productName?.trim() || (line.quantity ?? 0) <= 0) {
      return null;
    }

    return {
      productName: line.productName.trim(),
      quantity: line.quantity ?? 0,
      unitCode: line.unitCode?.trim().toUpperCase() || "EA",
      unitPrice: line.unitPrice?.trim() || null,
    };
  });

  if (lines.some(line => line === null)) {
    return null;
  }

  return {
    buyerEmail: draft.buyerEmail.trim().toLowerCase(),
    buyerName: draft.buyerName.trim(),
    sellerEmail: draft.sellerEmail.trim().toLowerCase(),
    sellerName: draft.sellerName.trim(),
    currency: draft.currency?.trim().toUpperCase() || null,
    issueDate: draft.issueDate?.trim() || null,
    notes: draft.notes?.trim() || null,
    delivery: draft.delivery
      ? {
          street: draft.delivery.street?.trim() || null,
          city: draft.delivery.city?.trim() || null,
          state: draft.delivery.state?.trim() || null,
          postcode: draft.delivery.postcode?.trim() || null,
          country: draft.delivery.country?.trim() || null,
          requestedDate: draft.delivery.requestedDate?.trim() || null,
        }
      : null,
    lines: lines.filter((line): line is NonNullable<typeof line> => line !== null),
  };
}

export function getBackendHttpUrl(): string {
  if (CONFIGURED_BACKEND_URL) {
    return CONFIGURED_BACKEND_URL.replace(/\/$/, "");
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
