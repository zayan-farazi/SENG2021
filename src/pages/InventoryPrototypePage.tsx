import { useEffect, useMemo, useRef, useState } from "react";
import type { ComponentType } from "react";
import {
  Coffee,
  ImagePlus,
  MoreHorizontal,
  Package2,
  Palette,
  Search,
  Shirt,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { AppHeader } from "../components/AppHeader";
import { VoiceAssistantDock } from "../components/VoiceAssistantDock";
import {
  createInventoryProduct,
  deleteInventoryProduct,
  fetchInventory,
  type ProductRecord,
  updateInventoryProduct,
} from "../productApi";
import { useStoredSession } from "../session";
import {
  parseInventoryVoiceCommand,
  type AssistantActionResult,
  type InventoryVoiceCommand,
} from "../voiceAssistant";
import { getInventoryAssistantWebSocketUrl } from "../voiceOrder";
import "./inventory-prototype.css";

type InventorySection = "launched" | "draft";

type InventoryProduct = {
  id: string;
  productId: number | null;
  name: string;
  price: number;
  stock: number;
  unitCode: string;
  status: string;
  section: InventorySection;
  dateLabel: string;
  sortDate: string;
  tone: "peach" | "mint" | "gold";
  icon: ComponentType<{ size?: number; strokeWidth?: number }>;
  description: string;
  category: string;
  isVisible: boolean;
  showSoldout: boolean;
};

type EditorMode =
  | { type: "closed" }
  | { type: "add" }
  | { type: "edit"; productId: string };

type EditorForm = {
  name: string;
  price: string;
  stock: string;
  unitCode: string;
  launchDate: string;
  description: string;
  category: string;
  isVisible: boolean;
  showSoldout: boolean;
};

type InventoryAssistantServerEnvelope = {
  type: string;
  payload?: {
    kind?: "partial" | "final";
    text?: string;
    command?: InventoryVoiceCommand | null;
    message?: string | null;
  };
};

const categoryOptions = [
  "Fashion",
  "Home and Kitchen",
  "Groceries and Consumables",
  "Antiques and Collectibles",
  "Jewellery and Accessories",
  "Health and Beauty",
  "Sports",
  "Furniture",
  "Electronics",
  "Arts & Crafts",
  "Books, Music and Film",
  "Gifts",
  "Handcrafted",
  "Others",
];

const emptyForm: EditorForm = {
  name: "",
  price: "",
  stock: "",
  unitCode: "EA",
  launchDate: "",
  description: "",
  category: "Handcrafted",
  isVisible: false,
  showSoldout: true,
};

function describeInventoryError(error: unknown, fallback: string): string {
  if (!(error instanceof Error) || !error.message.includes(":")) {
    return fallback;
  }

  return error.message.slice(error.message.lastIndexOf(":") + 1).trim() || fallback;
}

function formatPrice(value: number): string {
  return `$${value.toFixed(0)}`;
}

function formatInventoryDateLabel(product: ProductRecord, section: InventorySection): string {
  if (!product.release_date) {
    return section === "launched" ? "Live now" : "No launch date";
  }

  const parsed = new Date(product.release_date);
  if (Number.isNaN(parsed.getTime())) {
    return section === "launched" ? "Live now" : "No launch date";
  }

  const formatted = new Intl.DateTimeFormat("en-AU", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(parsed);

  return section === "launched" ? `Since ${formatted}` : `Launches ${formatted}`;
}

function deriveSection(product: ProductRecord): InventorySection {
  if (!product.is_visible) {
    return "draft";
  }

  if (!product.release_date) {
    return "launched";
  }

  const releaseAt = new Date(product.release_date);
  return releaseAt.getTime() > Date.now() ? "draft" : "launched";
}

function deriveStatus(product: ProductRecord, section: InventorySection): string {
  if (section === "draft") {
    return "Draft";
  }
  if (product.available_units <= 0) {
    return "Out of stock";
  }
  if (product.available_units <= 5) {
    return "Low stock";
  }
  return "Live";
}

function toneForCategory(category: string): InventoryProduct["tone"] {
  const normalized = category.toLowerCase();
  if (normalized.includes("fashion") || normalized.includes("beauty")) {
    return "mint";
  }
  if (normalized.includes("gift") || normalized.includes("craft")) {
    return "gold";
  }
  return "peach";
}

function iconForCategory(category: string): InventoryProduct["icon"] {
  const normalized = category.toLowerCase();
  if (normalized.includes("fashion")) {
    return Shirt;
  }
  if (normalized.includes("gift")) {
    return Sparkles;
  }
  if (normalized.includes("craft") || normalized.includes("art")) {
    return Palette;
  }
  if (normalized.includes("home") || normalized.includes("kitchen")) {
    return Coffee;
  }
  return Package2;
}

function normalizeInventoryRecord(product: ProductRecord): InventoryProduct {
  const section = deriveSection(product);
  return {
    id: String(product.prod_id ?? `${product.party_id}-${product.name}`),
    productId: product.prod_id,
    name: product.name,
    price: product.price,
    stock: product.available_units,
    unitCode: product.unit,
    status: deriveStatus(product, section),
    section,
    dateLabel: formatInventoryDateLabel(product, section),
    sortDate: product.release_date ?? "9999-12-31",
    tone: toneForCategory(product.category),
    icon: iconForCategory(product.category),
    description: product.description ?? "",
    category: product.category,
    isVisible: product.is_visible,
    showSoldout: product.show_soldout,
  };
}

function sortProducts(products: InventoryProduct[], section: InventorySection): InventoryProduct[] {
  const sorted = [...products];
  sorted.sort((left, right) =>
    section === "launched"
      ? right.sortDate.localeCompare(left.sortDate)
      : left.sortDate.localeCompare(right.sortDate),
  );
  return sorted;
}

type InventoryCardProps = {
  product: InventoryProduct;
  onEdit: (productId: string) => void;
};

function InventoryCard({ product, onEdit }: InventoryCardProps) {
  const statusClass =
    product.status === "Low stock"
      ? "inventory-product-badge inventory-product-badge-warning"
      : product.status === "Out of stock"
        ? "inventory-product-badge inventory-product-badge-muted"
        : product.status === "Draft"
          ? "inventory-product-badge inventory-product-badge-draft"
          : "inventory-product-badge inventory-product-badge-live";
  const Icon = product.icon;

  return (
    <article className="inventory-product-card">
      <div className={`inventory-product-media inventory-product-media-${product.tone}`} aria-hidden="true">
        <Icon size={34} strokeWidth={2} />
      </div>

      <div className="inventory-product-card-body">
        <div className="inventory-product-topline">
          <span className={statusClass}>{product.status}</span>
          <button
            type="button"
            className="inventory-product-menu"
            aria-label={`Edit ${product.name}`}
            onClick={() => onEdit(product.id)}
          >
            <MoreHorizontal size={16} strokeWidth={2.2} />
          </button>
        </div>

        <div className="inventory-product-heading">
          <h3>{product.name}</h3>
          <strong>{formatPrice(product.price)}</strong>
        </div>

        <div className="inventory-product-meta">
          <span className="inventory-product-stock">{product.stock} in stock</span>
          <span className="inventory-product-date">{product.dateLabel}</span>
        </div>
      </div>
    </article>
  );
}

type InventorySectionProps = {
  title: string;
  helper: string;
  products: InventoryProduct[];
  expanded: boolean;
  onToggleExpanded: () => void;
  onEdit: (productId: string) => void;
};

function InventorySectionBlock({
  title,
  helper,
  products,
  expanded,
  onToggleExpanded,
  onEdit,
}: InventorySectionProps) {
  return (
    <section className="inventory-section-shell" aria-labelledby={`${title}-title`}>
      <div className="inventory-section-header">
        <div>
          <h2 id={`${title}-title`}>{title}</h2>
          <p>{helper}</p>
        </div>
        <button type="button" className="inventory-text-button" onClick={onToggleExpanded}>
          {expanded ? "Show less" : "View all"}
        </button>
      </div>

      <div className="inventory-product-grid" data-expanded={expanded ? "true" : "false"}>
        {products.map(product => (
          <InventoryCard key={product.id} product={product} onEdit={onEdit} />
        ))}
      </div>
    </section>
  );
}

export function InventoryPrototypePage() {
  const session = useStoredSession();
  const [products, setProducts] = useState<InventoryProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [inStockOnly, setInStockOnly] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Record<InventorySection, boolean>>({
    launched: false,
    draft: false,
  });
  const [editorMode, setEditorMode] = useState<EditorMode>({ type: "closed" });
  const [editorForm, setEditorForm] = useState<EditorForm>(emptyForm);
  const [editorBusy, setEditorBusy] = useState<"save" | "delete" | null>(null);
  const [editorError, setEditorError] = useState<string | null>(null);
  const [assistantLiveTranscript, setAssistantLiveTranscript] = useState<string | null>(null);
  const assistantSocketRef = useRef<WebSocket | null>(null);
  const assistantResultResolverRef = useRef<((result: AssistantActionResult) => void) | null>(null);
  const productsRef = useRef(products);
  const searchQueryRef = useRef(searchQuery);
  const inStockOnlyRef = useRef(inStockOnly);
  const categoriesRef = useRef<string[]>(categoryOptions);
  const sessionRef = useRef(session);
  const inventoryAssistantWebSocketUrl = getInventoryAssistantWebSocketUrl();

  useEffect(() => {
    productsRef.current = products;
  }, [products]);

  useEffect(() => {
    searchQueryRef.current = searchQuery;
  }, [searchQuery]);

  useEffect(() => {
    inStockOnlyRef.current = inStockOnly;
  }, [inStockOnly]);

  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  useEffect(() => {
    if (!session) {
      return;
    }

    let cancelled = false;
    setLoading(true);
    setPageError(null);

    void fetchInventory(session)
      .then(response => {
        if (cancelled) {
          return;
        }
        setProducts(response.items.map(normalizeInventoryRecord));
      })
      .catch(error => {
        if (cancelled) {
          return;
        }
        setPageError(
          error instanceof Error && error.message.startsWith("inventory-fetch:")
            ? error.message.slice(error.message.lastIndexOf(":") + 1).trim() ||
                "Unable to load inventory."
            : "Unable to load inventory.",
        );
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [session]);

  const openAddPanel = () => {
    setEditorMode({ type: "add" });
    setEditorForm(emptyForm);
    setEditorError(null);
  };

  const openEditPanel = (productId: string) => {
    const product = products.find(item => item.id === productId);
    if (!product) {
      return;
    }

    setEditorMode({ type: "edit", productId });
    setEditorForm({
      name: product.name,
      price: String(product.price),
      stock: String(product.stock),
      unitCode: product.unitCode,
      launchDate: product.sortDate === "9999-12-31" ? "" : product.sortDate.slice(0, 10),
      description: product.description,
      category: product.category,
      isVisible: product.isVisible,
      showSoldout: product.showSoldout,
    });
    setEditorError(null);
  };

  const closeEditor = () => {
    setEditorMode({ type: "closed" });
    setEditorError(null);
    setEditorBusy(null);
  };

  const filteredLaunched = useMemo(() => {
    return sortProducts(
      products.filter(product => {
        const matchesSection = product.section === "launched";
        const matchesSearch = product.name.toLowerCase().includes(searchQuery.toLowerCase());
        const matchesStock = !inStockOnly || product.stock > 0;
        return matchesSection && matchesSearch && matchesStock;
      }),
      "launched",
    );
  }, [inStockOnly, products, searchQuery]);

  const filteredDraft = useMemo(() => {
    return sortProducts(
      products.filter(product => {
        const matchesSection = product.section === "draft";
        const matchesSearch = product.name.toLowerCase().includes(searchQuery.toLowerCase());
        const matchesStock = !inStockOnly || product.stock > 0;
        return matchesSection && matchesSearch && matchesStock;
      }),
      "draft",
    );
  }, [inStockOnly, products, searchQuery]);

  const inventoryCategories = useMemo(() => {
    return Array.from(new Set([...categoryOptions, ...products.map(product => product.category)])).sort();
  }, [products]);

  useEffect(() => {
    categoriesRef.current = inventoryCategories;
  }, [inventoryCategories]);

  const applyInventoryCommand = (command: InventoryVoiceCommand): AssistantActionResult => {
    const currentSession = sessionRef.current;
    if (!currentSession) {
      return {
        kind: "rejected",
        message: "Sign in again before using inventory voice actions.",
      };
    }

    if (command.kind === "search") {
      setSearchQuery(command.query);
      return {
        kind: "applied",
        message: `Updated inventory search to ${command.query}.`,
      };
    }

    if (command.kind === "clear_search") {
      setSearchQuery("");
      return {
        kind: "applied",
        message: "Cleared the inventory search.",
      };
    }

    if (command.kind === "set_in_stock") {
      setInStockOnly(command.value);
      return {
        kind: "applied",
        message: command.value ? "Enabled in-stock-only inventory filtering." : "Showing all stock states.",
      };
    }

    if (command.kind === "create_product") {
      return {
        kind: "confirm",
        message: `Create ${command.name} in ${command.category} for $${command.price.toFixed(2)} with ${command.stock} in stock?`,
        confirmLabel: "Create product",
        execute: async () => {
          try {
            const created = await createInventoryProduct(currentSession, {
              partyId: currentSession.contactEmail,
              name: command.name,
              price: command.price,
              unit: command.unitCode,
              description: "",
              category: command.category,
              availableUnits: command.stock,
              isVisible: command.isVisible,
              showSoldout: true,
              releaseDate: null,
            });
            const normalized = normalizeInventoryRecord(created);
            setProducts(current => [normalized, ...current]);
            setExpandedSections(current => ({ ...current, [normalized.section]: true }));

            return {
              kind: "applied",
              message: `Created ${normalized.name} in inventory.`,
            };
          } catch (error) {
            return {
              kind: "rejected",
              message: describeInventoryError(error, "Unable to create the inventory product."),
            };
          }
        },
      };
    }

    const product = productsRef.current.find(item => item.id === command.productId);
    if (!product?.productId) {
      return {
        kind: "rejected",
        message: "That inventory item could not be found.",
      };
    }
    const productId = product.productId;

    return {
      kind: "confirm",
      message: `Delete ${command.productName} from inventory?`,
      confirmLabel: "Delete product",
      execute: async () => {
        try {
          await deleteInventoryProduct(currentSession, productId);
          setProducts(current => current.filter(item => item.id !== product.id));
          return {
            kind: "applied",
            message: `Deleted ${command.productName} from inventory.`,
          };
        } catch (error) {
          return {
            kind: "rejected",
            message: describeInventoryError(error, "Unable to delete the inventory product."),
          };
        }
      },
    };
  };

  const startInventoryAssistantRequest = (transcript: string) => {
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
            message: "The inventory assistant timed out.",
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
    const socket = new WebSocket(inventoryAssistantWebSocketUrl);
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
              category: product.category,
              stock: product.stock,
            })),
            categories: categoriesRef.current,
            filters: {
              query: searchQueryRef.current,
              inStockOnly: inStockOnlyRef.current,
            },
          },
        }),
      );
    };

    const handleOpen = () => {
      sendContext("session.start");
    };

    const handleMessage = (event: MessageEvent<string>) => {
      const envelope = JSON.parse(event.data) as InventoryAssistantServerEnvelope;
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
          ? applyInventoryCommand(envelope.payload.command)
          : {
              kind: "rejected" as const,
              message: envelope.payload?.message ?? "I could not map that to an inventory action.",
            };
        resolver?.(result);
        return;
      }

      if (envelope.type === "error") {
        const resolver = assistantResultResolverRef.current;
        assistantResultResolverRef.current = null;
        resolver?.({
          kind: "rejected",
          message: envelope.payload?.message ?? "The inventory assistant could not respond.",
        });
      }
    };

    const handleClose = () => {
      setAssistantLiveTranscript(null);
      const resolver = assistantResultResolverRef.current;
      assistantResultResolverRef.current = null;
      resolver?.({
        kind: "rejected",
        message: "The inventory assistant disconnected.",
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
  }, [inventoryAssistantWebSocketUrl]);

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
            category: product.category,
            stock: product.stock,
          })),
          categories: inventoryCategories,
          filters: {
            query: searchQuery,
            inStockOnly,
          },
        },
      }),
    );
  }, [inStockOnly, inventoryCategories, products, searchQuery]);

  const handleInventoryVoiceTranscript = async (
    transcript: string,
  ): Promise<AssistantActionResult> => {
    if (!session) {
      return {
        kind: "rejected",
        message: "Sign in again before using inventory voice actions.",
      };
    }

    setAssistantLiveTranscript(null);
    const streamedResult = await startInventoryAssistantRequest(transcript);
    if (streamedResult) {
      return streamedResult;
    }

    const command = parseInventoryVoiceCommand(
      transcript,
      productsRef.current.map(product => ({ id: product.id, name: product.name })),
      categoriesRef.current,
    );

    if (!command) {
      return {
        kind: "rejected",
        message:
          "Try a more explicit inventory command, such as creating a named product or deleting an existing listing.",
      };
    }

    return applyInventoryCommand(command);
  };

  const handleInventoryVoicePartialTranscript = (transcript: string) => {
    const socket = assistantSocketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setAssistantLiveTranscript(transcript);
      return;
    }

    socket.send(JSON.stringify({ type: "transcript.partial", payload: { text: transcript } }));
  };

  const handleSave = async () => {
    if (!session) {
      setEditorError("Sign in again before saving products.");
      return;
    }

    setEditorBusy("save");
    setEditorError(null);

    try {
      if (editorMode.type === "edit") {
        const product = products.find(item => item.id === editorMode.productId);
        if (!product?.productId) {
          throw new Error("Missing product identifier.");
        }

        const updated = await updateInventoryProduct(session, product.productId, {
          name: editorForm.name.trim(),
          price: Number(editorForm.price),
          unit: editorForm.unitCode.trim() || "EA",
          description: editorForm.description.trim(),
          category: editorForm.category,
          availableUnits: Number(editorForm.stock),
          isVisible: editorForm.isVisible,
          showSoldout: editorForm.showSoldout,
          releaseDate: editorForm.launchDate || null,
        });

        const normalized = normalizeInventoryRecord(updated);
        setProducts(current =>
          current.map(item => (item.id === editorMode.productId ? normalized : item)),
        );
      } else {
        const created = await createInventoryProduct(session, {
          partyId: session.contactEmail,
          name: editorForm.name.trim(),
          price: Number(editorForm.price),
          unit: editorForm.unitCode.trim() || "EA",
          description: editorForm.description.trim(),
          category: editorForm.category,
          availableUnits: Number(editorForm.stock),
          isVisible: editorForm.isVisible,
          showSoldout: editorForm.showSoldout,
          releaseDate: editorForm.launchDate || null,
        });
        const normalized = normalizeInventoryRecord(created);
        setProducts(current => [normalized, ...current]);
        setExpandedSections(current => ({ ...current, [normalized.section]: true }));
      }

      closeEditor();
    } catch (error) {
      setEditorError(describeInventoryError(error, "Unable to save product."));
      setEditorBusy(null);
    }
  };

  const handleDelete = async () => {
    if (!session || editorMode.type !== "edit") {
      return;
    }

    const product = products.find(item => item.id === editorMode.productId);
    if (!product?.productId) {
      setEditorError("Missing product identifier.");
      return;
    }

    setEditorBusy("delete");
    setEditorError(null);

    try {
      await deleteInventoryProduct(session, product.productId);
      setProducts(current => current.filter(item => item.id !== editorMode.productId));
      closeEditor();
    } catch (error) {
      setEditorError(describeInventoryError(error, "Unable to delete product."));
      setEditorBusy(null);
    }
  };

  return (
    <div className="landing-root">
      <div className="landing-container">
        <section className="landing-stage">
          <AppHeader />

          <main className="inventory-page">
            <header className="inventory-page-header">
              <div>
                <h1>Inventory</h1>
                <p>Manage live products and draft listings without turning the page into a dashboard.</p>
              </div>

              <div className="inventory-toolbar">
                <label className="inventory-search">
                  <span className="inventory-search-icon" aria-hidden="true">
                    <Search size={16} strokeWidth={2.2} />
                  </span>
                  <input
                    type="search"
                    value={searchQuery}
                    onChange={event => setSearchQuery(event.target.value)}
                    placeholder="Search products"
                    aria-label="Search products"
                  />
                </label>

                <label className="inventory-filter-toggle">
                  <input
                    type="checkbox"
                    checked={inStockOnly}
                    onChange={event => setInStockOnly(event.target.checked)}
                  />
                  <span className="inventory-filter-toggle-mark" aria-hidden="true" />
                  <span>In stock only</span>
                </label>

                <button type="button" className="inventory-primary-action" onClick={openAddPanel}>
                  Add product
                </button>
              </div>
            </header>

            <VoiceAssistantDock
              context="inventory"
              hint='Try “find my tote listings”, “only show in-stock items”, “create a new linen tote for 31 dollars with 8 in stock in Fashion”, or “delete the ceramic mug listing”.'
              disabledReason={!session ? "Sign in again before using inventory voice actions." : null}
              liveTranscript={assistantLiveTranscript}
              streaming
              onPartialTranscript={handleInventoryVoicePartialTranscript}
              onTranscript={handleInventoryVoiceTranscript}
            />

            {pageError ? (
              <div className="inventory-section-shell" role="alert">
                <div className="inventory-empty-state">
                  <strong>Inventory could not be loaded.</strong>
                  <span>{pageError}</span>
                </div>
              </div>
            ) : loading ? (
              <div className="inventory-section-shell">
                <div className="inventory-empty-state">
                  <strong>Loading inventory…</strong>
                </div>
              </div>
            ) : (
              <div className="inventory-content">
                <div className="inventory-sections">
                  <InventorySectionBlock
                    title="Launched"
                    helper="Visible to buyers right now"
                    products={filteredLaunched}
                    expanded={expandedSections.launched}
                    onToggleExpanded={() =>
                      setExpandedSections(current => ({
                        ...current,
                        launched: !current.launched,
                      }))
                    }
                    onEdit={openEditPanel}
                  />

                  <InventorySectionBlock
                    title="Draft listings"
                    helper="Hidden from buyers until their launch date"
                    products={filteredDraft}
                    expanded={expandedSections.draft}
                    onToggleExpanded={() =>
                      setExpandedSections(current => ({
                        ...current,
                        draft: !current.draft,
                      }))
                    }
                    onEdit={openEditPanel}
                  />
                </div>
              </div>
            )}

            <div
              className="inventory-editor-backdrop"
              data-open={editorMode.type === "closed" ? "false" : "true"}
              onClick={closeEditor}
            />

            <aside
              className="inventory-editor-panel"
              data-open={editorMode.type === "closed" ? "false" : "true"}
              aria-hidden={editorMode.type === "closed"}
            >
              <div className="inventory-editor-header">
                <div>
                  <h2>
                    {editorMode.type === "edit"
                      ? "Edit product"
                      : editorMode.type === "add"
                        ? "Add product"
                        : "Product editor"}
                  </h2>
                  <p>
                    {editorMode.type === "closed"
                      ? "Choose Add product or open a card menu to start editing."
                      : "Edit live stock, release timing, and catalogue visibility."}
                  </p>
                </div>
                <button
                  type="button"
                  className="inventory-editor-close"
                  onClick={closeEditor}
                  aria-label="Close product editor"
                >
                  <X size={18} strokeWidth={2.2} />
                </button>
              </div>

              {editorMode.type === "closed" ? (
                <div className="inventory-editor-empty">
                  <ImagePlus size={22} strokeWidth={2.1} />
                  <strong>No listing selected</strong>
                  <span>Use Add product or a card menu to open the shared form.</span>
                </div>
              ) : (
                <div className="inventory-editor-form">
                  <label className="inventory-field">
                    <span>Product name</span>
                    <input
                      value={editorForm.name}
                      onChange={event =>
                        setEditorForm(current => ({ ...current, name: event.target.value }))
                      }
                    />
                  </label>

                  <div className="inventory-field-grid">
                    <label className="inventory-field">
                      <span>Price</span>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={editorForm.price}
                        onChange={event =>
                          setEditorForm(current => ({ ...current, price: event.target.value }))
                        }
                      />
                    </label>

                    <label className="inventory-field">
                      <span>Stock quantity</span>
                      <input
                        type="number"
                        min="0"
                        step="1"
                        value={editorForm.stock}
                        onChange={event =>
                          setEditorForm(current => ({ ...current, stock: event.target.value }))
                        }
                      />
                    </label>
                  </div>

                  <div className="inventory-field-grid">
                    <label className="inventory-field">
                      <span>Unit code</span>
                      <input
                        value={editorForm.unitCode}
                        onChange={event =>
                          setEditorForm(current => ({ ...current, unitCode: event.target.value }))
                        }
                      />
                    </label>

                    <label className="inventory-field">
                      <span>Launch date</span>
                      <input
                        type="date"
                        value={editorForm.launchDate}
                        onChange={event =>
                          setEditorForm(current => ({ ...current, launchDate: event.target.value }))
                        }
                      />
                    </label>
                  </div>

                  <label className="inventory-field">
                    <span>Category</span>
                    <select
                      value={editorForm.category}
                      onChange={event =>
                        setEditorForm(current => ({ ...current, category: event.target.value }))
                      }
                    >
                      {categoryOptions.map(option => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="inventory-field">
                    <span>Description</span>
                    <textarea
                      rows={4}
                      value={editorForm.description}
                      onChange={event =>
                        setEditorForm(current => ({ ...current, description: event.target.value }))
                      }
                    />
                  </label>

                  <div className="inventory-toggle-grid">
                    <label className="inventory-filter-toggle">
                      <input
                        type="checkbox"
                        checked={editorForm.isVisible}
                        onChange={event =>
                          setEditorForm(current => ({ ...current, isVisible: event.target.checked }))
                        }
                      />
                      <span className="inventory-filter-toggle-mark" aria-hidden="true" />
                      <span>Visible now</span>
                    </label>

                    <label className="inventory-filter-toggle">
                      <input
                        type="checkbox"
                        checked={editorForm.showSoldout}
                        onChange={event =>
                          setEditorForm(current => ({
                            ...current,
                            showSoldout: event.target.checked,
                          }))
                        }
                      />
                      <span className="inventory-filter-toggle-mark" aria-hidden="true" />
                      <span>Show when sold out</span>
                    </label>
                  </div>

                  <div className="inventory-upload-slot" role="button" tabIndex={0}>
                    <ImagePlus size={18} strokeWidth={2.1} />
                    <span>Image upload wiring is the next pass.</span>
                  </div>

                  {editorError ? (
                    <div className="inventory-editor-error" role="alert">
                      {editorError}
                    </div>
                  ) : null}

                  <div className="inventory-editor-actions">
                    <button
                      type="button"
                      className="inventory-primary-action"
                      onClick={() => {
                        void handleSave();
                      }}
                      disabled={editorBusy !== null}
                    >
                      {editorBusy === "save" ? "Saving..." : "Save product"}
                    </button>
                    {editorMode.type === "edit" ? (
                      <button
                        type="button"
                        className="inventory-danger-action"
                        onClick={() => {
                          void handleDelete();
                        }}
                        disabled={editorBusy !== null}
                      >
                        <Trash2 size={16} strokeWidth={2.1} />
                        {editorBusy === "delete" ? "Deleting..." : "Delete"}
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="inventory-secondary-action"
                      onClick={closeEditor}
                      disabled={editorBusy !== null}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </aside>
          </main>
        </section>
      </div>
    </div>
  );
}
