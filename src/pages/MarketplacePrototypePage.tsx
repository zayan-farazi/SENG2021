import { useEffect, useMemo, useRef, useState } from "react";
import { Minus, Plus, Search, ShoppingBag } from "lucide-react";
import { AppHeader } from "../components/AppHeader";
import { VoiceAssistantDock } from "../components/VoiceAssistantDock";
import { navigate } from "../components/AppLink";
import { buildLiveRefreshLabel, LIVE_REFRESH_INTERVAL_MS } from "../liveRefresh";
import { fetchMarketplaceProducts } from "../productApi";
import { getMarketplaceAssistantWebSocketUrl } from "../voiceOrder";
import {
  calculateCartTotal,
  deriveMarketplaceCategories,
  productRecordToMarketplaceProduct,
  readStoredMarketplaceCart,
  writeStoredMarketplaceCart,
  type MarketplaceCartLine,
  type MarketplaceCartState,
  type MarketplaceFilterState,
  type MarketplaceProduct,
} from "./marketplacePrototypeData";
import { parseMarketplaceVoiceCommand, type AssistantActionResult } from "../voiceAssistant";
import "./marketplace-prototype.css";

type MarketplaceAssistantCommand =
  | { kind: "search"; query: string }
  | { kind: "clear_search" }
  | { kind: "set_category"; category: string }
  | { kind: "set_in_stock"; value: boolean }
  | { kind: "go_to_checkout" }
  | { kind: "change_quantity"; productId: string; quantityDelta: number }
  | { kind: "remove_product"; productId: string };

type MarketplaceAssistantServerEnvelope = {
  type: string;
  payload?: {
    kind?: "partial" | "final";
    text?: string;
    command?: MarketplaceAssistantCommand | null;
    message?: string | null;
  };
};

const defaultFilters: MarketplaceFilterState = {
  query: "",
  category: "All",
  inStockOnly: false,
};

function formatPrice(value: number): string {
  return `$${value.toFixed(0)}`;
}

function getBadgeClassName(badge: MarketplaceProduct["badge"]): string {
  if (badge === "Out of stock") {
    return "marketplace-product-badge marketplace-product-badge-out";
  }

  if (badge === "Low stock") {
    return "marketplace-product-badge marketplace-product-badge-warning";
  }

  if (badge === "New") {
    return "marketplace-product-badge marketplace-product-badge-new";
  }

  return "marketplace-product-badge marketplace-product-badge-featured";
}

function buildCartLine(product: MarketplaceProduct, quantity: number): MarketplaceCartLine {
  return {
    productId: product.id,
    productRecordId: product.productRecordId,
    name: product.name,
    seller: product.seller,
    sellerEmail: product.sellerEmail,
    unitPrice: product.price,
    quantity,
    stock: product.stock,
    unitCode: product.unitCode,
    subtotal: product.price * quantity,
  };
}

type MarketplaceProductCardProps = {
  product: MarketplaceProduct;
  quantity: number;
  onChangeQuantity: (product: MarketplaceProduct, delta: number) => void;
};

function MarketplaceProductCard({
  product,
  quantity,
  onChangeQuantity,
}: MarketplaceProductCardProps) {
  const Icon = product.icon;
  const isSelected = quantity > 0;

  return (
    <article className="marketplace-product-card" data-selected={isSelected ? "true" : "false"}>
      <div className={`marketplace-product-media marketplace-product-media-${product.tone}`} aria-hidden="true">
        <Icon size={34} strokeWidth={2} />
      </div>

      <div className="marketplace-product-card-body">
        <div className="marketplace-product-heading">
          <div className="marketplace-product-heading-copy">
            <div className="marketplace-product-labels">
              <span className="marketplace-product-category">{product.category}</span>
              {product.badge ? <span className={getBadgeClassName(product.badge)}>{product.badge}</span> : null}
            </div>
            <h2>{product.name}</h2>
            <p>{product.seller}</p>
          </div>
          <strong>{formatPrice(product.price)}</strong>
        </div>

        <div className="marketplace-product-footer">
          <span className="marketplace-product-stock">{product.stock} available</span>

          <div className="marketplace-quantity-stepper" aria-label={`Quantity for ${product.name}`}>
            <button
              type="button"
              className="marketplace-stepper-button"
              aria-label={`Decrease ${product.name}`}
              onClick={() => onChangeQuantity(product, -1)}
              disabled={quantity === 0}
            >
              <Minus size={14} strokeWidth={2.2} />
            </button>
            <span className="marketplace-stepper-value" aria-live="polite">
              {quantity}
            </span>
            <button
              type="button"
              className="marketplace-stepper-button"
              aria-label={`Increase ${product.name}`}
              onClick={() => onChangeQuantity(product, 1)}
              disabled={quantity >= product.stock}
            >
              <Plus size={14} strokeWidth={2.2} />
            </button>
          </div>
        </div>
      </div>
    </article>
  );
}

