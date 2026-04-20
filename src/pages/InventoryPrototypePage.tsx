import { useMemo, useState } from "react";
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
  X,
} from "lucide-react";
import { AppHeader } from "../components/AppHeader";
import "./inventory-prototype.css";

type InventorySection = "launched" | "draft";

type InventoryProduct = {
  id: string;
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
};

const initialLaunchedProducts: InventoryProduct[] = [
  {
    id: "launch-denim-jacket",
    name: "Vintage denim jacket",
    price: 62,
    stock: 12,
    unitCode: "EA",
    status: "Low stock",
    section: "launched",
    dateLabel: "Since 14 Apr 2026",
    sortDate: "2026-04-14",
    tone: "mint",
    icon: Shirt,
  },
  {
    id: "launch-soy-candle",
    name: "Soy candle set",
    price: 28,
    stock: 4,
    unitCode: "EA",
    status: "Limited",
    section: "launched",
    dateLabel: "Since 17 Apr 2026",
    sortDate: "2026-04-17",
    tone: "gold",
    icon: Sparkles,
  },
  {
    id: "launch-ceramic-mug",
    name: "Ceramic mug",
    price: 34,
    stock: 40,
    unitCode: "EA",
    status: "Live",
    section: "launched",
    dateLabel: "Since 08 Apr 2026",
    sortDate: "2026-04-08",
    tone: "peach",
    icon: Coffee,
  },
  {
    id: "launch-market-tote",
    name: "Market tote bag",
    price: 31,
    stock: 18,
    unitCode: "EA",
    status: "Live",
    section: "launched",
    dateLabel: "Since 02 Apr 2026",
    sortDate: "2026-04-02",
    tone: "mint",
    icon: Package2,
  },
];

const initialDraftProducts: InventoryProduct[] = [
  {
    id: "draft-wall-print",
    name: "Abstract wall print",
    price: 46,
    stock: 40,
    unitCode: "EA",
    status: "Draft",
    section: "draft",
    dateLabel: "Launches 22 Apr 2026",
    sortDate: "2026-04-22",
    tone: "peach",
    icon: Palette,
  },
  {
    id: "draft-weekend-tote",
    name: "Weekend tote bag",
    price: 31,
    stock: 18,
    unitCode: "EA",
    status: "Draft",
    section: "draft",
    dateLabel: "Launches 28 Apr 2026",
    sortDate: "2026-04-28",
    tone: "mint",
    icon: Package2,
  },
  {
    id: "draft-linen-runner",
    name: "Linen table runner",
    price: 25,
    stock: 24,
    unitCode: "EA",
    status: "Draft",
    section: "draft",
    dateLabel: "Launches 02 May 2026",
    sortDate: "2026-05-02",
    tone: "gold",
    icon: Shirt,
  },
  {
    id: "draft-ceramic-bowl",
    name: "Ceramic serving bowl",
    price: 52,
    stock: 16,
    unitCode: "EA",
    status: "Draft",
    section: "draft",
    dateLabel: "Launches 10 May 2026",
    sortDate: "2026-05-10",
    tone: "peach",
    icon: Coffee,
  },
];

const emptyForm: EditorForm = {
  name: "",
  price: "",
  stock: "",
  unitCode: "EA",
  launchDate: "2026-05-01",
};

function formatPrice(value: number): string {
  return `$${value.toFixed(0)}`;
}

function formatLaunchLabel(date: string): string {
  const parsed = new Date(`${date}T00:00:00`);
  const formatter = new Intl.DateTimeFormat("en-AU", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
  return `Launches ${formatter.format(parsed)}`;
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
      : product.status === "Limited"
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

      <div
        className="inventory-product-grid"
        data-expanded={expanded ? "true" : "false"}
      >
        {products.map(product => (
          <InventoryCard key={product.id} product={product} onEdit={onEdit} />
        ))}
      </div>
    </section>
  );
}

