import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { ChartNoAxesColumn, Package2, TrendingUp } from "lucide-react";
import { AppHeader } from "../components/AppHeader";
import { AppLink } from "../components/AppLink";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { deleteOrder } from "../orderApi";
import {
  dateInputValueToIso,
  fetchOrdersAnalytics,
  fetchRecentOrders,
  formatCurrency,
  formatDateLabel,
  formatDateTimeLabel,
  formatNumber,
  getDateRangeDayCountLabel,
  getDefaultDashboardDateRange,
  isoToDateInputValue,
  type BuyerAnalytics,
  type CombinedAnalyticsResponse,
  type OrderListItem,
  type OrderListResponse,
  type OrdersAnalyticsResponse,
  type SellerAnalytics,
} from "../ordersDashboard";
import { useStoredSession } from "../session";
import "../orders-dashboard.css";

type LoadState = "idle" | "loading" | "ready" | "error";
type ChartTone = "blue" | "cyan" | "amber" | "violet";
type ChartDatum = {
  label: string;
  value: number;
  tone: ChartTone;
  detail?: string;
};

function getInitialDeletedOrderNotice(): string | null {
  const deletedOrderId = new URLSearchParams(window.location.search).get("deleted");
  return deletedOrderId ? `Order ${deletedOrderId} deleted.` : null;
}

function clearDeletedOrderQueryParam() {
  const url = new URL(window.location.href);
  if (!url.searchParams.has("deleted")) {
    return;
  }

  url.searchParams.delete("deleted");
  window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
}

function isNoOrdersResponse(
  analytics: OrdersAnalyticsResponse | null,
): analytics is { message: string } {
  return Boolean(analytics && "message" in analytics);
}

function getHeadlineValue(analytics: OrdersAnalyticsResponse | null): string {
  if (!analytics) {
    return "--";
  }
  if (isNoOrdersResponse(analytics)) {
    return "No data";
  }
  if (analytics.role === "seller") {
    return formatCurrency(analytics.analytics.totalIncome);
  }
  if (analytics.role === "buyer") {
    return formatCurrency(analytics.analytics.totalSpent);
  }
  return formatCurrency(analytics.netProfit);
}

function getHeadlineLabel(analytics: OrdersAnalyticsResponse | null): string {
  if (!analytics) {
    return "Awaiting analytics";
  }
  if (isNoOrdersResponse(analytics)) {
    return "No orders found";
  }
  if (analytics.role === "seller") {
    return "Total revenue";
  }
  if (analytics.role === "buyer") {
    return "Total expenses";
  }
  return "Net profit";
}

function getSummaryTiles(analytics: OrdersAnalyticsResponse | null) {
  if (!analytics || isNoOrdersResponse(analytics)) {
    return [];
  }
  if (analytics.role === "seller") {
    return [
      { label: "Total orders", value: formatNumber(analytics.analytics.totalOrders) },
      { label: "Daily income", value: formatCurrency(analytics.analytics.averageDailyIncome) },
      { label: "Items sold", value: formatNumber(analytics.analytics.itemsSold) },
    ];
  }
  if (analytics.role === "buyer") {
    return [
      { label: "Total orders", value: formatNumber(analytics.analytics.totalOrders) },
      { label: "Daily spend", value: formatCurrency(analytics.analytics.averageDailySpend) },
      { label: "Items bought", value: formatNumber(analytics.analytics.itemsBought) },
    ];
  }
  const totalOrders =
    analytics.sellerAnalytics.totalOrders + analytics.buyerAnalytics.totalOrders;
  return [
    { label: "Total revenue", value: formatCurrency(analytics.sellerAnalytics.totalIncome) },
    { label: "Total expenses", value: formatCurrency(analytics.buyerAnalytics.totalSpent) },
    { label: "Total Orders", value: formatNumber(totalOrders) },
  ];
}

function buildChartRows(analytics: OrdersAnalyticsResponse | null) {
  if (!analytics || isNoOrdersResponse(analytics)) {
    return [];
  }

  const rows =
    analytics.role === "seller"
      ? [
          { label: "Daily income", value: analytics.analytics.averageDailyIncome },
          { label: "Avg order", value: analytics.analytics.averageOrderAmount },
        ]
      : analytics.role === "buyer"
        ? [
            { label: "Daily spend", value: analytics.analytics.averageDailySpend },
            { label: "Avg order", value: analytics.analytics.averageOrderAmount },
          ]
        : [
            { label: "Daily income", value: analytics.sellerAnalytics.averageDailyIncome },
            { label: "Daily spend", value: analytics.buyerAnalytics.averageDailySpend },
            { label: "Net profit", value: analytics.netProfit },
          ];

  const maxValue = Math.max(...rows.map(row => row.value), 1);
  return rows.map(row => ({
    ...row,
    width: `${Math.max((row.value / maxValue) * 100, 10)}%`,
  }));
}

