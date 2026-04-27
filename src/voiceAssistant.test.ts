import { describe, expect, it } from "vitest";
import { marketplaceCategories, marketplaceProducts } from "./pages/marketplacePrototypeData";
import {
  parseCheckoutVoiceCommand,
  parseInventoryVoiceCommand,
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

  it("parses marketplace checkout navigation commands", () => {
    const command = parseMarketplaceVoiceCommand(
      "go to checkout",
      marketplaceProducts,
      marketplaceCategories,
    );

    expect(command).toEqual({
      kind: "go_to_checkout",
    });
  });

  it("parses inventory create commands", () => {
    const command = parseInventoryVoiceCommand(
      "create a product called linen tote priced at 31 with 8 in stock in Fashion",
      [
        { id: "1", name: "Ceramic mug" },
        { id: "2", name: "Weekend tote bag" },
      ],
      ["Fashion", "Handcrafted", "Others"],
    );

    expect(command).toEqual({
      kind: "create_product",
      name: "linen tote",
      price: 31,
      stock: 8,
      category: "Fashion",
      unitCode: "EA",
      isVisible: true,
    });
  });

  it("parses inventory delete commands", () => {
    const command = parseInventoryVoiceCommand(
      "delete ceramic mug",
      [
        { id: "1", name: "Ceramic mug" },
        { id: "2", name: "Weekend tote bag" },
      ],
      ["Fashion", "Handcrafted", "Others"],
    );

    expect(command).toEqual({
      kind: "delete_product",
      productId: "1",
      productName: "Ceramic mug",
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
    expect(parseLockedOrderVoiceCommand("download it as a pdf")).toEqual({
      kind: "download_invoice_pdf",
    });
    expect(parseLockedOrderVoiceCommand("download as a pdf")).toEqual({
      kind: "download_invoice_pdf",
    });
    expect(parseLockedOrderVoiceCommand("copy the invoice xml")).toEqual({
      kind: "copy_invoice_xml",
    });
    expect(parseLockedOrderVoiceCommand("remove that invoice")).toEqual({
      kind: "delete_invoice",
    });
    expect(parseLockedOrderVoiceCommand("delete the invoice")).toEqual({
      kind: "delete_invoice",
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

  it("parses forgiving checkout placement phrases", () => {
    expect(parseCheckoutVoiceCommand("place the order")).toEqual({
      kind: "submit_checkout",
    });
    expect(parseCheckoutVoiceCommand("great can you please the order for me")).toEqual({
      kind: "submit_checkout",
    });
    expect(parseCheckoutVoiceCommand("submit it")).toEqual({
      kind: "submit_checkout",
    });
  });

  it("parses checkout draft-saving phrases", () => {
    expect(parseCheckoutVoiceCommand("save as draft")).toEqual({
      kind: "save_checkout_draft",
    });
    expect(parseCheckoutVoiceCommand("save this order as draft")).toEqual({
      kind: "save_checkout_draft",
    });
    expect(parseCheckoutVoiceCommand("make this a draft")).toEqual({
      kind: "save_checkout_draft",
    });
  });
});
