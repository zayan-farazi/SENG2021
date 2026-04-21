import type { MarketplaceProduct } from "./pages/marketplacePrototypeData";
import type { OrderRequestPayload } from "./voiceOrder";

export type AssistantContext = "marketplace" | "checkout" | "locked_order" | "inventory";

export type AssistantActionResult =
  | {
      kind: "applied";
      message: string;
    }
  | {
      kind: "rejected";
      message: string;
    }
  | {
      kind: "confirm";
      message: string;
      confirmLabel?: string;
      execute: () => Promise<AssistantActionResult>;
    };

export type MarketplaceVoiceCommand =
  | { kind: "search"; query: string }
  | { kind: "clear_search" }
  | { kind: "set_category"; category: string }
  | { kind: "set_in_stock"; value: boolean }
  | { kind: "go_to_checkout" }
  | { kind: "change_quantity"; productId: string; quantityDelta: number; productName: string }
  | { kind: "remove_product"; productId: string; productName: string };

export type InventoryVoiceCommand =
  | { kind: "search"; query: string }
  | { kind: "clear_search" }
  | { kind: "set_in_stock"; value: boolean }
  | {
      kind: "create_product";
      name: string;
      price: number;
      stock: number;
      category: string;
      unitCode: string;
      isVisible: boolean;
    }
  | { kind: "delete_product"; productId: string; productName: string };

export type LockedOrderVoiceCommand =
  | { kind: "fetch_despatch" }
  | { kind: "generate_despatch" }
  | { kind: "generate_invoice" }
  | { kind: "refresh_invoice" }
  | { kind: "fetch_invoice_xml" }
  | { kind: "download_invoice_pdf" }
  | { kind: "set_invoice_status"; status: string; paymentDate?: string | null }
  | { kind: "delete_invoice" };

export type CheckoutVoiceCommand = { kind: "submit_checkout" };

const STOP_WORDS = new Set([
  "add",
  "remove",
  "delete",
  "increase",
  "decrease",
  "show",
  "only",
  "search",
  "find",
  "for",
  "please",
  "the",
  "a",
  "an",
  "to",
  "my",
  "cart",
  "in",
  "stock",
  "item",
  "items",
  "inventory",
]);

const NUMBER_WORDS: Record<string, number> = {
  one: 1,
  two: 2,
  three: 3,
  four: 4,
  five: 5,
  six: 6,
  seven: 7,
  eight: 8,
  nine: 9,
  ten: 10,
  couple: 2,
};

const DEFAULT_INVENTORY_CATEGORY = "Others";
const DEFAULT_INVENTORY_UNIT_CODE = "EA";

function normalizeToken(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9\s$\.]/g, " ")
    .trim()
    .replace(
      /\b(mugs|bags|candles|jackets|prints|boxes|products|listings)\b/g,
      match => match.slice(0, -1),
    )
    .replace(/\s+/g, " ");
}

function tokenize(value: string): string[] {
  return normalizeToken(value)
    .split(" ")
    .filter(token => token && !STOP_WORDS.has(token));
}

function extractQuantity(transcript: string): number {
  const normalized = normalizeToken(transcript);
  const numberMatch = normalized.match(/\b(\d+)\b/);
  if (numberMatch) {
    return Math.max(1, Number.parseInt(numberMatch[1]!, 10));
  }

  const wordMatch = normalized
    .split(" ")
    .find(token => Object.prototype.hasOwnProperty.call(NUMBER_WORDS, token));
  if (wordMatch) {
    return NUMBER_WORDS[wordMatch]!;
  }

  return 1;
}

function findBestMatchingNamedItem<T extends { name: string }>(
  transcript: string,
  items: T[],
): T | null {
  const transcriptTokens = tokenize(transcript);
  if (transcriptTokens.length === 0) {
    return null;
  }

  const scored = items
    .map(item => {
      const itemTokens = tokenize(item.name);
      const score = itemTokens.reduce((count, token) => {
        return transcriptTokens.some(
          transcriptToken =>
            transcriptToken.startsWith(token) || token.startsWith(transcriptToken),
        )
          ? count + 1
          : count;
      }, 0);
      return { item, score, tokenCount: itemTokens.length };
    })
    .filter(candidate => candidate.score > 0)
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score;
      }
      return left.tokenCount - right.tokenCount;
    });

  if (scored.length === 0) {
    return null;
  }

  const best = scored[0]!;
  const second = scored[1];
  if (second && second.score === best.score) {
    return null;
  }

  return best.score >= 2 || best.tokenCount === 1 ? best.item : null;
}