function buildStatusSegments(analytics: OrdersAnalyticsResponse | null): ChartDatum[] {
  if (!analytics || isNoOrdersResponse(analytics) || analytics.role === "buyer") {
    return [];
  }

  const source = analytics.role === "seller" ? analytics.analytics : analytics.sellerAnalytics;
  return [
    { label: "Pending", value: source.ordersPending, tone: "amber" },
    { label: "Completed", value: source.ordersCompleted, tone: "blue" },
    { label: "Cancelled", value: source.ordersCancelled, tone: "violet" },
  ];
}

function buildComparisonBars(analytics: OrdersAnalyticsResponse | null): ChartDatum[] {
  if (!analytics || isNoOrdersResponse(analytics)) {
    return [];
  }

  if (analytics.role === "seller") {
    return [
      {
        label: "Daily income",
        value: analytics.analytics.averageDailyIncome,
        tone: "blue",
        detail: formatCurrency(analytics.analytics.averageDailyIncome),
      },
      {
        label: "Avg order",
        value: analytics.analytics.averageOrderAmount,
        tone: "cyan",
        detail: formatCurrency(analytics.analytics.averageOrderAmount),
      },
    ];
  }

  if (analytics.role === "buyer") {
    return [
      {
        label: "Daily spend",
        value: analytics.analytics.averageDailySpend,
        tone: "blue",
        detail: formatCurrency(analytics.analytics.averageDailySpend),
      },
      {
        label: "Avg order",
        value: analytics.analytics.averageOrderAmount,
        tone: "cyan",
        detail: formatCurrency(analytics.analytics.averageOrderAmount),
      },
    ];
  }

  return [
    {
      label: "Income",
      value: analytics.sellerAnalytics.totalIncome,
      tone: "blue",
      detail: formatCurrency(analytics.sellerAnalytics.totalIncome),
    },
    {
      label: "Spend",
      value: analytics.buyerAnalytics.totalSpent,
      tone: "amber",
      detail: formatCurrency(analytics.buyerAnalytics.totalSpent),
    },
    {
      label: "Net Profit",
      value: analytics.netProfit,
      tone: "cyan",
      detail: formatCurrency(analytics.netProfit),
    },
  ];
}

function buildCompositionBars(analytics: OrdersAnalyticsResponse | null): ChartDatum[] {
  if (!analytics || isNoOrdersResponse(analytics)) {
    return [];
  }

  if (analytics.role === "seller") {
    return [
      {
        label: "Items sold",
        value: analytics.analytics.itemsSold,
        tone: "blue",
        detail: formatNumber(analytics.analytics.itemsSold),
      },
      {
        label: "Items per order",
        value: analytics.analytics.averageOrderItemNumber,
        tone: "cyan",
        detail: formatNumber(analytics.analytics.averageOrderItemNumber),
      },
      {
        label: "Item price",
        value: analytics.analytics.averageItemSoldPrice,
        tone: "amber",
        detail: formatCurrency(analytics.analytics.averageItemSoldPrice),
      },
    ];
  }

  if (analytics.role === "buyer") {
    return [
      {
        label: "Items bought",
        value: analytics.analytics.itemsBought,
        tone: "blue",
        detail: formatNumber(analytics.analytics.itemsBought),
      },
      {
        label: "Items per order",
        value: analytics.analytics.averageItemsPerOrder,
        tone: "cyan",
        detail: formatNumber(analytics.analytics.averageItemsPerOrder),
      },
      {
        label: "Item price",
        value: analytics.analytics.averageItemPrice,
        tone: "amber",
        detail: formatCurrency(analytics.analytics.averageItemPrice),
      },
    ];
  }

  return [
    {
      label: "Seller items",
      value: analytics.sellerAnalytics.itemsSold,
      tone: "blue",
      detail: formatNumber(analytics.sellerAnalytics.itemsSold),
    },
    {
      label: "Buyer items",
      value: analytics.buyerAnalytics.itemsBought,
      tone: "cyan",
      detail: formatNumber(analytics.buyerAnalytics.itemsBought),
    },
    {
      label: "Avg order size",
      value: analytics.sellerAnalytics.averageOrderItemNumber,
      tone: "amber",
      detail: formatNumber(analytics.sellerAnalytics.averageOrderItemNumber),
    },
  ];
}

function buildRecentOrderStatusCounts(orders: OrderListResponse | null): ChartDatum[] {
  if (!orders || orders.items.length === 0) {
    return [];
  }

  const counts = new Map<string, number>();
  for (const order of orders.items) {
    const status = order.status.trim() || "Unknown";
    counts.set(status, (counts.get(status) ?? 0) + 1);
  }

  const toneMap: Record<string, ChartTone> = {
    draft: "amber",
    pending: "amber",
    complete: "blue",
    completed: "blue",
    submitted: "cyan",
    cancelled: "violet",
  };

  return [...counts.entries()].map(([label, value]) => ({
    label,
    value,
    tone: toneMap[label.toLowerCase()] ?? "cyan",
    detail: `${value} recent`,
  }));
}

function getToneClass(tone: ChartTone) {
  return `orders-dashboard-tone-${tone}`;
}

function isValidDashboardDateRange(range: { fromDate: string; toDate: string }) {
  if (!range.fromDate || !range.toDate) {
    return false;
  }

  const start = new Date(range.fromDate);
  const end = new Date(range.toDate);

  return !Number.isNaN(start.getTime()) && !Number.isNaN(end.getTime()) && end >= start;
}

