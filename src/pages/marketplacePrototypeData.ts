import type { ComponentType } from "react";
import { Coffee, Gift, Package2, Palette, Shirt, Sparkles } from "lucide-react";
import type { ProductRecord } from "../productApi";

export type MarketplaceProduct = {
  id: string;
  productRecordId: number | null;
  name: string;
  price: number;
  seller: string;
  sellerEmail: string;
  stock: number;
  category: string;
  unitCode: string;
  badge?: "Featured" | "Low stock" | "New";
  tone: "peach" | "mint" | "gold";
  icon: ComponentType<{ size?: number; strokeWidth?: number }>;
};

export type MarketplaceFilterState = {
  query: string;
  category: string;
  inStockOnly: boolean;
};

export type MarketplaceCartLine = {
  productId: string;
  productRecordId: number | null;
  name: string;
  seller: string;
  sellerEmail: string;
  unitPrice: number;
  quantity: number;
  stock: number;
  unitCode: string;
  subtotal: number;
};

export type MarketplaceCartState = {
  lines: MarketplaceCartLine[];
};

export type MarketplaceSellerOrderGroup = {
  seller: string;
  sellerEmail: string;
  lines: MarketplaceCartLine[];
  itemCount: number;
  total: number;
};

export type MarketplacePlacedOrder = {
  orderId: string;
  seller: string;
  sellerEmail: string;
  itemCount: number;
  total: number;
};

export type MarketplaceCheckoutSuccessState = {
  buyerName: string;
  orders: MarketplacePlacedOrder[];
};

export const MARKETPLACE_CART_STORAGE_KEY = "lockedout.marketplace-cart";
export const MARKETPLACE_CHECKOUT_SUCCESS_STORAGE_KEY = "lockedout.marketplace-checkout-success";

export const marketplaceProducts: MarketplaceProduct[] = [
  {
    id: "market-ceramic-mug",
    productRecordId: 101,
    name: "Handmade ceramic mug",
    price: 34,
    seller: "Harbour Studio",
    sellerEmail: "orders@harbourstudio.example",
    stock: 9,
    category: "Homeware",
    unitCode: "EA",
    badge: "Featured",
    tone: "peach",
    icon: Coffee,
  },
  {
    id: "market-denim-jacket",
    productRecordId: 102,
    name: "Vintage denim jacket",
    price: 62,
    seller: "North Lane Vintage",
    sellerEmail: "sales@northlanevintage.example",
    stock: 3,
    category: "Fashion",
    unitCode: "EA",
    badge: "Low stock",
    tone: "mint",
    icon: Shirt,
  },
  {
    id: "market-soy-candle",
    productRecordId: 103,
    name: "Natural soy candle set",
    price: 28,
    seller: "Soft Light Co",
    sellerEmail: "dispatch@softlight.example",
    stock: 12,
    category: "Homeware",
    unitCode: "EA",
    badge: "New",
    tone: "gold",
    icon: Sparkles,
  },
  {
    id: "market-gift-box",
    productRecordId: 104,
    name: "Self-care gift box",
    price: 48,
    seller: "Bloom Assembly",
    sellerEmail: "orders@bloomassembly.example",
    stock: 6,
    category: "Gifts",
    unitCode: "EA",
    tone: "mint",
    icon: Gift,
  },
  {
    id: "market-art-print",
    productRecordId: 105,
    name: "Abstract wall print",
    price: 46,
    seller: "Lineform Press",
    sellerEmail: "studio@lineformpress.example",
    stock: 14,
    category: "Art",
    unitCode: "EA",
    badge: "Featured",
    tone: "peach",
    icon: Palette,
  },
  {
    id: "market-market-tote",
    productRecordId: 106,
    name: "Weekend tote bag",
    price: 31,
    seller: "Field Notes Goods",
    sellerEmail: "hello@fieldnotesgoods.example",
    stock: 18,
    category: "Fashion",
    unitCode: "EA",
    tone: "gold",
    icon: Package2,
  },
];

export const marketplaceCategories = ["All", ...new Set(marketplaceProducts.map(product => product.category))];

