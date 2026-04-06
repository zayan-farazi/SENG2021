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

function buildAuthenticatedHeaders(session: StoredSession): HeadersInit {
  return {
    Authorization: `Bearer ${session.credential}`,
    "X-Party-Email": session.contactEmail,
  };
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
      .then(body => body?.detail)
      .catch(() => undefined);
    throw new Error(`order-update:${response.status}:${typeof detail === "string" ? detail : ""}`);
  }

  return (await response.json()) as OrderUpdateResult;
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
      detail = typeof body.detail === "string" ? body.detail : "";
    } catch {
      detail = "";
    }
    throw new Error(`order-delete:${response.status}:${detail}`);
  }
}
