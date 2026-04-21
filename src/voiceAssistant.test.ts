import { describe, expect, it } from "vitest";
import { marketplaceCategories, marketplaceProducts } from "./pages/marketplacePrototypeData";
import {
  parseLockedOrderVoiceCommand,
  parseMarketplaceVoiceCommand,
  summarizeCheckoutFieldMutations,
} from "./voiceAssistant";

describe("voiceAssistant helpers", () => {
  it("parses marketplace add-item commands", () => {
    const command = parseMarketplaceVoiceCommand(
      "add two ceramic mugs",
      marketplaceProducts,
      marketplaceCategories,
    );

    expect(command).toEqual({
      kind: "change_quantity",
      productId: "market-ceramic-mug",
      productName: "Handmade ceramic mug",
      quantityDelta: 2,
    });
  });

  it("parses marketplace category commands", () => {
    const command = parseMarketplaceVoiceCommand(
      "show fashion only",
      marketplaceProducts,
      marketplaceCategories,
    );

    expect(command).toEqual({
      kind: "set_category",
      category: "Fashion",
    });
  });

  it("parses locked-order risky commands", () => {
    expect(parseLockedOrderVoiceCommand("generate invoice")).toEqual({
      kind: "generate_invoice",
    });
    expect(parseLockedOrderVoiceCommand("mark invoice paid")).toEqual({
      kind: "set_invoice_status",
      status: "paid",
    });
  });

  it("summarizes checkout field changes", () => {
    const summary = summarizeCheckoutFieldMutations(
      {
        buyerName: "Buyer Co",
        street: "",
        city: "",
        state: "",
        postcode: "",
        country: "AU",
        requestedDate: "",
        notes: "",
      },
      {
        buyerName: "Buyer Co",
        street: "123 Harbour Street",
        city: "Sydney",
        state: "NSW",
        postcode: "2000",
        country: "AU",
        requestedDate: "2026-05-03",
        notes: "Leave at loading dock",
      },
    );

    expect(summary).toEqual([
      "Updated delivery street to 123 Harbour Street.",
      "Updated delivery city to Sydney.",
      "Updated delivery state to NSW.",
      "Updated delivery postcode to 2000.",
      "Updated requested date to 2026-05-03.",
      "Updated notes to Leave at loading dock.",
    ]);
  });
});
