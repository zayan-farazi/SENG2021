import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { InventoryPrototypePage } from "./InventoryPrototypePage";
import { setStoredSession } from "../session";

function inventoryResponse() {
  return {
    items: [
      {
        prod_id: 1,
        party_id: "seller@example.com",
        name: "Ceramic mug",
        price: 34,
        unit: "EA",
        description: "Handmade mug",
        category: "Handcrafted",
        release_date: "2026-04-08T00:00:00Z",
        available_units: 40,
        is_visible: true,
        show_soldout: true,
        image_url: "https://example.com/mug.png",
      },
      {
        prod_id: 2,
        party_id: "seller@example.com",
        name: "Vintage denim jacket",
        price: 62,
        unit: "EA",
        description: "Vintage denim",
        category: "Fashion",
        release_date: "2026-04-14T00:00:00Z",
        available_units: 12,
        is_visible: true,
        show_soldout: true,
        image_url: "https://example.com/jacket.png",
      },
      {
        prod_id: 3,
        party_id: "seller@example.com",
        name: "Abstract wall print",
        price: 46,
        unit: "EA",
        description: "Print",
        category: "Arts & Crafts",
        release_date: "2099-04-22T00:00:00Z",
        available_units: 40,
        is_visible: false,
        show_soldout: true,
        image_url: "https://example.com/print.png",
      },
    ],
    page: {
      limit: 100,
      offset: 0,
      hasMore: false,
      total: 3,
    },
  };
}

describe("InventoryPrototypePage", () => {
  beforeEach(() => {
    setStoredSession({
      partyId: "seller@example.com",
      partyName: "Seller Co",
      contactEmail: "seller@example.com",
      credential: "super-secure-password",
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => inventoryResponse(),
      }),
    );
  });

  afterEach(() => {
    cleanup();
    window.localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("renders launched and draft listing sections", async () => {
    render(<InventoryPrototypePage />);

    expect(await screen.findByRole("heading", { name: /^inventory$/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^launched$/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^draft listings$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^add product$/i })).toBeInTheDocument();
  });

  it("opens the shared editor in add mode", async () => {
    const user = userEvent.setup();

    render(<InventoryPrototypePage />);
    await screen.findByText("Ceramic mug");
    await user.click(screen.getByRole("button", { name: /^add product$/i }));

    expect(screen.getByRole("heading", { name: /^add product$/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/product name/i)).toHaveValue("");
  });

  it("opens the shared editor in edit mode from a product card", async () => {
    const user = userEvent.setup();

    render(<InventoryPrototypePage />);
    await screen.findByText("Ceramic mug");
    await user.click(screen.getByRole("button", { name: /edit ceramic mug/i }));

    expect(screen.getByRole("heading", { name: /^edit product$/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/product name/i)).toHaveValue("Ceramic mug");
  });

  it("filters cards from the search input", async () => {
    const user = userEvent.setup();

    render(<InventoryPrototypePage />);
    await screen.findByText("Ceramic mug");
    await user.type(screen.getByRole("searchbox", { name: /search products/i }), "mug");

    expect(screen.getByText("Ceramic mug")).toBeInTheDocument();
    expect(screen.queryByText("Vintage denim jacket")).not.toBeInTheDocument();
  });
});
