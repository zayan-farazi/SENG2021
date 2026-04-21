import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { setStoredSession } from "../session";
import { MarketplacePrototypePage } from "./MarketplacePrototypePage";
import { MarketplaceCheckoutSuccessPage } from "./MarketplaceCheckoutSuccessPage";
import { MarketplaceReviewPage } from "./MarketplaceReviewPage";
import {
  clearStoredMarketplaceCart,
  clearStoredMarketplaceCheckoutSuccess,
  writeStoredMarketplaceCheckoutSuccess,
  writeStoredMarketplaceCart,
} from "./marketplacePrototypeData";

describe("MarketplacePrototypePage", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
    clearStoredMarketplaceCart();
    clearStoredMarketplaceCheckoutSuccess();
    window.history.replaceState({}, "", "/");
    vi.unstubAllGlobals();
  });

  it("renders search, filters, products, and cart summary", () => {
    render(<MarketplacePrototypePage />);

    expect(screen.getByRole("heading", { name: /^marketplace$/i })).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: /search products or sellers/i })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /filter by category/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /cart summary/i })).toBeInTheDocument();
    expect(screen.getByText("Handmade ceramic mug")).toBeInTheDocument();
  });

  it("updates the cart when quantities change", async () => {
    const user = userEvent.setup();

    render(<MarketplacePrototypePage />);
    await user.click(screen.getByRole("button", { name: /increase handmade ceramic mug/i }));

    expect(screen.getByText(/1 items/i)).toBeInTheDocument();
    const cart = screen.getByRole("heading", { name: /cart summary/i }).closest("aside");
    expect(cart).not.toBeNull();
    expect(within(cart as HTMLElement).getByText("Handmade ceramic mug")).toBeInTheDocument();
    expect(within(cart as HTMLElement).getByText("$34")).toBeInTheDocument();
  });

  it("caps incrementing at the available stock count", async () => {
    const user = userEvent.setup();

    render(<MarketplacePrototypePage />);
    const increaseButton = screen.getByRole("button", { name: /increase vintage denim jacket/i });

    await user.click(increaseButton);
    await user.click(increaseButton);
    await user.click(increaseButton);

    expect(increaseButton).toBeDisabled();
    expect(screen.getByText(/3 items/i)).toBeInTheDocument();
  });

  it("shows a no-results state when filters remove every listing", async () => {
    const user = userEvent.setup();

    render(<MarketplacePrototypePage />);
    await user.type(screen.getByRole("searchbox", { name: /search products or sellers/i }), "zzzz");

    expect(screen.getByText(/no listings match these filters/i)).toBeInTheDocument();
    expect(screen.queryByText("Handmade ceramic mug")).not.toBeInTheDocument();
  });

  it("navigates to the review route when the cart has items", async () => {
    const user = userEvent.setup();

    render(<MarketplacePrototypePage />);
    await user.click(screen.getByRole("button", { name: /increase handmade ceramic mug/i }));
    await user.click(screen.getByRole("button", { name: /review order/i }));

    expect(window.location.pathname).toBe("/marketplace/review");
  });
});

describe("MarketplaceReviewPage", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
    clearStoredMarketplaceCart();
    clearStoredMarketplaceCheckoutSuccess();
    vi.unstubAllGlobals();
  });

  it("renders stored cart lines on the review page", () => {
    setStoredSession({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });
    writeStoredMarketplaceCart({
      lines: [
        {
          productId: "market-ceramic-mug",
          name: "Handmade ceramic mug",
          seller: "Harbour Studio",
          sellerEmail: "orders@harbourstudio.example",
          unitPrice: 34,
          quantity: 2,
          stock: 9,
          unitCode: "EA",
          subtotal: 68,
        },
      ],
    });

    render(<MarketplaceReviewPage />);

    expect(screen.getByRole("heading", { name: /review your order/i })).toBeInTheDocument();
    expect(screen.getByText("Handmade ceramic mug")).toBeInTheDocument();
    expect(screen.getAllByText(/\$68/).length).toBeGreaterThan(0);
    expect(screen.getByDisplayValue("buyer@example.com")).toBeInTheDocument();
  });

  it("groups cart lines by seller and submits each order before navigating to success", async () => {
    const user = userEvent.setup();
    setStoredSession({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });
    writeStoredMarketplaceCart({
      lines: [
        {
          productId: "market-ceramic-mug",
          name: "Handmade ceramic mug",
          seller: "Harbour Studio",
          sellerEmail: "orders@harbourstudio.example",
          unitPrice: 34,
          quantity: 2,
          stock: 9,
          unitCode: "EA",
          subtotal: 68,
        },
        {
          productId: "market-art-print",
          name: "Abstract wall print",
          seller: "Lineform Press",
          sellerEmail: "studio@lineformpress.example",
          unitPrice: 46,
          quantity: 1,
          stock: 14,
          unitCode: "EA",
          subtotal: 46,
        },
      ],
    });
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ orderId: "ord_1", status: "DRAFT", createdAt: "2026-04-21T00:00:00Z" }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ orderId: "ord_1", status: "SUBMITTED", updatedAt: "2026-04-21T00:01:00Z" }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ orderId: "ord_2", status: "DRAFT", createdAt: "2026-04-21T00:00:00Z" }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ orderId: "ord_2", status: "SUBMITTED", updatedAt: "2026-04-21T00:01:00Z" }),
        }),
    );

    render(<MarketplaceReviewPage />);

    await user.type(screen.getByLabelText(/street/i), "123 Harbour Street");
    await user.type(screen.getByLabelText(/^city$/i), "Sydney");
    await user.type(screen.getByLabelText(/^state$/i), "NSW");
    await user.type(screen.getByLabelText(/postcode/i), "2000");
    await user.clear(screen.getByLabelText(/country/i));
    await user.type(screen.getByLabelText(/country/i), "AU");
    await user.click(screen.getByRole("button", { name: /place orders/i }));

    await waitFor(() => {
      expect(window.location.pathname).toBe("/marketplace/success");
    });
    expect(window.sessionStorage.getItem("lockedout.marketplace-cart")).toBeNull();
    expect(screen.getByText("Harbour Studio")).toBeInTheDocument();
    expect(screen.getByText("Lineform Press")).toBeInTheDocument();
  });

  it("renders the placed-order summary page from stored checkout data", () => {
    writeStoredMarketplaceCheckoutSuccess({
      buyerName: "Buyer Co",
      orders: [
        {
          orderId: "ord_created_1",
          seller: "Harbour Studio",
          sellerEmail: "orders@harbourstudio.example",
          itemCount: 2,
          total: 68,
        },
      ],
    });

    render(<MarketplaceCheckoutSuccessPage />);

    expect(screen.getByRole("heading", { name: /checkout complete/i })).toBeInTheDocument();
    expect(screen.getByText("Harbour Studio")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open first order/i })).toHaveAttribute(
      "href",
      "/orders/ord_created_1/edit",
    );
  });
});
