import type { StoredSession } from "./session";
import { getBackendHttpUrl, type OrderDraft, type OrderRequestPayload } from "./voiceOrder";

export type EditableOrderResponse = {
  orderId: string;
  status: string;
  createdAt: string;
  updatedAt: string;
  payload: OrderDraft;
};

export type OrderUpdateResult = {
  orderId: string;
  status: string;
  updatedAt: string;
};

export type OrderCreateResult = {
  orderId: string;
  status: string;
  createdAt: string;
};

export type OrderSubmitResult = {
  orderId: string;
  status: string;
  updatedAt: string;
};

export type OrderDespatch = {
  adviceId: string | null;
  xml: string;
};

export type OrderDespatchResult = {
  orderId: string;
  updatedAt?: string;
  despatch: OrderDespatch;
};

export type InvoiceRecord = Record<string, unknown> & {
  invoice_id?: string;
  invoiceId?: string;
  status?: string;
  updated_at?: string;
  updatedAt?: string;
  issue_date?: string;
  issueDate?: string;
  currency?: string;
};

export type OrderInvoiceResult = {
  orderId: string;
  invoice: InvoiceRecord;
};

export type InvoiceStatusUpdatePayload = {
  status: string;
  payment_date?: string | null;
};

export type InvoiceUpdatePayload = Record<string, unknown>;

function buildAuthenticatedHeaders(session: StoredSession): HeadersInit {
  return {
    Authorization: `Bearer ${session.credential}`,
    "X-Party-Email": session.contactEmail,
  };
}

function formatResponseDetail(detail: unknown): string {
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map(entry => {
        if (!entry || typeof entry !== "object") {
          return "";
        }

        const issue = "issue" in entry && typeof entry.issue === "string" ? entry.issue : "";
        const path = "path" in entry && typeof entry.path === "string" ? entry.path : "";
        if (path && issue) {
          return `${path}: ${issue}`;
        }
        return issue || path;
      })
      .filter(Boolean)
      .join(" ");
  }

  return "";
}

async function extractErrorDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    return formatResponseDetail(body?.detail);
  } catch {
    return "";
  }
}

export async function fetchEditableOrder(
  session: StoredSession,
  orderId: string,
): Promise<EditableOrderResponse> {
  const response = await fetch(`${getBackendHttpUrl()}/v1/order/${orderId}/payload`, {
    headers: buildAuthenticatedHeaders(session),
  });

  if (!response.ok) {
    throw new Error(`order-payload:${response.status}`);
  }

  return (await response.json()) as EditableOrderResponse;
}