function findBestMatchingProduct(
  transcript: string,
  products: MarketplaceProduct[],
): MarketplaceProduct | null {
  return findBestMatchingNamedItem(transcript, products);
}

function parseInventoryCategory(transcript: string, categories: string[]): string {
  const normalized = normalizeToken(transcript);
  const matched = categories.find(category => normalized.includes(normalizeToken(category)));
  return matched ?? DEFAULT_INVENTORY_CATEGORY;
}

function parseInventoryUnitCode(transcript: string): string {
  const normalized = normalizeToken(transcript);
  const unitMatch = normalized.match(/unit(?: code)?\s+([a-z]{1,4})\b/);
  return unitMatch?.[1]?.toUpperCase() || DEFAULT_INVENTORY_UNIT_CODE;
}

function parseInventoryName(transcript: string): string | null {
  const normalized = normalizeToken(transcript);
  const namedMatch = normalized.match(
    /(?:called|named)\s+(.+?)(?=\s+(?:priced?|price|for|with|category|in)\b|$)/,
  );
  if (namedMatch?.[1]) {
    return namedMatch[1]!.trim();
  }

  const createMatch = normalized.match(
    /(?:create|add|list)\s+(?:a\s+|an\s+|new\s+)?(?:product|item|listing)?\s*(.+?)(?=\s+(?:priced?|price|for|with|category|in)\b|$)/,
  );
  const candidate = createMatch?.[1]?.trim();
  if (!candidate || ["product", "item", "listing"].includes(candidate)) {
    return null;
  }

  return candidate;
}

function parseInventoryPrice(transcript: string): number | null {
  const normalized = normalizeToken(transcript);
  const priceMatch =
    normalized.match(/(?:priced? at|price|for)\s+\$?(\d+(?:\.\d+)?)/) ??
    normalized.match(/\$(\d+(?:\.\d+)?)/);
  if (!priceMatch?.[1]) {
    return null;
  }

  return Number.parseFloat(priceMatch[1]!);
}

function parseInventoryStock(transcript: string): number | null {
  const normalized = normalizeToken(transcript);
  const stockMatch = normalized.match(
    /(?:with|and)\s+(\d+)\s+(?:in stock|available|units?|items?)\b/,
  );
  if (!stockMatch?.[1]) {
    return null;
  }

  return Number.parseInt(stockMatch[1]!, 10);
}

