import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { InventoryPrototypePage } from "./InventoryPrototypePage";

describe("InventoryPrototypePage", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
  });

  it("renders launched and draft listing sections", () => {
    render(<InventoryPrototypePage />);

    expect(screen.getByRole("heading", { name: /^inventory$/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^launched$/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^draft listings$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^add product$/i })).toBeInTheDocument();
  });

  it("opens the shared editor in add mode", async () => {
    const user = userEvent.setup();

    render(<InventoryPrototypePage />);
    await user.click(screen.getByRole("button", { name: /^add product$/i }));

    expect(screen.getByRole("heading", { name: /^add product$/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/product name/i)).toHaveValue("");
  });

  it("opens the shared editor in edit mode from a product card", async () => {
    const user = userEvent.setup();

    render(<InventoryPrototypePage />);
    await user.click(screen.getByRole("button", { name: /edit ceramic mug/i }));

    expect(screen.getByRole("heading", { name: /^edit product$/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/product name/i)).toHaveValue("Ceramic mug");
  });

  it("filters cards from the search input", async () => {
    const user = userEvent.setup();

    render(<InventoryPrototypePage />);
    await user.type(screen.getByRole("searchbox", { name: /search products/i }), "mug");

    expect(screen.getByText("Ceramic mug")).toBeInTheDocument();
    expect(screen.queryByText("Vintage denim jacket")).not.toBeInTheDocument();
  });
});