export function InventoryPrototypePage() {
  const [launchedProducts, setLaunchedProducts] = useState<InventoryProduct[]>(initialLaunchedProducts);
  const [draftProducts, setDraftProducts] = useState<InventoryProduct[]>(initialDraftProducts);
  const [searchQuery, setSearchQuery] = useState("");
  const [inStockOnly, setInStockOnly] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Record<InventorySection, boolean>>({
    launched: false,
    draft: false,
  });
  const [editorMode, setEditorMode] = useState<EditorMode>({ type: "closed" });
  const [editorForm, setEditorForm] = useState<EditorForm>(emptyForm);

  const allProducts = useMemo(
    () => [...launchedProducts, ...draftProducts],
    [draftProducts, launchedProducts],
  );

  const openAddPanel = () => {
    setEditorMode({ type: "add" });
    setEditorForm(emptyForm);
  };

  const openEditPanel = (productId: string) => {
    const product = allProducts.find(item => item.id === productId);
    if (!product) {
      return;
    }

    setEditorMode({ type: "edit", productId });
    setEditorForm({
      name: product.name,
      price: String(product.price),
      stock: String(product.stock),
      unitCode: product.unitCode,
      launchDate: product.sortDate,
    });
  };

  const closeEditor = () => {
    setEditorMode({ type: "closed" });
  };

  const filteredLaunched = useMemo(() => {
    return sortProducts(
      launchedProducts.filter(product => {
        const matchesSearch = product.name.toLowerCase().includes(searchQuery.toLowerCase());
        const matchesStock = !inStockOnly || product.stock > 0;
        return matchesSearch && matchesStock;
      }),
      "launched",
    );
  }, [inStockOnly, launchedProducts, searchQuery]);

  const filteredDraft = useMemo(() => {
    return sortProducts(
      draftProducts.filter(product => {
        const matchesSearch = product.name.toLowerCase().includes(searchQuery.toLowerCase());
        const matchesStock = !inStockOnly || product.stock > 0;
        return matchesSearch && matchesStock;
      }),
      "draft",
    );
  }, [draftProducts, inStockOnly, searchQuery]);

  const handleSave = () => {
    const normalizedProduct: InventoryProduct = {
      id:
        editorMode.type === "edit"
          ? editorMode.productId
          : `draft-${editorForm.name.toLowerCase().replace(/\s+/g, "-") || Date.now()}`,
      name: editorForm.name || "Untitled product",
      price: Number(editorForm.price || 0),
      stock: Number(editorForm.stock || 0),
      unitCode: editorForm.unitCode || "EA",
      status: editorMode.type === "edit" ? "Draft" : "Draft",
      section: "draft",
      dateLabel: formatLaunchLabel(editorForm.launchDate || emptyForm.launchDate),
      sortDate: editorForm.launchDate || emptyForm.launchDate,
      tone: "mint",
      icon: Package2,
    };

    if (editorMode.type === "edit") {
      const update = (products: InventoryProduct[]) =>
        products.map(product =>
          product.id === editorMode.productId
            ? {
                ...product,
                name: normalizedProduct.name,
                price: normalizedProduct.price,
                stock: normalizedProduct.stock,
                unitCode: normalizedProduct.unitCode,
                dateLabel:
                  product.section === "draft"
                    ? normalizedProduct.dateLabel
                    : product.dateLabel,
                sortDate:
                  product.section === "draft"
                    ? normalizedProduct.sortDate
                    : product.sortDate,
              }
            : product,
        );
      setLaunchedProducts(update);
      setDraftProducts(update);
    } else {
      setDraftProducts(current => sortProducts([normalizedProduct, ...current], "draft"));
      setExpandedSections(current => ({ ...current, draft: true }));
    }

    closeEditor();
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
                      : "Shared editor for launched items and draft listings."}
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
                        value={editorForm.price}
                        onChange={event =>
                          setEditorForm(current => ({ ...current, price: event.target.value }))
                        }
                      />
                    </label>

                    <label className="inventory-field">
                      <span>Stock quantity</span>
                      <input
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

                  <div className="inventory-upload-slot" role="button" tabIndex={0}>
                    <ImagePlus size={18} strokeWidth={2.1} />
                    <span>Image placeholder / upload slot</span>
                  </div>

                  <div className="inventory-editor-actions">
                    <button type="button" className="inventory-primary-action" onClick={handleSave}>
                      Save product
                    </button>
                    <button type="button" className="inventory-secondary-action" onClick={closeEditor}>
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