export function MarketplacePrototypePage() {
  const [filters, setFilters] = useState<MarketplaceFilterState>(defaultFilters);
  const [cart, setCart] = useState<MarketplaceCartState>(() => readStoredMarketplaceCart());
  const [products, setProducts] = useState<MarketplaceProduct[]>([]);
  const [isLoadingProducts, setIsLoadingProducts] = useState(true);
  const [productsError, setProductsError] = useState<string | null>(null);
  const [isRefreshingProducts, setIsRefreshingProducts] = useState(false);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);
  const [assistantLiveTranscript, setAssistantLiveTranscript] = useState<string | null>(null);
  const assistantSocketRef = useRef<WebSocket | null>(null);
  const assistantResultResolverRef = useRef<((result: AssistantActionResult) => void) | null>(null);
  const cartRef = useRef(cart);
  const filtersRef = useRef(filters);
  const productsRef = useRef(products);
  const categoriesRef = useRef<string[]>(["All"]);
  const marketplaceAssistantWebSocketUrl = getMarketplaceAssistantWebSocketUrl();

  useEffect(() => {
    writeStoredMarketplaceCart(cart);
  }, [cart]);

  useEffect(() => {
    cartRef.current = cart;
  }, [cart]);

  useEffect(() => {
    filtersRef.current = filters;
  }, [filters]);

  useEffect(() => {
    productsRef.current = products;
  }, [products]);

  useEffect(() => {
    let cancelled = false;
    let pollTimer: number | null = null;

    const clearPollTimer = () => {
      if (pollTimer !== null) {
        window.clearTimeout(pollTimer);
        pollTimer = null;
      }
    };

    const scheduleNextPoll = () => {
      clearPollTimer();
      if (cancelled) {
        return;
      }

      pollTimer = window.setTimeout(() => {
        if (document.visibilityState !== "visible") {
          scheduleNextPoll();
          return;
        }

        void refreshProducts(false).finally(scheduleNextPoll);
      }, LIVE_REFRESH_INTERVAL_MS);
    };

    const refreshProducts = async (showLoading: boolean) => {
      if (showLoading) {
        setIsLoadingProducts(true);
      } else {
        setIsRefreshingProducts(true);
      }
      setProductsError(null);

      try {
        const response = await fetchMarketplaceProducts(100, 0);
        if (cancelled) {
          return;
        }

        const nextProducts = response.items.map(productRecordToMarketplaceProduct);
        setProducts(nextProducts);
        setLastUpdatedAt(Date.now());
        setCart(current => {
          const productIndex = new Map(nextProducts.map(product => [product.id, product]));
          const nextLines = current.lines
            .map(line => {
              const product = productIndex.get(line.productId);
              if (!product || product.stock <= 0) {
                return null;
              }

              const quantity = Math.max(0, Math.min(line.quantity, product.stock));
              if (quantity === 0) {
                return null;
              }

              return buildCartLine(product, quantity);
            })
            .filter((line): line is MarketplaceCartLine => line !== null);

          return { lines: nextLines };
        });
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "Unable to load marketplace listings.";
          setProductsError(message);
          if (productsRef.current.length === 0) {
            setProducts([]);
          }
        }
      } finally {
        if (!cancelled && showLoading) {
          setIsLoadingProducts(false);
        }
        if (!cancelled && !showLoading) {
          setIsRefreshingProducts(false);
        }
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState !== "visible") {
        return;
      }

      void refreshProducts(false);
    };

    void refreshProducts(true).finally(scheduleNextPoll);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      cancelled = true;
      clearPollTimer();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  const marketplaceCategories = useMemo(() => deriveMarketplaceCategories(products), [products]);

  useEffect(() => {
    categoriesRef.current = marketplaceCategories;
  }, [marketplaceCategories]);

  const filteredProducts = useMemo(() => {
    return products.filter(product => {
      const matchesQuery =
        filters.query.trim().length === 0 ||
        `${product.name} ${product.seller}`.toLowerCase().includes(filters.query.trim().toLowerCase());
      const matchesCategory = filters.category === "All" || product.category === filters.category;
      const matchesStock = !filters.inStockOnly || product.stock > 0;
      return matchesQuery && matchesCategory && matchesStock;
    });
  }, [filters, products]);

  const totalItems = useMemo(
    () => cart.lines.reduce((sum, line) => sum + line.quantity, 0),
    [cart.lines],
  );
  const totalPrice = useMemo(() => calculateCartTotal(cart.lines), [cart.lines]);

  const getQuantity = (productId: string) =>
    cart.lines.find(line => line.productId === productId)?.quantity ?? 0;

  const handleChangeQuantity = (product: MarketplaceProduct, delta: number) => {
    setCart(current => {
      const existing = current.lines.find(line => line.productId === product.id);
      const nextQuantity = Math.max(0, Math.min(product.stock, (existing?.quantity ?? 0) + delta));

      if (nextQuantity === 0) {
        return {
          lines: current.lines.filter(line => line.productId !== product.id),
        };
      }

      const nextLine = buildCartLine(product, nextQuantity);

      if (!existing) {
        return { lines: [...current.lines, nextLine] };
      }

      return {
        lines: current.lines.map(line => (line.productId === product.id ? nextLine : line)),
      };
    });
  };

  const applyMarketplaceCommand = (command: MarketplaceAssistantCommand): AssistantActionResult => {
    if (command.kind === "search") {
      setFilters(current => ({ ...current, query: command.query }));
      return {
        kind: "applied",
        message: `Updated search to ${command.query}.`,
      };
    }

    if (command.kind === "clear_search") {
      setFilters(current => ({ ...current, query: "" }));
      return {
        kind: "applied",
        message: "Cleared the marketplace search.",
      };
    }

    if (command.kind === "set_category") {
      setFilters(current => ({ ...current, category: command.category }));
      return {
        kind: "applied",
        message:
          command.category === "All"
            ? "Showing all categories."
            : `Filtered the marketplace to ${command.category}.`,
      };
    }

    if (command.kind === "set_in_stock") {
      setFilters(current => ({ ...current, inStockOnly: command.value }));
      return {
        kind: "applied",
        message: command.value ? "Enabled in-stock-only filtering." : "Showing all stock states.",
      };
    }

    if (command.kind === "go_to_checkout") {
      if (cartRef.current.lines.length === 0) {
        return {
          kind: "rejected",
          message: "Add items to the cart before going to checkout.",
        };
      }

      navigate("/marketplace/review");
      return {
        kind: "applied",
        message: "Opened checkout.",
      };
    }

    const product = productsRef.current.find(candidate => candidate.id === command.productId);
    if (!product) {
      return {
        kind: "rejected",
        message: "That product is not available in the current catalogue.",
      };
    }

    const currentQuantity =
      cartRef.current.lines.find(line => line.productId === product.id)?.quantity ?? 0;

    if (command.kind === "remove_product") {
      if (currentQuantity === 0) {
        return {
          kind: "rejected",
          message: `${product.name} is not currently in the cart.`,
        };
      }

      handleChangeQuantity(product, -currentQuantity);
      return {
        kind: "applied",
        message: `Removed ${product.name} from the cart.`,
      };
    }

    const nextQuantity = Math.max(0, Math.min(product.stock, currentQuantity + command.quantityDelta));
    if (nextQuantity === currentQuantity) {
      return {
        kind: "rejected",
        message:
          command.quantityDelta > 0
            ? `${product.name} is already at the available stock limit.`
            : `${product.name} is not currently in the cart.`,
      };
    }

    handleChangeQuantity(product, command.quantityDelta);
    return {
      kind: "applied",
      message:
        command.quantityDelta > 0
          ? `Added ${nextQuantity - currentQuantity} ${product.name} to the cart.`
          : `Removed ${currentQuantity - nextQuantity} ${product.name} from the cart.`,
    };
  };

  const startMarketplaceAssistantRequest = (transcript: string) => {
    const socket = assistantSocketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return null;
    }

    return new Promise<AssistantActionResult>(resolve => {
      const timeoutId = window.setTimeout(() => {
        if (assistantResultResolverRef.current) {
          assistantResultResolverRef.current = null;
          resolve({
            kind: "rejected",
            message: "The marketplace assistant timed out.",
          });
        }
      }, 12000);

      assistantResultResolverRef.current = resolve;
      socket.send(JSON.stringify({ type: "transcript.final", payload: { text: transcript } }));

      assistantResultResolverRef.current = result => {
        window.clearTimeout(timeoutId);
        resolve(result);
      };
    });
  };

  useEffect(() => {
    const socket = new WebSocket(marketplaceAssistantWebSocketUrl);
    assistantSocketRef.current = socket;

    const sendContext = (type: "session.start" | "context.patch") => {
      if (socket.readyState !== WebSocket.OPEN) {
        return;
      }

      socket.send(
        JSON.stringify({
          type,
          payload: {
            products: productsRef.current.map(product => ({
              id: product.id,
              name: product.name,
              seller: product.seller,
              category: product.category,
              stock: product.stock,
            })),
            categories: categoriesRef.current,
            filters: filtersRef.current,
            cartLines: cartRef.current.lines.map(line => ({
              productId: line.productId,
              name: line.name,
              quantity: line.quantity,
            })),
          },
        }),
      );
    };

    const handleOpen = () => {
      sendContext("session.start");
    };

    const handleMessage = (event: MessageEvent<string>) => {
      const envelope = JSON.parse(event.data) as MarketplaceAssistantServerEnvelope;
      if (envelope.type === "transcript.echo") {
        if (envelope.payload?.kind === "partial") {
          setAssistantLiveTranscript(envelope.payload.text ?? null);
        }
        if (envelope.payload?.kind === "final") {
          setAssistantLiveTranscript(null);
        }
        return;
      }

      if (envelope.type === "assistant.command") {
        const resolver = assistantResultResolverRef.current;
        assistantResultResolverRef.current = null;
        const result = envelope.payload?.command
          ? applyMarketplaceCommand(envelope.payload.command)
          : {
              kind: "rejected" as const,
              message: envelope.payload?.message ?? "I could not map that to a marketplace action.",
            };
        resolver?.(result);
        return;
      }

      if (envelope.type === "error") {
        const resolver = assistantResultResolverRef.current;
        assistantResultResolverRef.current = null;
        resolver?.({
          kind: "rejected",
          message: envelope.payload?.message ?? "The marketplace assistant could not respond.",
        });
      }
    };

    const handleClose = () => {
      setAssistantLiveTranscript(null);
      const resolver = assistantResultResolverRef.current;
      assistantResultResolverRef.current = null;
      resolver?.({
        kind: "rejected",
        message: "The marketplace assistant disconnected.",
      });
    };

    socket.addEventListener("open", handleOpen);
    socket.addEventListener("message", handleMessage);
    socket.addEventListener("close", handleClose);

    return () => {
      socket.removeEventListener("open", handleOpen);
      socket.removeEventListener("message", handleMessage);
      socket.removeEventListener("close", handleClose);
      assistantSocketRef.current = null;
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close();
      }
    };
  }, [marketplaceAssistantWebSocketUrl]);

  useEffect(() => {
    const socket = assistantSocketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return;
    }

    socket.send(
      JSON.stringify({
        type: "context.patch",
        payload: {
          products: products.map(product => ({
            id: product.id,
            name: product.name,
            seller: product.seller,
            category: product.category,
            stock: product.stock,
          })),
          categories: marketplaceCategories,
          filters,
          cartLines: cart.lines.map(line => ({
            productId: line.productId,
            name: line.name,
            quantity: line.quantity,
          })),
        },
      }),
    );
  }, [cart, filters, marketplaceCategories, products]);

  const handleVoiceTranscript = async (transcript: string): Promise<AssistantActionResult> => {
    setAssistantLiveTranscript(null);
    const streamedResult = await startMarketplaceAssistantRequest(transcript);
    if (streamedResult) {
      return streamedResult;
    }

    const command = parseMarketplaceVoiceCommand(transcript, products, marketplaceCategories);

    if (!command) {
      return {
        kind: "rejected",
        message: "I could not map that to a marketplace action.",
      };
    }
    return applyMarketplaceCommand(command);
  };

  const handleVoicePartialTranscript = (transcript: string) => {
    const socket = assistantSocketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setAssistantLiveTranscript(transcript);
      return;
    }

    socket.send(JSON.stringify({ type: "transcript.partial", payload: { text: transcript } }));
  };

  const openReview = () => {
    if (cart.lines.length === 0) {
      return;
    }

    navigate("/marketplace/review");
  };

  return (
    <div className="landing-root">
      <div className="landing-container">
        <section className="landing-stage">
          <AppHeader />

          <main className="marketplace-page">
            <header className="marketplace-page-header">
              <div>
                <h1>Marketplace</h1>
                <p>Browse seller listings, set quantities, and stage an order before review.</p>
                <p className="marketplace-live-status" aria-live="polite">
                  {buildLiveRefreshLabel(lastUpdatedAt, isRefreshingProducts)}
                </p>
              </div>

              <div className="marketplace-toolbar">
                <label className="marketplace-search">
                  <span className="marketplace-search-icon" aria-hidden="true">
                    <Search size={16} strokeWidth={2.2} />
                  </span>
                  <input
                    type="search"
                    value={filters.query}
                    onChange={event =>
                      setFilters(current => ({ ...current, query: event.target.value }))
                    }
                    placeholder="Search products or sellers"
                    aria-label="Search products or sellers"
                  />
                </label>

                <label className="marketplace-select-field">
                  <span className="marketplace-select-label">Category</span>
                  <select
                    value={filters.category}
                    onChange={event =>
                      setFilters(current => ({ ...current, category: event.target.value }))
                    }
                    aria-label="Filter by category"
                  >
                    {marketplaceCategories.map(category => (
                      <option key={category} value={category}>
                        {category}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="marketplace-filter-toggle">
                  <input
                    type="checkbox"
                    checked={filters.inStockOnly}
                    onChange={event =>
                      setFilters(current => ({ ...current, inStockOnly: event.target.checked }))
                    }
                  />
                  <span className="marketplace-filter-toggle-mark" aria-hidden="true" />
                  <span>In stock only</span>
                </label>
              </div>
            </header>

            <VoiceAssistantDock
              context="marketplace"
              hint="Try “search candles”, “add two ceramic mugs”, or “go to checkout”."
              liveTranscript={assistantLiveTranscript}
              streaming
              onPartialTranscript={handleVoicePartialTranscript}
              onTranscript={handleVoiceTranscript}
            />

            <div className="marketplace-content">
              <section className="marketplace-products-shell" aria-labelledby="marketplace-products-title">
                <div className="marketplace-section-header">
                  <div>
                    <h2 id="marketplace-products-title">Available listings</h2>
                    <p>{filteredProducts.length} products match the current filters.</p>
                  </div>
                  <span className="marketplace-count-chip">{totalItems} items selected</span>
                </div>

                {filteredProducts.length === 0 ? (
                  <div className="marketplace-empty-state">
                    <strong>
                      {productsError
                        ? "Marketplace listings are unavailable."
                        : isLoadingProducts
                          ? "Loading marketplace listings."
                          : "No listings match these filters."}
                    </strong>
                    <span>
                      {productsError
                        ? "The catalogue request failed. Reload or publish products from inventory first."
                        : isLoadingProducts
                          ? "Fetching the latest published products."
                          : "Adjust the search or category to bring products back into view."}
                    </span>
                  </div>
                ) : (
                  <div className="marketplace-product-grid">
                    {filteredProducts.map(product => (
                      <MarketplaceProductCard
                        key={product.id}
                        product={product}
                        quantity={getQuantity(product.id)}
                        onChangeQuantity={handleChangeQuantity}
                      />
                    ))}
                  </div>
                )}
              </section>

              <aside className="marketplace-cart-shell" aria-labelledby="marketplace-cart-title">
                <div className="marketplace-cart-header">
                  <div>
                    <h2 id="marketplace-cart-title">Cart summary</h2>
                    <p>Review the cart, then place real orders grouped by seller.</p>
                  </div>
                  <span className="marketplace-cart-pill">
                    <ShoppingBag size={14} strokeWidth={2.1} />
                    {totalItems} items
                  </span>
                </div>

                {cart.lines.length === 0 ? (
                  <div className="marketplace-empty-state marketplace-empty-state-cart">
                    <strong>Your cart is empty.</strong>
                    <span>Select quantities from the product cards to begin building the order.</span>
                  </div>
                ) : (
                  <div className="marketplace-cart-lines">
                    {cart.lines.map(line => (
                      <article key={line.productId} className="marketplace-cart-line">
                        <div>
                          <strong>{line.name}</strong>
                          <span>
                            {line.seller} · {line.quantity} × {formatPrice(line.unitPrice)}
                          </span>
                        </div>
                        <strong>{formatPrice(line.subtotal)}</strong>
                      </article>
                    ))}
                  </div>
                )}

                <div className="marketplace-cart-footer">
                  <div className="marketplace-cart-total">
                    <span>Total</span>
                    <strong>{formatPrice(totalPrice)}</strong>
                  </div>

                  <button
                    type="button"
                    className="marketplace-primary-action"
                    onClick={openReview}
                    disabled={cart.lines.length === 0}
                  >
                    Review order
                  </button>
                </div>
              </aside>
            </div>
          </main>
        </section>
      </div>
    </div>
  );
}
