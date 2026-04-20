import type { ComponentType } from "react";
import { Coffee, Gift, Package2, Palette, Shirt, Sparkles } from "lucide-react";

export type MarketplaceProduct = {
  id: string;
  name: string;
  price: number;
  seller: string;
  stock: number;
  category: string;
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
  unitPrice: number;
  quantity: number;
  stock: number;
  subtotal: number;
};

export type MarketplaceCartState = {
  lines: MarketplaceCartLine[];
};

export const MARKETPLACE_CART_STORAGE_KEY = "lockedout.marketplace-cart";

export const marketplaceProducts: MarketplaceProduct[] = [
  {
    id: "market-ceramic-mug",
    name: "Handmade ceramic mug",
    price: 34,
    seller: "Harbour Studio",
    stock: 9,
    category: "Homeware",
    badge: "Featured",
    tone: "peach",
    icon: Coffee,
  },
  {
    id: "market-denim-jacket",
    name: "Vintage denim jacket",
    price: 62,
    seller: "North Lane Vintage",
    stock: 3,
    category: "Fashion",
    badge: "Low stock",
    tone: "mint",
    icon: Shirt,
  },
  {
    id: "market-soy-candle",
    name: "Natural soy candle set",
    price: 28,
    seller: "Soft Light Co",
    stock: 12,
    category: "Homeware",
    badge: "New",
    tone: "gold",
    icon: Sparkles,
  },
  {
    id: "market-gift-box",
    name: "Self-care gift box",
    price: 48,
    seller: "Bloom Assembly",
    stock: 6,
    category: "Gifts",
    tone: "mint",
    icon: Gift,
  },
  {
    id: "market-art-print",
    name: "Abstract wall print",
    price: 46,
    seller: "Lineform Press",
    stock: 14,
    category: "Art",
    badge: "Featured",
    tone: "peach",
    icon: Palette,
  },
  {
    id: "market-market-tote",
    name: "Weekend tote bag",
    price: 31,
    seller: "Field Notes Goods",
    stock: 18,
    category: "Fashion",
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
