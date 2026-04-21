import type { MarketplaceProduct } from "./pages/marketplacePrototypeData";
import type { OrderRequestPayload } from "./voiceOrder";

export type AssistantContext = "marketplace" | "checkout" | "locked_order";

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
  | { kind: "change_quantity"; productId: string; quantityDelta: number; productName: string }
  | { kind: "remove_product"; productId: string; productName: string };

export type LockedOrderVoiceCommand =
  | { kind: "fetch_despatch" }
  | { kind: "generate_despatch" }
  | { kind: "generate_invoice" }
  | { kind: "refresh_invoice" }
  | { kind: "fetch_invoice_xml" }
  | { kind: "download_invoice_pdf" }
  | { kind: "set_invoice_status"; status: string }
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

function normalizeToken(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .trim()
    .replace(/\b(mugs|bags|candles|jackets|prints|boxes)\b/g, match => match.slice(0, -1))
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

function findBestMatchingProduct(
  transcript: string,
  products: MarketplaceProduct[],
): MarketplaceProduct | null {
  const transcriptTokens = tokenize(transcript);
  if (transcriptTokens.length === 0) {
    return null;
  }

  const scored = products
    .map(product => {
      const productTokens = tokenize(product.name);
      const score = productTokens.reduce((count, token) => {
        return transcriptTokens.some(transcriptToken => transcriptToken.startsWith(token) || token.startsWith(transcriptToken))
          ? count + 1
          : count;
      }, 0);
      return { product, score, tokenCount: productTokens.length };
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

  return best.score >= 2 || best.tokenCount === 1 ? best.product : null;
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
      (normalized.startsWith("show") || normalized.startsWith("filter") || normalized.includes("only")),
  );
  if (category) {
    return { kind: "set_category", category };
  }

  if (normalized.includes("show all") || normalized.includes("all categories")) {
    return { kind: "set_category", category: "All" };
  }

  if (normalized.startsWith("search ") || normalized.startsWith("find ") || normalized.startsWith("look for ")) {
    const query = normalized
      .replace(/^search\s+/, "")
      .replace(/^find\s+/, "")
      .replace(/^look for\s+/, "")
      .trim();
    return query ? { kind: "search", query } : null;
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
    normalized.match(/set invoice status to ([a-z]+)/) ||
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
    previous.buyerName !== next.buyerName ? summarizeFieldChange("buyer name", next.buyerName) : null,
    previous.street !== next.street ? summarizeFieldChange("delivery street", next.street) : null,
    previous.city !== next.city ? summarizeFieldChange("delivery city", next.city) : null,
    previous.state !== next.state ? summarizeFieldChange("delivery state", next.state) : null,
    previous.postcode !== next.postcode ? summarizeFieldChange("delivery postcode", next.postcode) : null,
    previous.country !== next.country ? summarizeFieldChange("delivery country", next.country) : null,
    previous.requestedDate !== next.requestedDate
      ? summarizeFieldChange("requested date", next.requestedDate)
      : null,
    previous.notes !== next.notes ? summarizeFieldChange("notes", next.notes) : null,
  ];

  return messages.filter((message): message is string => Boolean(message));
}
