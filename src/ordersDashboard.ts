import { getBackendHttpUrl } from "./voiceOrder";
import type { StoredSession } from "./session";

export type SellerAnalytics = {
  totalOrders: number;
  totalIncome: number;
  itemsSold: number;
  averageItemSoldPrice: number;
  averageOrderAmount: number;
  averageOrderItemNumber: number;
  averageDailyIncome: number;
  averageDailyOrders: number;
  ordersPending: number;
  ordersCompleted: number;
  ordersCancelled: number;
  mostSuccessfulDay: string | null;
  mostSalesMade: number;
  mostPopularProductCode: string | null;
  mostPopularProductName: string | null;
  mostPopularProductSales: number;
};

export type BuyerAnalytics = {
  totalOrders: number;
  totalSpent: number;
  itemsBought: number;
  averageItemPrice: number;
  averageOrderAmount: number;
  averageItemsPerOrder: number;
  averageDailySpend: number;
  averageDailyOrders: number;
};

export type SellerAnalyticsResponse = {
  role: "seller";
  analytics: SellerAnalytics;
};

export type BuyerAnalyticsResponse = {
  role: "buyer";
  analytics: BuyerAnalytics;
};

export type CombinedAnalyticsResponse = {
  role: "buyer_and_seller";
  sellerAnalytics: SellerAnalytics;
  buyerAnalytics: BuyerAnalytics;
  netProfit: number;
};

export type NoOrdersAnalyticsResponse = {
  message: string;
};

export type OrdersAnalyticsResponse =
  | SellerAnalyticsResponse
  | BuyerAnalyticsResponse
  | CombinedAnalyticsResponse
  | NoOrdersAnalyticsResponse;

export type OrderListItem = {
  orderId: string;
  status: string;
  createdAt: string;
  updatedAt: string;
  buyerName: string | null;
  sellerName: string | null;
  issueDate: string | null;
};

export type OrderListPage = {
  limit: number;
  offset: number;
  hasMore: boolean;
  total: number;
};

export type OrderListResponse = {
  items: OrderListItem[];
  page: OrderListPage;
};

export type DashboardDateRange = {
  fromDate: string;
  toDate: string;
};

function parseDateInputParts(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) {
    return null;
  }

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);

  if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) {
    return null;
  }

  return { year, month, day };
}

function formatUtcDateInputValue(date: Date) {
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function buildAuthenticatedHeaders(session: StoredSession): HeadersInit {
  return {
    Authorization: `Bearer ${session.credential}`,
    "X-Party-Email": session.contactEmail,
  };
}

export async function fetchOrdersAnalytics(
  session: StoredSession,
  dateRange: DashboardDateRange,
): Promise<OrdersAnalyticsResponse> {
  const backendUrl = getBackendHttpUrl();
  const params = new URLSearchParams({
    fromDate: dateRange.fromDate,
    toDate: dateRange.toDate,
  });

  const response = await fetch(`${backendUrl}/v1/analytics/orders?${params.toString()}`, {
    headers: buildAuthenticatedHeaders(session),
  });

  if (!response.ok) {
    throw new Error(`analytics:${response.status}`);
  }

  return (await response.json()) as OrdersAnalyticsResponse;
}

export async function fetchRecentOrders(session: StoredSession): Promise<OrderListResponse> {
  const backendUrl = getBackendHttpUrl();
  const params = new URLSearchParams({
    limit: "10",
    offset: "0",
  });

  const response = await fetch(`${backendUrl}/v1/orders?${params.toString()}`, {
    headers: buildAuthenticatedHeaders(session),
  });

  if (!response.ok) {
    throw new Error(`orders:${response.status}`);
  }

  return (await response.json()) as OrderListResponse;
}

export function getDefaultDashboardDateRange(now: Date = new Date()): DashboardDateRange {
  const end = new Date(
    Date.UTC(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999),
  );
  const start = new Date(
    Date.UTC(now.getFullYear(), now.getMonth(), now.getDate() - 29, 0, 0, 0, 0),
  );

  return {
    fromDate: start.toISOString(),
    toDate: end.toISOString(),
  };
}

export function isoToDateInputValue(value: string): string {
  if (!value) {
    return "";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return formatUtcDateInputValue(date);
}

export function dateInputValueToIso(value: string, boundary: "start" | "end"): string {
  if (!value) {
    return "";
  }

  const parts = parseDateInputParts(value);
  if (!parts) {
    return "";
  }

  const hours = boundary === "end" ? 23 : 0;
  const minutes = boundary === "end" ? 59 : 0;
  const seconds = boundary === "end" ? 59 : 0;
  const milliseconds = boundary === "end" ? 999 : 0;

  return new Date(
    Date.UTC(parts.year, parts.month - 1, parts.day, hours, minutes, seconds, milliseconds),
  ).toISOString();
}

export function getDateRangeDayCountLabel(range: DashboardDateRange): string {
  const startValue = isoToDateInputValue(range.fromDate);
  const endValue = isoToDateInputValue(range.toDate);
  const start = new Date(`${startValue}T00:00:00Z`);
  const end = new Date(`${endValue}T00:00:00Z`);

  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) {
    return "Custom range";
  }

  const days = Math.round((end.getTime() - start.getTime()) / 86_400_000) + 1;
  return `${days} ${days === 1 ? "day" : "days"}`;
}

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency: "AUD",
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-AU", {
    maximumFractionDigits: value % 1 === 0 ? 0 : 2,
  }).format(value);
}

export function formatDateLabel(value: string | null): string {
  if (!value) {
    return "No data";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}

export function formatDateTimeLabel(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}