function formatSellerLabel(email: string): string {
  const [handle = email, domain = ""] = email.split("@");
  const genericHandles = new Set(["orders", "sales", "dispatch", "hello", "studio", "support"]);
  const rawLabel =
    genericHandles.has(handle.toLowerCase()) && domain
      ? (domain.split(".")[0] ?? handle)
      : handle;

  return rawLabel
    .split(/[._-]+/)
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function getMarketplaceTone(category: string): MarketplaceProduct["tone"] {
  const normalized = category.toLowerCase();
  if (normalized.includes("fashion") || normalized.includes("beauty") || normalized.includes("accessories")) {
    return "mint";
  }
  if (normalized.includes("gift") || normalized.includes("electronics") || normalized.includes("sports")) {
    return "gold";
  }
  return "peach";
}

function getMarketplaceIcon(
  category: string,
): ComponentType<{ size?: number; strokeWidth?: number }> {
  const normalized = category.toLowerCase();
  if (normalized.includes("fashion") || normalized.includes("beauty") || normalized.includes("accessories")) {
    return Shirt;
  }
  if (normalized.includes("gift")) {
    return Gift;
  }
  if (normalized.includes("art") || normalized.includes("craft")) {
    return Palette;
  }
  if (normalized.includes("home") || normalized.includes("kitchen") || normalized.includes("handcrafted")) {
    return Coffee;
  }
  if (normalized.includes("electronics") || normalized.includes("book") || normalized.includes("music")) {
    return Sparkles;
  }
  return Package2;
}

function getMarketplaceBadge(record: ProductRecord): MarketplaceProduct["badge"] | undefined {
  if (record.available_units <= 3) {
    return "Low stock";
  }

  if (record.release_date) {
    const releaseTimestamp = Date.parse(record.release_date);
    if (!Number.isNaN(releaseTimestamp)) {
      const ageDays = Math.abs(Date.now() - releaseTimestamp) / (1000 * 60 * 60 * 24);
      if (ageDays <= 21) {
        return "New";
      }
    }
  }

  return undefined;
}

export function deriveMarketplaceCategories(products: MarketplaceProduct[]): string[] {
  return ["All", ...new Set(products.map(product => product.category).filter(Boolean))];
}

export function productRecordToMarketplaceProduct(record: ProductRecord): MarketplaceProduct {
  return {
    id: `product-${record.prod_id ?? `${record.party_id}-${record.name}`}`,
    productRecordId: record.prod_id,
    name: record.name,
    price: record.price,
    seller: formatSellerLabel(record.party_id),
    sellerEmail: record.party_id,
    stock: Math.max(0, Math.floor(record.available_units)),
    category: record.category,
    unitCode: record.unit,
    badge: getMarketplaceBadge(record),
    tone: getMarketplaceTone(record.category),
    icon: getMarketplaceIcon(record.category),
  };
}

export function readStoredMarketplaceCart(): MarketplaceCartState {
  if (typeof window === "undefined") {
    return { lines: [] };
  }

  const raw = window.sessionStorage.getItem(MARKETPLACE_CART_STORAGE_KEY);
  if (!raw) {
    return { lines: [] };
  }

  try {
    const parsed = JSON.parse(raw) as MarketplaceCartState;
    if (!parsed || !Array.isArray(parsed.lines)) {
      return { lines: [] };
    }
    return parsed;
  } catch {
    return { lines: [] };
  }
}

export function writeStoredMarketplaceCart(cart: MarketplaceCartState) {
  if (typeof window === "undefined") {
    return;
  }

  window.sessionStorage.setItem(MARKETPLACE_CART_STORAGE_KEY, JSON.stringify(cart));
}

export function clearStoredMarketplaceCart() {
  if (typeof window === "undefined") {
    return;
  }

  window.sessionStorage.removeItem(MARKETPLACE_CART_STORAGE_KEY);
}

export function calculateCartTotal(lines: MarketplaceCartLine[]): number {
  return lines.reduce((sum, line) => sum + line.subtotal, 0);
}

export function groupMarketplaceCartLines(
  lines: MarketplaceCartLine[],
): MarketplaceSellerOrderGroup[] {
  const grouped = new Map<string, MarketplaceSellerOrderGroup>();

  lines.forEach(line => {
    const key = `${line.sellerEmail}::${line.seller}`;
    const existing = grouped.get(key);
    if (existing) {
      existing.lines.push(line);
      existing.itemCount += line.quantity;
      existing.total += line.subtotal;
      return;
    }

    grouped.set(key, {
      seller: line.seller,
      sellerEmail: line.sellerEmail,
      lines: [line],
      itemCount: line.quantity,
      total: line.subtotal,
    });
  });

  return Array.from(grouped.values()).sort((left, right) => left.seller.localeCompare(right.seller));
}

export function readStoredMarketplaceCheckoutSuccess(): MarketplaceCheckoutSuccessState | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.sessionStorage.getItem(MARKETPLACE_CHECKOUT_SUCCESS_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as MarketplaceCheckoutSuccessState;
    if (!parsed || !Array.isArray(parsed.orders)) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function writeStoredMarketplaceCheckoutSuccess(state: MarketplaceCheckoutSuccessState) {
  if (typeof window === "undefined") {
    return;
  }

  window.sessionStorage.setItem(MARKETPLACE_CHECKOUT_SUCCESS_STORAGE_KEY, JSON.stringify(state));
}

export function clearStoredMarketplaceCheckoutSuccess() {
  if (typeof window === "undefined") {
    return;
  }

  window.sessionStorage.removeItem(MARKETPLACE_CHECKOUT_SUCCESS_STORAGE_KEY);
}