export async function updateExistingOrder(
  session: StoredSession,
  orderId: string,
  payload: OrderRequestPayload,
): Promise<OrderUpdateResult> {
  const response = await fetch(`${getBackendHttpUrl()}/v1/order/${orderId}`, {
    method: "PUT",
    headers: {
      ...buildAuthenticatedHeaders(session),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const detail = await response
      .json()
      .then(body => formatResponseDetail(body?.detail))
      .catch(() => "");
    throw new Error(`order-update:${response.status}:${detail}`);
  }

  return (await response.json()) as OrderUpdateResult;
}

export async function createOrder(
  session: StoredSession,
  payload: OrderRequestPayload,
): Promise<OrderCreateResult> {
  const response = await fetch(`${getBackendHttpUrl()}/v1/order/create`, {
    method: "POST",
    headers: {
      ...buildAuthenticatedHeaders(session),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const detail = await response
      .json()
      .then(body => formatResponseDetail(body?.detail))
      .catch(() => "");
    throw new Error(`order-create:${response.status}:${detail}`);
  }

  return (await response.json()) as OrderCreateResult;
}

export async function submitOrder(
  session: StoredSession,
  orderId: string,
): Promise<OrderSubmitResult> {
  const response = await fetch(`${getBackendHttpUrl()}/v1/order/${orderId}/submit`, {
    method: "POST",
    headers: buildAuthenticatedHeaders(session),
  });

  if (!response.ok) {
    const detail = await extractErrorDetail(response);
    throw new Error(`order-submit:${response.status}:${detail}`);
  }

  return (await response.json()) as OrderSubmitResult;
}

export async function fetchOrderUblXml(session: StoredSession, orderId: string): Promise<string> {
  const response = await fetch(`${getBackendHttpUrl()}/v1/order/${orderId}/ubl`, {
    headers: buildAuthenticatedHeaders(session),
  });

  if (!response.ok) {
    throw new Error(`order-ubl:${response.status}`);
  }

  return await response.text();
}

export async function deleteOrder(session: StoredSession, orderId: string): Promise<void> {
  const response = await fetch(`${getBackendHttpUrl()}/v1/order/${orderId}`, {
    method: "DELETE",
    headers: buildAuthenticatedHeaders(session),
  });

  if (!response.ok) {
    let detail = "";
    try {
      const body = (await response.json()) as { detail?: string };
      detail = formatResponseDetail(body.detail);
    } catch {
      detail = "";
    }
    throw new Error(`order-delete:${response.status}:${detail}`);
  }
}

export async function generateOrderDespatch(
  session: StoredSession,
  orderId: string,
): Promise<OrderDespatchResult> {
  const response = await fetch(`${getBackendHttpUrl()}/v1/order/${orderId}/despatch`, {
    method: "POST",
    headers: buildAuthenticatedHeaders(session),
  });

  if (!response.ok) {
    const detail = await extractErrorDetail(response);
    throw new Error(`order-despatch-create:${response.status}:${detail}`);
  }

  return (await response.json()) as OrderDespatchResult;
}

export async function fetchOrderDespatchXml(
  session: StoredSession,
  orderId: string,
): Promise<string> {
  const response = await fetch(`${getBackendHttpUrl()}/v1/order/${orderId}/despatch`, {
    headers: buildAuthenticatedHeaders(session),
  });

  if (!response.ok) {
    const detail = await extractErrorDetail(response);
    throw new Error(`order-despatch:${response.status}:${detail}`);
  }

  return await response.text();
}

export async function generateOrderInvoice(
  session: StoredSession,
  orderId: string,
): Promise<OrderInvoiceResult> {
  const response = await fetch(`${getBackendHttpUrl()}/v1/order/${orderId}/invoice`, {
    method: "POST",
    headers: buildAuthenticatedHeaders(session),
  });

  if (!response.ok) {
    const detail = await extractErrorDetail(response);
    throw new Error(`order-invoice-create:${response.status}:${detail}`);
  }

  return (await response.json()) as OrderInvoiceResult;
}

export async function fetchInvoice(
  session: StoredSession,
  invoiceId: string,
): Promise<InvoiceRecord> {
  const response = await fetch(`${getBackendHttpUrl()}/v1/invoice/${invoiceId}`, {
    headers: buildAuthenticatedHeaders(session),
  });

  if (!response.ok) {
    const detail = await extractErrorDetail(response);
    throw new Error(`invoice-fetch:${response.status}:${detail}`);
  }

  return (await response.json()) as InvoiceRecord;
}

export async function fetchInvoiceUblXml(
  session: StoredSession,
  invoiceId: string,
): Promise<string> {
  const response = await fetch(`${getBackendHttpUrl()}/v1/invoice/${invoiceId}/ubl`, {
    headers: buildAuthenticatedHeaders(session),
  });

  if (!response.ok) {
    const detail = await extractErrorDetail(response);
    throw new Error(`invoice-ubl:${response.status}:${detail}`);
  }

  return await response.text();
}

export async function fetchInvoicePdf(
  session: StoredSession,
  invoiceId: string,
): Promise<Blob> {
  const response = await fetch(`${getBackendHttpUrl()}/v1/invoice/${invoiceId}/pdf`, {
    headers: buildAuthenticatedHeaders(session),
  });

  if (!response.ok) {
    const detail = await extractErrorDetail(response);
    throw new Error(`invoice-pdf:${response.status}:${detail}`);
  }

  return await response.blob();
}

export async function updateInvoice(
  session: StoredSession,
  invoiceId: string,
  payload: InvoiceUpdatePayload,
): Promise<InvoiceRecord> {
  const response = await fetch(`${getBackendHttpUrl()}/v1/invoice/${invoiceId}`, {
    method: "PUT",
    headers: {
      ...buildAuthenticatedHeaders(session),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const detail = await extractErrorDetail(response);
    throw new Error(`invoice-update:${response.status}:${detail}`);
  }

  return (await response.json()) as InvoiceRecord;
}

export async function deleteInvoice(
  session: StoredSession,
  invoiceId: string,
): Promise<void> {
  const response = await fetch(`${getBackendHttpUrl()}/v1/invoice/${invoiceId}`, {
    method: "DELETE",
    headers: buildAuthenticatedHeaders(session),
  });

  if (!response.ok) {
    const detail = await extractErrorDetail(response);
    throw new Error(`invoice-delete:${response.status}:${detail}`);
  }
}

export async function transitionInvoiceStatus(
  session: StoredSession,
  invoiceId: string,
  payload: InvoiceStatusUpdatePayload,
): Promise<InvoiceRecord> {
  const response = await fetch(`${getBackendHttpUrl()}/v1/invoice/${invoiceId}/status`, {
    method: "POST",
    headers: {
      ...buildAuthenticatedHeaders(session),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const detail = await extractErrorDetail(response);
    throw new Error(`invoice-status:${response.status}:${detail}`);
  }

  return (await response.json()) as InvoiceRecord;
}
