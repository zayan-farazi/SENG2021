import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { MarketplacePrototypePage } from "./MarketplacePrototypePage";
import { MarketplaceReviewPage } from "./MarketplaceReviewPage";
import {
  clearStoredMarketplaceCart,
  writeStoredMarketplaceCart,
} from "./marketplacePrototypeData";

describe("MarketplacePrototypePage", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
    clearStoredMarketplaceCart();
    window.history.replaceState({}, "", "/");
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
  });

  it("renders stored cart lines on the review page", () => {
    writeStoredMarketplaceCart({
      lines: [
        {
          productId: "market-ceramic-mug",
          name: "Handmade ceramic mug",
          seller: "Harbour Studio",
          unitPrice: 34,
          quantity: 2,
          stock: 9,
          subtotal: 68,
        },
      ],
    });

    render(<MarketplaceReviewPage />);

    expect(screen.getByRole("heading", { name: /review your order/i })).toBeInTheDocument();
    expect(screen.getByText("Handmade ceramic mug")).toBeInTheDocument();
    expect(screen.getAllByText(/\$68/).length).toBeGreaterThan(0);
  });
});
