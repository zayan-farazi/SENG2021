import type { ComponentType } from "react";
import { Coffee, Gift, Package2, Palette, Shirt, Sparkles } from "lucide-react";

export type MarketplaceProduct = {
  id: string;
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