export function parseMarketplaceVoiceCommand(
  transcript: string,
  products: MarketplaceProduct[],
  categories: string[],
): MarketplaceVoiceCommand | null {
  const normalized = normalizeToken(transcript);

  if (!normalized) {
    return null;
  }

  if (normalized.includes("clear search")) {
    return { kind: "clear_search" };
  }

  if (
    normalized.includes("in stock only") ||
    normalized.includes("only in stock") ||
    normalized.includes("hide out of stock")
  ) {
    return { kind: "set_in_stock", value: true };
  }

  if (
    normalized.includes("show out of stock") ||
    normalized.includes("include out of stock") ||
    normalized.includes("all stock")
  ) {
    return { kind: "set_in_stock", value: false };
  }

  const category = categories.find(
    candidate =>
      candidate !== "All" &&
      normalized.includes(normalizeToken(candidate)) &&
      (normalized.startsWith("show") ||
        normalized.startsWith("filter") ||
        normalized.includes("only")),
  );
  if (category) {
    return { kind: "set_category", category };
  }

  if (normalized.includes("show all") || normalized.includes("all categories")) {
    return { kind: "set_category", category: "All" };
  }

  if (
    normalized.startsWith("search ") ||
    normalized.startsWith("find ") ||
    normalized.startsWith("look for ")
  ) {
    const query = normalized
      .replace(/^search\s+/, "")
      .replace(/^find\s+/, "")
      .replace(/^look for\s+/, "")
      .trim();
    return query ? { kind: "search", query } : null;
  }

  if (
    normalized.includes("go to checkout") ||
    normalized.includes("go checkout") ||
    normalized.includes("open checkout") ||
    normalized.includes("review order") ||
    normalized === "checkout"
  ) {
    return { kind: "go_to_checkout" };
  }

  const product = findBestMatchingProduct(normalized, products);
  if (!product) {
    return null;
  }

  if (normalized.includes("from cart") || normalized.includes("remove all")) {
    return { kind: "remove_product", productId: product.id, productName: product.name };
  }

  if (
    normalized.startsWith("add") ||
    normalized.startsWith("increase") ||
    normalized.startsWith("plus")
  ) {
    return {
      kind: "change_quantity",
      productId: product.id,
      productName: product.name,
      quantityDelta: extractQuantity(normalized),
    };
  }

  if (
    normalized.startsWith("remove") ||
    normalized.startsWith("decrease") ||
    normalized.startsWith("minus")
  ) {
    return {
      kind: "change_quantity",
      productId: product.id,
      productName: product.name,
      quantityDelta: -extractQuantity(normalized),
    };
  }

  return null;
}

export function parseInventoryVoiceCommand(
  transcript: string,
  products: Array<{ id: string; name: string }>,
  categories: string[],
): InventoryVoiceCommand | null {
  const normalized = normalizeToken(transcript);

  if (!normalized) {
    return null;
  }

  if (normalized.includes("clear search")) {
    return { kind: "clear_search" };
  }

  if (
    normalized.includes("in stock only") ||
    normalized.includes("only in stock") ||
    normalized.includes("hide out of stock")
  ) {
    return { kind: "set_in_stock", value: true };
  }

  if (
    normalized.includes("show out of stock") ||
    normalized.includes("include out of stock") ||
    normalized.includes("all stock")
  ) {
    return { kind: "set_in_stock", value: false };
  }

  if (
    normalized.startsWith("search ") ||
    normalized.startsWith("find ") ||
    normalized.startsWith("look for ")
  ) {
    const query = normalized
      .replace(/^search\s+/, "")
      .replace(/^find\s+/, "")
      .replace(/^look for\s+/, "")
      .trim();
    return query ? { kind: "search", query } : null;
  }

  if (
    normalized.startsWith("create") ||
    normalized.startsWith("add product") ||
    normalized.startsWith("add item") ||
    normalized.startsWith("list product") ||
    normalized.startsWith("list item")
  ) {
    const name = parseInventoryName(transcript);
    const price = parseInventoryPrice(transcript);
    const stock = parseInventoryStock(transcript);
    if (!name || price === null || stock === null) {
      return null;
    }

    return {
      kind: "create_product",
      name,
      price,
      stock,
      category: parseInventoryCategory(transcript, categories),
      unitCode: parseInventoryUnitCode(transcript),
      isVisible: !(normalized.includes("draft") || normalized.includes("hidden")),
    };
  }

  if (
    normalized.startsWith("delete") ||
    normalized.startsWith("remove") ||
    normalized.includes("remove from inventory") ||
    normalized.includes("delete from inventory")
  ) {
    const product = findBestMatchingNamedItem(normalized, products);
    if (!product) {
      return null;
    }

    return {
      kind: "delete_product",
      productId: product.id,
      productName: product.name,
    };
  }

  return null;
}

