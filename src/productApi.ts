import type { StoredSession } from "./session";
import { getBackendHttpUrl } from "./voiceOrder";

export type ProductRecord = {
  prod_id: number | null;
  party_id: string;
  name: string;
  price: number;
  unit: string;
  description: string | null;
  category: string;
  release_date: string | null;
  available_units: number;
  is_visible: boolean;
  show_soldout: boolean;
  image_url: string;
};

export type ProductListResponse = {
  items: ProductRecord[];
  page: {
    limit: number | null;
    offset: number | null;
    hasMore: boolean;
    total: number;
  };
};

export type CreateProductInput = {
  partyId: string;
  name: string;
  price: number;
  unit: string;
  description: string;
  category: string;
  availableUnits: number;
  isVisible: boolean;
  showSoldout: boolean;
  releaseDate: string | null;
};

export type UpdateProductInput = {
  name?: string;
  price?: number;
  unit?: string;
  description?: string;
  category?: string;
  availableUnits?: number;
  isVisible?: boolean;
  showSoldout?: boolean;
  releaseDate?: string | null;
};

function buildAuthenticatedHeaders(session: StoredSession): HeadersInit {
  return {
    Authorization: `Bearer ${session.credential}`,
    "X-Party-Email": session.contactEmail,
  };
}

async function extractErrorDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      return body.detail;
    }
    if (Array.isArray(body.detail)) {
      return body.detail
        .map(item => {
          if (!item || typeof item !== "object") {
            return "";
          }
          const path = "path" in item && typeof item.path === "string" ? item.path : "";
          const issue = "issue" in item && typeof item.issue === "string" ? item.issue : "";
          return [path, issue].filter(Boolean).join(": ");
        })
        .filter(Boolean)
        .join(" ");
    }
    return "";
  } catch {
    return "";
  }
}

function appendOptionalField(formData: FormData, key: string, value: unknown) {
  if (value === undefined || value === null || value === "") {
    return;
  }
  formData.append(key, String(value));
}

export async function fetchInventory(
  session: StoredSession,
  limit = 100,
  offset = 0,
): Promise<ProductListResponse> {
  const response = await fetch(
    `${getBackendHttpUrl()}/v2/inventory?limit=${encodeURIComponent(String(limit))}&offset=${encodeURIComponent(
      String(offset),
    )}`,
    {
      headers: buildAuthenticatedHeaders(session),
    },
  );

  if (!response.ok) {
    const detail = await extractErrorDetail(response);
    throw new Error(`inventory-fetch:${response.status}:${detail}`);
  }

  return (await response.json()) as ProductListResponse;
}

export async function fetchMarketplaceProducts(
  limit = 100,
  offset = 0,
): Promise<ProductListResponse> {
  const response = await fetch(
    `${getBackendHttpUrl()}/v2/catalogue?limit=${encodeURIComponent(String(limit))}&offset=${encodeURIComponent(
      String(offset),
    )}`,
  );

  if (!response.ok) {
    const detail = await extractErrorDetail(response);
    throw new Error(`marketplace-products:${response.status}:${detail}`);
  }

  return (await response.json()) as ProductListResponse;
}

export async function createInventoryProduct(
  session: StoredSession,
  payload: CreateProductInput,
): Promise<ProductRecord> {
  const formData = new FormData();
  formData.append("party_id", payload.partyId);
  formData.append("name", payload.name);
  formData.append("price", String(payload.price));
  formData.append("unit", payload.unit);
  formData.append("description", payload.description);
  formData.append("category", payload.category);
  formData.append("is_visible", String(payload.isVisible));
  formData.append("available_units", String(payload.availableUnits));
  formData.append("show_soldout", String(payload.showSoldout));
  appendOptionalField(formData, "release_date", payload.releaseDate);

  const response = await fetch(`${getBackendHttpUrl()}/v2/inventory/add`, {
    method: "POST",
    headers: buildAuthenticatedHeaders(session),
    body: formData,
  });

  if (!response.ok) {
    const detail = await extractErrorDetail(response);
    throw new Error(`inventory-create:${response.status}:${detail}`);
  }

  return (await response.json()) as ProductRecord;
}

export async function updateInventoryProduct(
  session: StoredSession,
  productId: number,
  payload: UpdateProductInput,
): Promise<ProductRecord> {
  const formData = new FormData();
  appendOptionalField(formData, "name", payload.name);
  appendOptionalField(formData, "price", payload.price);
  appendOptionalField(formData, "unit", payload.unit);
  appendOptionalField(formData, "description", payload.description);
  appendOptionalField(formData, "category", payload.category);
  appendOptionalField(formData, "available_units", payload.availableUnits);
  appendOptionalField(formData, "is_visible", payload.isVisible);
  appendOptionalField(formData, "show_soldout", payload.showSoldout);
  appendOptionalField(formData, "release_date", payload.releaseDate);

  const response = await fetch(`${getBackendHttpUrl()}/v2/inventory/${productId}`, {
    method: "PATCH",
    headers: buildAuthenticatedHeaders(session),
    body: formData,
  });

  if (!response.ok) {
    const detail = await extractErrorDetail(response);
    throw new Error(`inventory-update:${response.status}:${detail}`);
  }

  return (await response.json()) as ProductRecord;
}

export async function deleteInventoryProduct(
  session: StoredSession,
  productId: number,
): Promise<void> {
  const response = await fetch(`${getBackendHttpUrl()}/v2/inventory/${productId}`, {
    method: "DELETE",
    headers: buildAuthenticatedHeaders(session),
  });

  if (!response.ok) {
    const detail = await extractErrorDetail(response);
    throw new Error(`inventory-delete:${response.status}:${detail}`);
  }
}
