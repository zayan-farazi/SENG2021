import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  dateInputValueToIso,
  getDateRangeDayCountLabel,
  getDefaultDashboardDateRange,
} from "./ordersDashboard";
import {
  OrdersAnalyticsPage,
  OrdersPage,
} from "./pages/OrdersPlaceholderPage";
import { setStoredSession } from "./session";

function jsonResponse(body: unknown) {
  return {
    ok: true,
    json: async () => body,
  };
}

describe("Orders pages", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/orders");
    window.localStorage.clear();
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-04-05T10:00:00.000Z"));
    setStoredSession({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("loads recent orders on entry for the orders page", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      jsonResponse({
        items: [
          {
            orderId: "ord_123",
            status: "DRAFT",
            createdAt: "2026-04-01T08:00:00Z",
            updatedAt: "2026-04-05T08:00:00Z",
            buyerName: "Buyer Co",
            sellerName: "Seller Co",
            issueDate: "2026-04-01",
          },
          {
            orderId: "ord_999",
            status: "SUBMITTED",
            createdAt: "2026-04-02T08:00:00Z",
            updatedAt: "2026-04-05T09:00:00Z",
            buyerName: "Buyer Co",
            sellerName: "Seller Co",
            issueDate: "2026-04-02",
          },
        ],
        page: {
          limit: 10,
          offset: 0,
          hasMore: false,
          total: 2,
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<OrdersPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /^orders\.$/i })).toBeInTheDocument();
      expect(screen.getByText("ord_123")).toBeInTheDocument();
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/v1/orders?limit=10&offset=0",
      {
        headers: {
          Authorization: "Bearer super-secure-password",
          "X-Party-Email": "buyer@example.com",
        },
      },
    );
    expect(screen.getByRole("link", { name: /^analytics$/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /analytics ready/i })).not.toBeInTheDocument();
  });

  it("opens a delete dialog for draft rows and refreshes orders after deletion", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          items: [
            {
              orderId: "ord_delete123",
              status: "DRAFT",
              createdAt: "2026-04-01T08:00:00Z",
              updatedAt: "2026-04-05T08:00:00Z",
              buyerName: "Buyer Co",
              sellerName: "Seller Co",
              issueDate: "2026-04-01",
            },
            {
              orderId: "ord_keep999",
              status: "SUBMITTED",
              createdAt: "2026-04-02T08:00:00Z",
              updatedAt: "2026-04-05T09:00:00Z",
              buyerName: "Buyer Co",
              sellerName: "Seller Co",
              issueDate: "2026-04-02",
            },
          ],
          page: {
            limit: 10,
            offset: 0,
            hasMore: false,
            total: 2,
          },
        }),
      )
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce(
        jsonResponse({
          items: [
            {
              orderId: "ord_keep999",
              status: "SUBMITTED",
              createdAt: "2026-04-02T08:00:00Z",
              updatedAt: "2026-04-05T09:00:00Z",
              buyerName: "Buyer Co",
              sellerName: "Seller Co",
              issueDate: "2026-04-02",
            },
          ],
          page: {
            limit: 10,
            offset: 0,
            hasMore: false,
            total: 1,
          },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<OrdersPage />);

    await waitFor(() => {
      expect(screen.getByText("ord_delete123")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /delete/i }));

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent(/delete order\?/i);
    expect(screen.getByText(/order id: ord_delete123/i)).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: /^delete order$/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenNthCalledWith(
        2,
        "http://localhost:8000/v1/order/ord_delete123",
        {
          method: "DELETE",
          headers: {
            Authorization: "Bearer super-secure-password",
            "X-Party-Email": "buyer@example.com",
          },
        },
      );
      expect(screen.queryByText("ord_delete123")).not.toBeInTheDocument();
      expect(screen.getByRole("status")).toHaveTextContent(/order ord_delete123 deleted\./i);
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(3);
      expect(screen.getByText("ord_keep999")).toBeInTheDocument();
    });
  });

  it("closes the delete dialog on escape", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        jsonResponse({
          items: [
            {
              orderId: "ord_delete123",
              status: "DRAFT",
              createdAt: "2026-04-01T08:00:00Z",
              updatedAt: "2026-04-05T08:00:00Z",
              buyerName: "Buyer Co",
              sellerName: "Seller Co",
              issueDate: "2026-04-01",
            },
          ],
          page: {
            limit: 10,
            offset: 0,
            hasMore: false,
            total: 1,
          },
        }),
      ),
    );

    render(<OrdersPage />);

    await waitFor(() => {
      expect(screen.getByText("ord_delete123")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /delete/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });
});