export function parseLockedOrderVoiceCommand(transcript: string): LockedOrderVoiceCommand | null {
  const normalized = normalizeToken(transcript);

  if (!normalized) {
    return null;
  }

  if (normalized.includes("load despatch") || normalized.includes("fetch despatch")) {
    return { kind: "fetch_despatch" };
  }

  if (normalized.includes("generate despatch") || normalized.includes("create despatch")) {
    return { kind: "generate_despatch" };
  }

  if (normalized.includes("generate invoice") || normalized.includes("create invoice")) {
    return { kind: "generate_invoice" };
  }

  if (normalized.includes("refresh invoice") || normalized.includes("fetch invoice details")) {
    return { kind: "refresh_invoice" };
  }

  if (normalized.includes("load invoice xml") || normalized.includes("fetch invoice xml")) {
    return { kind: "fetch_invoice_xml" };
  }

  if (normalized.includes("download invoice pdf") || normalized.includes("get invoice pdf")) {
    return { kind: "download_invoice_pdf" };
  }

  if (normalized.includes("delete invoice")) {
    return { kind: "delete_invoice" };
  }

  const statusMatch =
    normalized.match(/set invoice status to ([a-z]+)/) ??
    normalized.match(/mark invoice ([a-z]+)/);
  if (statusMatch?.[1]) {
    return { kind: "set_invoice_status", status: statusMatch[1]!.trim() };
  }

  return null;
}

export function parseCheckoutVoiceCommand(transcript: string): CheckoutVoiceCommand | null {
  const normalized = normalizeToken(transcript);

  if (!normalized) {
    return null;
  }

  if (
    normalized.includes("place order") ||
    normalized.includes("place orders") ||
    normalized.includes("submit checkout") ||
    normalized.includes("submit order") ||
    normalized.includes("complete checkout") ||
    normalized.includes("confirm order") ||
    normalized.includes("checkout now")
  ) {
    return { kind: "submit_checkout" };
  }

  return null;
}

function summarizeFieldChange(label: string, nextValue: string | null | undefined): string | null {
  const value = nextValue?.trim();
  return value ? `Updated ${label} to ${value}.` : null;
}

export function buildCheckoutAssistantPayload(current: {
  buyerEmail: string;
  buyerName: string;
  sellerEmail: string;
  sellerName: string;
  street: string;
  city: string;
  state: string;
  postcode: string;
  country: string;
  requestedDate: string;
  notes: string;
  issueDate: string;
  currency: string;
  lines: Array<{
    productId?: number | null;
    productName: string;
    quantity: number;
    unitCode: string;
    unitPrice: string;
  }>;
}): OrderRequestPayload {
  return {
    buyerEmail: current.buyerEmail,
    buyerName: current.buyerName,
    sellerEmail: current.sellerEmail,
    sellerName: current.sellerName,
    currency: current.currency,
    issueDate: current.issueDate,
    notes: current.notes || null,
    delivery: {
      street: current.street || null,
      city: current.city || null,
      state: current.state || null,
      postcode: current.postcode || null,
      country: current.country || null,
      requestedDate: current.requestedDate || null,
    },
    lines: current.lines.map(line => ({
      productId: line.productId ?? null,
      productName: line.productName,
      quantity: line.quantity,
      unitCode: line.unitCode,
      unitPrice: line.unitPrice || null,
    })),
  };
}

export function summarizeCheckoutFieldMutations(
  previous: {
    buyerName: string;
    street: string;
    city: string;
    state: string;
    postcode: string;
    country: string;
    requestedDate: string;
    notes: string;
  },
  next: {
    buyerName: string;
    street: string;
    city: string;
    state: string;
    postcode: string;
    country: string;
    requestedDate: string;
    notes: string;
  },
): string[] {
  const messages = [
    previous.buyerName !== next.buyerName
      ? summarizeFieldChange("buyer name", next.buyerName)
      : null,
    previous.street !== next.street ? summarizeFieldChange("delivery street", next.street) : null,
    previous.city !== next.city ? summarizeFieldChange("delivery city", next.city) : null,
    previous.state !== next.state ? summarizeFieldChange("delivery state", next.state) : null,
    previous.postcode !== next.postcode
      ? summarizeFieldChange("delivery postcode", next.postcode)
      : null,
    previous.country !== next.country
      ? summarizeFieldChange("delivery country", next.country)
      : null,
    previous.requestedDate !== next.requestedDate
      ? summarizeFieldChange("requested date", next.requestedDate)
      : null,
    previous.notes !== next.notes ? summarizeFieldChange("notes", next.notes) : null,
  ];

  return messages.filter((message): message is string => Boolean(message));
}