function StatusDonut({
  segments,
  total,
}: {
  segments: ChartDatum[];
  total: number;
}) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const visibleSegments = segments.filter(segment => segment.value > 0);
  let offset = 0;

  return (
    <div className="orders-dashboard-donut-wrap">
      <svg
        viewBox="0 0 120 120"
        className="orders-dashboard-donut"
        role="img"
        aria-label="Order status split"
      >
        <circle cx="60" cy="60" r={radius} className="orders-dashboard-donut-track" />
        {visibleSegments.map(segment => {
          const length = total > 0 ? (segment.value / total) * circumference : 0;
          const circle = (
            <circle
              key={segment.label}
              cx="60"
              cy="60"
              r={radius}
              className={`orders-dashboard-donut-segment ${getToneClass(segment.tone)}`}
              strokeDasharray={`${length} ${Math.max(circumference - length, 0)}`}
              strokeDashoffset={-offset}
              transform="rotate(-90 60 60)"
            />
          );
          offset += length;
          return circle;
        })}
      </svg>
      <div className="orders-dashboard-donut-center">
        <strong>{formatNumber(total)}</strong>
        <span>Seller orders</span>
      </div>
    </div>
  );
}

function StatusSplitChart({
  analytics,
}: {
  analytics: OrdersAnalyticsResponse;
}) {
  const segments = buildStatusSegments(analytics);

  if (segments.length === 0) {
    return null;
  }

  return (
    <section className="orders-dashboard-chart orders-dashboard-chart-primary orders-dashboard-chart-feature">
      <div className="orders-dashboard-table-header">
        <div>
          <h2>Order status breakdown</h2>
        </div>
        <Package2 size={20} color="#a7d5ff" />
      </div>
      <div className="orders-dashboard-status-main">
        <div className="orders-dashboard-donut-layout">
          <StatusDonut
            segments={segments}
            total={segments.reduce((sum, segment) => sum + segment.value, 0)}
          />
        </div>
        <div className="orders-dashboard-legend">
          {segments.map(segment => (
            <div key={segment.label} className="orders-dashboard-legend-item">
              <span
                className={`orders-dashboard-legend-dot ${getToneClass(segment.tone)}`}
                aria-hidden="true"
              />
              <div>
                <strong>{segment.label}</strong>
                <span>{formatNumber(segment.value)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function RangeComparisonChart({
  title,
  subtitle,
  rows,
}: {
  title: string;
  subtitle: string;
  rows: ChartDatum[];
}) {
  const maxValue = Math.max(...rows.map(row => row.value), 1);

  return (
    <section className="orders-dashboard-range-comparison">
      <div className="orders-dashboard-status-comparison-header">
        <h3>{title}</h3>
      </div>
      <div className="orders-dashboard-comparison-inline">
        {rows.map(row => (
          <div key={`range-${row.label}`} className="orders-dashboard-comparison-inline-row">
            <header>
              <span>{row.label}</span>
              <strong>{row.detail ?? formatNumber(row.value)}</strong>
            </header>
            <div className="orders-dashboard-composition-track" aria-hidden="true">
              <div
                className={`orders-dashboard-composition-fill ${getToneClass(row.tone)}`}
                style={{ width: `${Math.max((row.value / maxValue) * 100, 14)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function StatusShareChart({ analytics }: { analytics: OrdersAnalyticsResponse }) {
  const segments = buildStatusSegments(analytics);
  const total = segments.reduce((sum, segment) => sum + segment.value, 0);

  if (segments.length === 0) {
    return null;
  }

  return (
    <section className="orders-dashboard-panel orders-dashboard-chart-support orders-dashboard-status-share-panel">
      <div className="orders-dashboard-table-header">
        <div>
          <h2>Status share</h2>
        </div>
      </div>
      <div className="orders-dashboard-status-share-grid">
        {segments.map(segment => {
          const percentage = total > 0 ? (segment.value / total) * 100 : 0;
          return (
            <article key={`${segment.label}-share`} className="orders-dashboard-status-share-card">
              <header>
                <span
                  className={`orders-dashboard-legend-dot ${getToneClass(segment.tone)}`}
                  aria-hidden="true"
                />
                <strong>{segment.label}</strong>
              </header>
              <div className="orders-dashboard-status-share-value">
                {Math.round(percentage)}%
              </div>
              <div className="orders-dashboard-status-share-track" aria-hidden="true">
                <div
                  className={`orders-dashboard-status-share-fill ${getToneClass(segment.tone)}`}
                  style={{ width: `${Math.max(percentage, segment.value > 0 ? 10 : 0)}%` }}
                />
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function ComparisonChart({
  title,
  subtitle,
  rows,
  primary = false,
}: {
  title: string;
  subtitle: string;
  rows: ChartDatum[];
  primary?: boolean;
}) {
  const maxValue = Math.max(...rows.map(row => row.value), 1);

  return (
    <section
      className={`orders-dashboard-chart${primary ? " orders-dashboard-chart-primary" : ""}`}
    >
      <div className="orders-dashboard-table-header">
        <div>
          <h2>{title}</h2>
        </div>
        <TrendingUp size={20} color="#a7d5ff" />
      </div>
      <div className="orders-dashboard-bars">
        {rows.map(row => (
          <article key={row.label} className="orders-dashboard-bar-card">
            <header>
              <span>{row.label}</span>
              <strong>{row.detail ?? formatNumber(row.value)}</strong>
            </header>
            <div className="orders-dashboard-bar-track" aria-hidden="true">
              <div
                className={`orders-dashboard-bar-fill ${getToneClass(row.tone)}`}
                style={{ height: `${Math.max((row.value / maxValue) * 100, 12)}%` }}
              />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function CompositionChart({
  title,
  subtitle,
  rows,
}: {
  title: string;
  subtitle: string;
  rows: ChartDatum[];
}) {
  const maxValue = Math.max(...rows.map(row => row.value), 1);

  return (
    <section className="orders-dashboard-panel orders-dashboard-chart-support">
      <div className="orders-dashboard-table-header">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
      </div>
      <div className="orders-dashboard-composition">
        {rows.map(row => (
          <div key={row.label} className="orders-dashboard-composition-row">
            <header>
              <strong>{row.label}</strong>
              <span>{row.detail ?? formatNumber(row.value)}</span>
            </header>
            <div className="orders-dashboard-composition-track" aria-hidden="true">
              <div
                className={`orders-dashboard-composition-fill ${getToneClass(row.tone)}`}
                style={{ width: `${Math.max((row.value / maxValue) * 100, 14)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function RecentStatusStrip({ orders }: { orders: OrderListResponse }) {
  const segments = buildRecentOrderStatusCounts(orders);
  const total = segments.reduce((sum, segment) => sum + segment.value, 0);

  if (segments.length === 0) {
    return null;
  }

  return (
    <section className="orders-dashboard-status-strip" aria-label="Recent order status mix">
      <div className="orders-dashboard-table-header">
        <div>
          <h3>Recent status mix</h3>
          <p>Latest orders.</p>
        </div>
      </div>
      <div className="orders-dashboard-status-strip-track" aria-hidden="true">
        {segments.map(segment => (
          <span
            key={segment.label}
            className={`orders-dashboard-status-strip-segment ${getToneClass(segment.tone)}`}
            style={{ width: `${(segment.value / total) * 100}%` }}
          />
        ))}
      </div>
      <div className="orders-dashboard-status-strip-legend">
        {segments.map(segment => (
          <div key={segment.label} className="orders-dashboard-status-strip-item">
            <span
              className={`orders-dashboard-legend-dot ${getToneClass(segment.tone)}`}
              aria-hidden="true"
            />
            <span>{segment.label}</span>
            <strong>{formatNumber(segment.value)}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function buildMetricCards(analytics: OrdersAnalyticsResponse | null) {
  if (!analytics || isNoOrdersResponse(analytics)) {
    return [];
  }
  if (analytics.role === "seller") {
    const seller = analytics.analytics;
    return [
      { label: "Average item price", value: formatCurrency(seller.averageItemSoldPrice) },
      { label: "Average order amount", value: formatCurrency(seller.averageOrderAmount) },
      { label: "Items per order", value: formatNumber(seller.averageOrderItemNumber) },
      { label: "Daily orders", value: formatNumber(seller.averageDailyOrders) },
      { label: "Pending orders", value: formatNumber(seller.ordersPending) },
      { label: "Completed orders", value: formatNumber(seller.ordersCompleted) },
    ];
  }
  if (analytics.role === "buyer") {
    const buyer = analytics.analytics;
    return [
      { label: "Average item price", value: formatCurrency(buyer.averageItemPrice) },
      { label: "Average order amount", value: formatCurrency(buyer.averageOrderAmount) },
      { label: "Items per order", value: formatNumber(buyer.averageItemsPerOrder) },
      { label: "Daily orders", value: formatNumber(buyer.averageDailyOrders) },
      { label: "Items bought", value: formatNumber(buyer.itemsBought) },
      { label: "Total spent", value: formatCurrency(buyer.totalSpent) },
    ];
  }
  return [
    { label: "Seller daily income", value: formatCurrency(analytics.sellerAnalytics.averageDailyIncome) },
    { label: "Buyer daily spend", value: formatCurrency(analytics.buyerAnalytics.averageDailySpend) },
    { label: "Seller pending", value: formatNumber(analytics.sellerAnalytics.ordersPending) },
    { label: "Seller completed", value: formatNumber(analytics.sellerAnalytics.ordersCompleted) },
    { label: "Buyer items", value: formatNumber(analytics.buyerAnalytics.itemsBought) },
    { label: "Seller items", value: formatNumber(analytics.sellerAnalytics.itemsSold) },
  ];
}

function RoleDetails({ analytics }: { analytics: OrdersAnalyticsResponse }) {
  if (isNoOrdersResponse(analytics)) {
    return null;
  }

  if (analytics.role === "seller") {
    return (
      <dl className="orders-dashboard-detail-list">
        <div>
          <dt>Most successful day</dt>
          <dd>{formatDateLabel(analytics.analytics.mostSuccessfulDay)}</dd>
        </div>
        <div>
          <dt>Orders on that day</dt>
          <dd>{formatNumber(analytics.analytics.mostSalesMade)}</dd>
        </div>
        <div>
          <dt>Most popular product</dt>
          <dd>
            {analytics.analytics.mostPopularProductName
              ? `${analytics.analytics.mostPopularProductName} (${analytics.analytics.mostPopularProductCode ?? "N/A"})`
              : "No product data"}
          </dd>
        </div>
        <div>
          <dt>Product sales</dt>
          <dd>{formatNumber(analytics.analytics.mostPopularProductSales)}</dd>
        </div>
        <div>
          <dt>Cancelled orders</dt>
          <dd>{formatNumber(analytics.analytics.ordersCancelled)}</dd>
        </div>
      </dl>
    );
  }

  if (analytics.role === "buyer") {
    return (
      <dl className="orders-dashboard-detail-list">
        <div>
          <dt>Total orders</dt>
          <dd>{formatNumber(analytics.analytics.totalOrders)}</dd>
        </div>
        <div>
          <dt>Items bought</dt>
          <dd>{formatNumber(analytics.analytics.itemsBought)}</dd>
        </div>
        <div>
          <dt>Average daily spend</dt>
          <dd>{formatCurrency(analytics.analytics.averageDailySpend)}</dd>
        </div>
        <div>
          <dt>Average daily orders</dt>
          <dd>{formatNumber(analytics.analytics.averageDailyOrders)}</dd>
        </div>
      </dl>
    );
  }

  return (
    <div className="orders-dashboard-role-stack">
      <dl className="orders-dashboard-detail-list">
        <div>
          <dt>Seller favourite product</dt>
          <dd>
            {analytics.sellerAnalytics.mostPopularProductName
              ? `${analytics.sellerAnalytics.mostPopularProductName} (${analytics.sellerAnalytics.mostPopularProductCode ?? "N/A"})`
              : "No product data"}
          </dd>
        </div>
        <div>
          <dt>Seller strongest day</dt>
          <dd>{formatDateLabel(analytics.sellerAnalytics.mostSuccessfulDay)}</dd>
        </div>
      </dl>
      <dl className="orders-dashboard-detail-list">
        <div>
          <dt>Buyer average order</dt>
          <dd>{formatCurrency(analytics.buyerAnalytics.averageOrderAmount)}</dd>
        </div>
        <div>
          <dt>Buyer items per order</dt>
          <dd>{formatNumber(analytics.buyerAnalytics.averageItemsPerOrder)}</dd>
        </div>
      </dl>
    </div>
  );
}

function AnalyticsGroup({
  title,
  analytics,
  kind,
}: {
  title: string;
  analytics: SellerAnalytics | BuyerAnalytics;
  kind: "seller" | "buyer";
}) {
  const metrics =
    kind === "seller"
      ? [
          { label: "Total orders", value: formatNumber(analytics.totalOrders) },
          { label: "Total income", value: formatCurrency((analytics as SellerAnalytics).totalIncome) },
          { label: "Items sold", value: formatNumber((analytics as SellerAnalytics).itemsSold) },
          {
            label: "Average order",
            value: formatCurrency((analytics as SellerAnalytics).averageOrderAmount),
          },
        ]
      : [
          { label: "Total orders", value: formatNumber(analytics.totalOrders) },
          { label: "Total spent", value: formatCurrency((analytics as BuyerAnalytics).totalSpent) },
          { label: "Items bought", value: formatNumber((analytics as BuyerAnalytics).itemsBought) },
          {
            label: "Average order",
            value: formatCurrency((analytics as BuyerAnalytics).averageOrderAmount),
          },
        ];

  return (
    <section className="orders-dashboard-panel">
      <div className="orders-dashboard-table-header">
        <div>
          <h2>{title}</h2>
          <p>{kind === "seller" ? "Outgoing order performance" : "Purchasing activity"}</p>
        </div>
      </div>
      <div className="orders-dashboard-metrics">
        {metrics.map(metric => (
          <article key={`${title}-${metric.label}`} className="orders-dashboard-metric">
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
          </article>
        ))}
      </div>
    </section>
  );
}

function RecentOrdersTable({
  orders,
  loadState,
  errorMessage,
  onRequestDelete,
}: {
  orders: OrderListResponse | null;
  loadState: LoadState;
  errorMessage: string | null;
  onRequestDelete: (order: OrderListItem) => void;
}) {
  if (loadState === "loading") {
    return (
      <section className="orders-dashboard-table" aria-live="polite">
        <div className="orders-dashboard-table-header">
          <h2>Recent orders</h2>
        </div>
      </section>
    );
  }

  if (loadState === "error") {
    return (
      <section className="orders-dashboard-error" role="alert">
        <h2>Recent orders unavailable</h2>
        <p>{errorMessage ?? "Could not load orders."}</p>
      </section>
    );
  }

  if (!orders || orders.items.length === 0) {
    return (
      <section className="orders-dashboard-empty">
        <h2>Recent orders</h2>
        <p>No orders yet.</p>
        <div className="orders-dashboard-range-actions">
          <AppLink href="/orders/create" className="landing-button landing-button-primary">
            Create draft order
          </AppLink>
        </div>
      </section>
    );
  }

  return (
    <section className="orders-dashboard-table">
      <div className="orders-dashboard-table-header">
        <h2>Recent orders</h2>
        <div className="orders-dashboard-table-actions">
          <span className="orders-dashboard-table-meta">Total available: {orders.page.total}</span>
          <AppLink href="/orders/create" className="landing-button landing-button-secondary">
            Create draft order
          </AppLink>
        </div>
      </div>

      <RecentStatusStrip orders={orders} />

      <div className="orders-dashboard-table-wrap">
        <table>
          <thead>
            <tr>
              <th>Order ID</th>
              <th>Status</th>
              <th>Buyer</th>
              <th>Seller</th>
              <th>Issue date</th>
              <th>Updated</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {orders.items.map((order: OrderListItem) => (
              <tr key={order.orderId}>
                <td>{order.orderId}</td>
                <td>
                  <span
                    className="orders-dashboard-status"
                    data-status={order.status.toLowerCase()}
                  >
                    {order.status}
                  </span>
                </td>
                <td>{order.buyerName ?? "Unknown buyer"}</td>
                <td>{order.sellerName ?? "Unknown seller"}</td>
                <td>{order.issueDate ? formatDateLabel(order.issueDate) : "No issue date"}</td>
                <td>{formatDateTimeLabel(order.updatedAt)}</td>
                <td>
                  {order.status === "DRAFT" ? (
                    <div className="orders-dashboard-row-action-group">
                      <AppLink
                        href={`/orders/${encodeURIComponent(order.orderId)}/edit`}
                        className="orders-dashboard-row-action"
                      >
                        Edit
                      </AppLink>
                      <button
                        type="button"
                        className="orders-dashboard-row-action orders-dashboard-row-action-danger"
                        onClick={() => onRequestDelete(order)}
                      >
                        Delete
                      </button>
                    </div>
                  ) : (
                    <AppLink
                      href={`/orders/${encodeURIComponent(order.orderId)}/edit`}
                      className="orders-dashboard-row-action"
                    >
                      View
                    </AppLink>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function OrdersPlaceholderPage() {
  const session = useStoredSession();
  const [dateRange, setDateRange] = useState(() => getDefaultDashboardDateRange());
  const [requestedDateRange, setRequestedDateRange] = useState<{
    fromDate: string;
    toDate: string;
  } | null>(null);
  const [analyticsLoadState, setAnalyticsLoadState] = useState<LoadState>("idle");
  const [ordersLoadState, setOrdersLoadState] = useState<LoadState>("loading");
  const [analytics, setAnalytics] = useState<OrdersAnalyticsResponse | null>(null);
  const [orders, setOrders] = useState<OrderListResponse | null>(null);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);
  const [ordersError, setOrdersError] = useState<string | null>(null);
  const [ordersNotice, setOrdersNotice] = useState<string | null>(getInitialDeletedOrderNotice);
  const [orderPendingDelete, setOrderPendingDelete] = useState<OrderListItem | null>(null);
  const [deletePending, setDeletePending] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const refreshAnalytics = useCallback(async (options?: { silent?: boolean }) => {
    if (!session || !requestedDateRange) {
      return;
    }

    if (!options?.silent) {
      setAnalyticsLoadState("loading");
      setAnalyticsError(null);
    }

    try {
      const response = await fetchOrdersAnalytics(session, requestedDateRange);
      setAnalytics(response);
      setAnalyticsLoadState("ready");
    } catch (error) {
      setAnalyticsLoadState("error");
      setAnalyticsError(
        error instanceof Error && error.message === "analytics:422"
          ? "Please enter a valid date range."
          : "The analytics summary could not be loaded.",
      );
    }
  }, [requestedDateRange, session]);

  const refreshOrders = useCallback(async (options?: { silent?: boolean }) => {
    if (!session) {
      return;
    }

    if (!options?.silent) {
      setOrdersLoadState("loading");
      setOrdersError(null);
    }

    try {
      const response = await fetchRecentOrders(session);
      setOrders(response);
      setOrdersLoadState("ready");
    } catch {
      setOrdersLoadState("error");
      setOrdersError("The recent orders list could not be loaded.");
    }
  }, [session]);

  useEffect(() => {
    if (!requestedDateRange) {
      return;
    }

    void refreshAnalytics();
  }, [refreshAnalytics, requestedDateRange]);

  useEffect(() => {
    if (!session) {
      return;
    }

    void refreshOrders();
  }, [refreshOrders, session]);

  useEffect(() => {
    clearDeletedOrderQueryParam();
  }, []);

  useEffect(() => {
    if (!ordersNotice) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setOrdersNotice(null);
    }, 4000);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [ordersNotice]);

  const summaryTiles = useMemo(() => getSummaryTiles(analytics), [analytics]);
  const metricCards = useMemo(() => buildMetricCards(analytics), [analytics]);
  const comparisonBars = useMemo(() => buildComparisonBars(analytics), [analytics]);
  const compositionBars = useMemo(() => buildCompositionBars(analytics), [analytics]);
  const rangeLabel = useMemo(() => getDateRangeDayCountLabel(dateRange), [dateRange]);

  function handleDateRangeChange(field: "fromDate" | "toDate", value: string) {
    setDateRange(current => ({
      ...current,
      [field]: value ? dateInputValueToIso(value, field === "fromDate" ? "start" : "end") : "",
    }));
    setRequestedDateRange(null);
    setAnalytics(null);
    setAnalyticsLoadState("idle");
    setAnalyticsError(null);
  }

  function handleAnalyticsSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!isValidDashboardDateRange(dateRange)) {
      setRequestedDateRange(null);
      setAnalytics(null);
      setAnalyticsLoadState("idle");
      setAnalyticsError("Please enter a valid date range.");
      return;
    }

    setAnalyticsError(null);
    setRequestedDateRange({ ...dateRange });
  }

  async function handleDeleteOrder() {
    if (!session || !orderPendingDelete) {
      return;
    }

    setDeletePending(true);
    setDeleteError(null);

    try {
      await deleteOrder(session, orderPendingDelete.orderId);
      const deletedOrderId = orderPendingDelete.orderId;
      setOrders(current =>
        current
          ? {
              ...current,
              items: current.items.filter(order => order.orderId !== deletedOrderId),
              page: {
                ...current.page,
                total: Math.max(current.page.total - 1, 0),
              },
            }
          : current,
      );
      setOrdersNotice(`Order ${deletedOrderId} deleted.`);
      setOrderPendingDelete(null);
      void refreshOrders({ silent: true });
      if (requestedDateRange) {
        void refreshAnalytics({ silent: true });
      }
    } catch (error) {
      if (!(error instanceof Error)) {
        setDeleteError("The order could not be deleted.");
        setDeletePending(false);
        return;
      }

      if (error.message.startsWith("order-delete:404:")) {
        setDeleteError("This order no longer exists.");
        setOrderPendingDelete(null);
        setOrdersNotice("This order no longer exists.");
        void refreshOrders({ silent: true });
        if (requestedDateRange) {
          void refreshAnalytics({ silent: true });
        }
      } else if (
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
  }

  return (
    <div className="landing-root orders-dashboard-root">
      <div className="landing-container">
        <section className="landing-stage orders-dashboard-stage">
          <AppHeader />

          <main className="orders-dashboard-main">
            <section className="orders-dashboard-hero">
              <section className="orders-dashboard-summary orders-dashboard-hero-copy">
                <div>
                  <h1>Orders and analytics.</h1>
                </div>
                <div
                  className="orders-dashboard-summary-grid"
                  data-columns={summaryTiles.length === 2 ? "2" : "3"}
                >
                  <div>
                    <span className="orders-dashboard-kicker">{getHeadlineLabel(analytics)}</span>
                    <strong className="orders-dashboard-summary-value">
                      {analyticsLoadState === "loading" ? "Loading..." : getHeadlineValue(analytics)}
                    </strong>
                    {isNoOrdersResponse(analytics) ? (
                      <p className="orders-dashboard-summary-note">
                        Widen the range or create an order.
                      </p>
                    ) : null}
                  </div>
                  {summaryTiles.map(tile => (
                    <div key={tile.label} className="orders-dashboard-summary-tile">
                      <span className="orders-dashboard-kicker">{tile.label}</span>
                      <strong className="orders-dashboard-summary-value">{tile.value}</strong>
                    </div>
                  ))}
                </div>
              </section>

              <aside className="orders-dashboard-panel orders-dashboard-range-panel">
                <div className="orders-dashboard-range-header">
                  <div>
                    <span className="orders-dashboard-kicker">Analytics range</span>
                    <h2>{rangeLabel}</h2>
                  </div>
                  <ChartNoAxesColumn size={20} color="#a7d5ff" />
                </div>
                <form className="orders-dashboard-range-panel-form" onSubmit={handleAnalyticsSearch}>
                  <div className="orders-dashboard-range-form">
                    <label htmlFor="fromDate">
                      From
                      <input
                        id="fromDate"
                        type="date"
                        value={isoToDateInputValue(dateRange.fromDate)}
                        aria-invalid={analyticsError === "Please enter a valid date range."}
                        aria-describedby={
                          analyticsError === "Please enter a valid date range."
                            ? "analytics-range-error"
                            : undefined
                        }
                        onChange={event => handleDateRangeChange("fromDate", event.target.value)}
                      />
                    </label>
                    <label htmlFor="toDate">
                      To
                      <input
                        id="toDate"
                        type="date"
                        value={isoToDateInputValue(dateRange.toDate)}
                        aria-invalid={analyticsError === "Please enter a valid date range."}
                        aria-describedby={
                          analyticsError === "Please enter a valid date range."
                            ? "analytics-range-error"
                            : undefined
                        }
                        onChange={event => handleDateRangeChange("toDate", event.target.value)}
                      />
                    </label>
                  </div>
                  <div className="orders-dashboard-range-actions">
                    <button
                      type="submit"
                      className="landing-button landing-button-secondary"
                    >
                      Search
                    </button>
                    <AppLink href="/orders/create" className="landing-button landing-button-primary">
                      Create draft order
                    </AppLink>
                    <button
                      type="button"
                      className="landing-button landing-button-secondary landing-button-reset"
                      onClick={() => {
                        setDateRange(getDefaultDashboardDateRange());
                        setRequestedDateRange(null);
                        setAnalytics(null);
                        setAnalyticsLoadState("idle");
                        setAnalyticsError(null);
                      }}
                    >
                      Reset range
                    </button>
                  </div>
                  {analyticsError === "Please enter a valid date range." ? (
                    <p
                      id="analytics-range-error"
                      className="orders-dashboard-range-error"
                      role="alert"
                    >
                      {analyticsError}
                    </p>
                  ) : null}
                </form>
                {analyticsLoadState === "ready" &&
                analytics &&
                !isNoOrdersResponse(analytics) &&
                analytics.role !== "buyer" ? (
                  <RangeComparisonChart
                    title={
                      analytics.role === "buyer_and_seller"
                        ? "Income vs Spend"
                        : "Value comparison"
                    }
                    subtitle=""
                    rows={comparisonBars}
                  />
                ) : null}
              </aside>
            </section>

            {analyticsLoadState === "error" ? (
              <section className="orders-dashboard-error" role="alert">
                <h2>Analytics unavailable</h2>
                <p>{analyticsError ?? "Could not load analytics."}</p>
              </section>
            ) : analyticsLoadState === "loading" ? (
              <section className="orders-dashboard-panel">
                <h2>Loading analytics</h2>
                <p>Fetching data.</p>
              </section>
            ) : analyticsLoadState === "idle" ? (
              <section className="orders-dashboard-panel">
                <h2>Analytics ready</h2>
                <p>Choose a range, then search.</p>
              </section>
            ) : analytics && isNoOrdersResponse(analytics) ? (
              <section className="orders-dashboard-empty">
                <h2>No orders in range</h2>
                <p>Widen the range or create a draft order.</p>
                <div className="orders-dashboard-range-actions">
                  <AppLink href="/orders/create" className="landing-button landing-button-primary">
                    Create draft order
                  </AppLink>
                </div>
              </section>
            ) : analytics ? (
              <>
                <section className="orders-dashboard-chart-band">
                  {analytics.role === "buyer" ? (
                    <ComparisonChart
                      title="Buyer value comparison"
                      subtitle=""
                      rows={comparisonBars}
                      primary
                    />
                  ) : (
                    <>
                      <StatusSplitChart analytics={analytics} />
                      <StatusShareChart analytics={analytics} />
                    </>
                  )}
                  <div className="orders-dashboard-chart-stack">
                    <CompositionChart
                      title={
                        analytics.role === "buyer"
                          ? "Purchase composition"
                          : analytics.role === "buyer_and_seller"
                            ? "Order composition"
                            : "Seller composition"
                      }
                      subtitle={
                        analytics.role === "buyer"
                          ? ""
                          : ""
                      }
                      rows={compositionBars}
                    />
                  </div>
                </section>

                <section className="orders-dashboard-grid">
                  <div className="orders-dashboard-left">
                    <div className="orders-dashboard-metrics">
                      {metricCards.map(card => (
                        <article key={card.label} className="orders-dashboard-metric">
                          <span>{card.label}</span>
                          <strong>{card.value}</strong>
                        </article>
                      ))}
                    </div>
                  </div>

                  <div className="orders-dashboard-right">
                    <section className="orders-dashboard-panel">
                      <div className="orders-dashboard-table-header">
                        <div>
                          <h2>Details</h2>
                          <p>
                            {analytics.role === "buyer_and_seller"
                              ? "Buyer + seller."
                              : `${analytics.role} view.`}
                          </p>
                        </div>
                        <Package2 size={20} color="#a7d5ff" />
                      </div>
                      <RoleDetails analytics={analytics} />
                    </section>
                  </div>
                </section>

                {analytics.role === "buyer_and_seller" ? (
                  <section className="orders-dashboard-grid">
                    <AnalyticsGroup
                      title="Seller analytics"
                      analytics={(analytics as CombinedAnalyticsResponse).sellerAnalytics}
                      kind="seller"
                    />
                    <AnalyticsGroup
                      title="Buyer analytics"
                      analytics={(analytics as CombinedAnalyticsResponse).buyerAnalytics}
                      kind="buyer"
                    />
                  </section>
                ) : null}
              </>
            ) : null}

            {ordersNotice ? (
              <section className="orders-dashboard-banner orders-dashboard-banner-success" role="status">
                {ordersNotice}
              </section>
            ) : null}

            <RecentOrdersTable
              orders={orders}
              loadState={ordersLoadState}
              errorMessage={ordersError}
              onRequestDelete={order => {
                setDeleteError(null);
                setOrderPendingDelete(order);
              }}
            />
          </main>
        </section>
      </div>

      <ConfirmDialog
        open={orderPendingDelete !== null}
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
          setOrderPendingDelete(null);
        }}
        onConfirm={() => void handleDeleteOrder()}
      >
        Order ID: {orderPendingDelete?.orderId ?? ""}
      </ConfirmDialog>
    </div>
  );
}