describe("Orders analytics page", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/orders/analytics");
    window.localStorage.clear();
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-04-05T10:00:00.000Z"));
    setStoredSession({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("loads analytics after search with the default range", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      jsonResponse({
        role: "seller",
        analytics: {
          totalOrders: 4,
          totalIncome: 148.5,
          itemsSold: 21,
          averageItemSoldPrice: 7.07,
          averageOrderAmount: 37.13,
          averageOrderItemNumber: 5.25,
          averageDailyIncome: 4.95,
          averageDailyOrders: 0.13,
          ordersPending: 1,
          ordersCompleted: 2,
          ordersCancelled: 1,
          mostSuccessfulDay: "2026-04-03",
          mostSalesMade: 2,
          mostPopularProductCode: "EA",
          mostPopularProductName: "Oranges",
          mostPopularProductSales: 8,
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<OrdersAnalyticsPage />);

    const expectedRange = getDefaultDashboardDateRange(new Date("2026-04-05T10:00:00.000Z"));

    expect(screen.getByRole("heading", { name: /^analytics\.$/i })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: getDateRangeDayCountLabel(expectedRange) }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /analytics ready/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /search/i }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /order status breakdown/i })).toBeInTheDocument();
      expect(screen.getByText("$148.50")).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: /value comparison/i })).toBeInTheDocument();
      expect(screen.queryByRole("heading", { name: /recent orders/i })).not.toBeInTheDocument();
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `http://localhost:8000/v1/analytics/orders?fromDate=${encodeURIComponent(expectedRange.fromDate)}&toDate=${encodeURIComponent(expectedRange.toDate)}`,
      {
        headers: {
          Authorization: "Bearer super-secure-password",
          "X-Party-Email": "buyer@example.com",
        },
      },
    );
  });

  it("renders combined buyer and seller analytics", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        jsonResponse({
          role: "buyer_and_seller",
          sellerAnalytics: {
            totalOrders: 4,
            totalIncome: 300,
            itemsSold: 30,
            averageItemSoldPrice: 10,
            averageOrderAmount: 75,
            averageOrderItemNumber: 7.5,
            averageDailyIncome: 10,
            averageDailyOrders: 0.13,
            ordersPending: 1,
            ordersCompleted: 3,
            ordersCancelled: 0,
            mostSuccessfulDay: "2026-04-01",
            mostSalesMade: 2,
            mostPopularProductCode: "EA",
            mostPopularProductName: "Apples",
            mostPopularProductSales: 12,
          },
          buyerAnalytics: {
            totalOrders: 3,
            totalSpent: 120,
            itemsBought: 9,
            averageItemPrice: 13.33,
            averageOrderAmount: 40,
            averageItemsPerOrder: 3,
            averageDailySpend: 4,
            averageDailyOrders: 0.1,
          },
          netProfit: 180,
        }),
      ),
    );

    render(<OrdersAnalyticsPage />);

    fireEvent.click(screen.getByRole("button", { name: /search/i }));

    await waitFor(() => {
      expect(screen.getAllByText("$180.00").length).toBeGreaterThan(0);
      expect(screen.getByRole("heading", { name: /order status breakdown/i })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: /income vs spend/i })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: /seller analytics/i })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: /buyer analytics/i })).toBeInTheDocument();
    });
  });

  it("renders buyer-specific charts without the seller status donut", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        jsonResponse({
          role: "buyer",
          analytics: {
            totalOrders: 3,
            totalSpent: 90,
            itemsBought: 12,
            averageItemPrice: 7.5,
            averageOrderAmount: 30,
            averageItemsPerOrder: 4,
            averageDailySpend: 3,
            averageDailyOrders: 0.1,
          },
        }),
      ),
    );

    render(<OrdersAnalyticsPage />);

    fireEvent.click(screen.getByRole("button", { name: /search/i }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /buyer value comparison/i })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: /purchase composition/i })).toBeInTheDocument();
      expect(
        screen.queryByRole("heading", { name: /order status breakdown/i }),
      ).not.toBeInTheDocument();
    });
  });

  it("shows an inline error when analytics cannot be loaded", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 500,
      }),
    );

    render(<OrdersAnalyticsPage />);

    fireEvent.click(screen.getByRole("button", { name: /search/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/analytics unavailable/i);
      expect(
        screen.queryByRole("heading", { name: /recent orders/i }),
      ).not.toBeInTheDocument();
    });
  });

  it("keeps the empty state free of chart panels when analytics returns no orders", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(jsonResponse({ message: "No orders found" })));

    render(<OrdersAnalyticsPage />);

    fireEvent.click(screen.getByRole("button", { name: /search/i }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /no orders in range/i })).toBeInTheDocument();
      expect(
        screen.queryByRole("heading", { name: /order status breakdown/i }),
      ).not.toBeInTheDocument();
      expect(screen.queryByRole("heading", { name: /value comparison/i })).not.toBeInTheDocument();
    });
  });

  it("waits for search before loading analytics and validates the entered range", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          role: "buyer",
          analytics: {
            totalOrders: 1,
            totalSpent: 20,
            itemsBought: 2,
            averageItemPrice: 10,
            averageOrderAmount: 20,
            averageItemsPerOrder: 2,
            averageDailySpend: 0.67,
            averageDailyOrders: 0.03,
          },
        }),
      )
      .mockResolvedValue(
        jsonResponse({
          role: "buyer",
          analytics: {
            totalOrders: 2,
            totalSpent: 80,
            itemsBought: 6,
            averageItemPrice: 13.33,
            averageOrderAmount: 40,
            averageItemsPerOrder: 3,
            averageDailySpend: 4,
            averageDailyOrders: 0.1,
          },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<OrdersAnalyticsPage />);

    expect(fetchMock).toHaveBeenCalledTimes(0);

    fireEvent.change(screen.getByLabelText(/from/i), {
      target: { value: "2026-03-15" },
    });
    fireEvent.change(screen.getByLabelText(/to/i), {
      target: { value: "2026-04-01" },
    });

    expect(fetchMock).toHaveBeenCalledTimes(0);
    expect(
      screen.getByRole("heading", {
        name: getDateRangeDayCountLabel({
          fromDate: dateInputValueToIso("2026-03-15", "start"),
          toDate: dateInputValueToIso("2026-04-01", "end"),
        }),
      }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /search/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `http://localhost:8000/v1/analytics/orders?fromDate=${encodeURIComponent(dateInputValueToIso("2026-03-15", "start"))}&toDate=${encodeURIComponent(dateInputValueToIso("2026-04-01", "end"))}`,
      {
        headers: {
          Authorization: "Bearer super-secure-password",
          "X-Party-Email": "buyer@example.com",
        },
      },
    );

    fireEvent.change(screen.getByLabelText(/from/i), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByRole("button", { name: /search/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/please enter a valid date range\./i);
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
