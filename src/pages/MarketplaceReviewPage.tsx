import { useEffect, useMemo, useState } from "react";
import { AppHeader } from "../components/AppHeader";
import { AppLink, navigate } from "../components/AppLink";
import { VoiceAssistantDock } from "../components/VoiceAssistantDock";
import { convertTranscriptToOrderPayload, createOrder, submitOrder } from "../orderApi";
import { useStoredSession } from "../session";
import {
  calculateCartTotal,
  clearStoredMarketplaceCart,
  clearStoredMarketplaceCheckoutSuccess,
  groupMarketplaceCartLines,
  readStoredMarketplaceCart,
  type MarketplacePlacedOrder,
  type MarketplaceSellerOrderGroup,
  writeStoredMarketplaceCheckoutSuccess,
} from "./marketplacePrototypeData";
import {
  buildCheckoutAssistantPayload,
  parseCheckoutVoiceCommand,
  summarizeCheckoutFieldMutations,
  type AssistantActionResult,
} from "../voiceAssistant";
import "./marketplace-prototype.css";

type CheckoutFailure = {
  seller: string;
  message: string;
};

type CheckoutMode = "draft" | "submit";

type PlaceOrdersResult = {
  success: boolean;
  createdOrders: MarketplacePlacedOrder[];
  failures: CheckoutFailure[];
  errorMessage: string | null;
};

function formatPrice(value: number): string {
  return `$${value.toFixed(0)}`;
}

function getLocalDateString(offsetDays = 0): string {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function describeCheckoutError(error: unknown, prefix: string, fallbackMessage: string): string {
  if (!(error instanceof Error) || !error.message.startsWith(prefix)) {
    return fallbackMessage;
  }

  const separatorIndex = error.message.indexOf(":", prefix.length);
  if (separatorIndex === -1) {
    return fallbackMessage;
  }

  const detail = error.message.slice(separatorIndex + 1).trim();
  return detail || fallbackMessage;
}

function buildFailureMessage(error: unknown, mode: CheckoutMode): string {
  if (error instanceof Error && error.message.startsWith("order-create:")) {
    return describeCheckoutError(
      error,
      "order-create:",
      mode === "draft" ? "Unable to create the draft order." : "Unable to create the order.",
    );
  }

  if (mode === "submit" && error instanceof Error && error.message.startsWith("order-submit:")) {
    return describeCheckoutError(error, "order-submit:", "Unable to submit the order.");
  }

  return mode === "draft"
    ? "Unable to create this seller draft right now."
    : "Unable to place this seller order right now.";
}

function buildGroupedOrderPayload(
  group: MarketplaceSellerOrderGroup,
  buyerEmail: string,
  buyerName: string,
  form: {
    street: string;
    city: string;
    state: string;
    postcode: string;
    country: string;
    requestedDate: string;
    notes: string;
    issueDate: string;
    currency: string;
  },
) {
  return {
    buyerEmail,
    buyerName,
    sellerEmail: group.sellerEmail,
    sellerName: group.seller,
    currency: form.currency,
    issueDate: form.issueDate,
    notes: form.notes.trim() || null,
    delivery: {
      street: form.street.trim(),
      city: form.city.trim(),
      state: form.state.trim(),
      postcode: form.postcode.trim(),
      country: form.country.trim(),
      requestedDate: form.requestedDate.trim(),
    },
    lines: group.lines.map(line => ({
      productId: line.productRecordId,
      productName: line.name,
      quantity: line.quantity,
      unitCode: line.unitCode,
      unitPrice: line.unitPrice.toFixed(2),
    })),
  };
}

export function MarketplaceReviewPage() {
  const storedSession = useStoredSession();
  const cart = readStoredMarketplaceCart();
  const groupedOrders = useMemo(
    () => groupMarketplaceCartLines(cart.lines),
    [cart.lines],
  );
  const total = useMemo(() => calculateCartTotal(cart.lines), [cart.lines]);
  const [buyerName, setBuyerName] = useState(storedSession?.partyName ?? "");
  const [street, setStreet] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [postcode, setPostcode] = useState("");
  const [country, setCountry] = useState("AU");
  const [requestedDate, setRequestedDate] = useState(getLocalDateString(7));
  const [notes, setNotes] = useState("");
  const [issueDate] = useState(getLocalDateString());
  const [currency] = useState("AUD");
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [checkoutFailures, setCheckoutFailures] = useState<CheckoutFailure[]>([]);
  const [partialOrders, setPartialOrders] = useState<MarketplacePlacedOrder[]>([]);
  const [submittingMode, setSubmittingMode] = useState<CheckoutMode | null>(null);

  useEffect(() => {
    if (storedSession?.partyName) {
      setBuyerName(current => current || storedSession.partyName);
    }
  }, [storedSession?.partyName]);

  const applyCheckoutPayload = (payload: ReturnType<typeof buildCheckoutAssistantPayload>) => {
    const nextState = {
      buyerName: payload.buyerName,
      street: payload.delivery?.street ?? "",
      city: payload.delivery?.city ?? "",
      state: payload.delivery?.state ?? "",
      postcode: payload.delivery?.postcode ?? "",
      country: payload.delivery?.country ?? "",
      requestedDate: payload.delivery?.requestedDate ?? "",
      notes: payload.notes ?? "",
    };

    const previousState = {
      buyerName,
      street,
      city,
      state,
      postcode,
      country,
      requestedDate,
      notes,
    };
    const summaries = summarizeCheckoutFieldMutations(previousState, nextState);

    setBuyerName(nextState.buyerName);
    setStreet(nextState.street);
    setCity(nextState.city);
    setState(nextState.state);
    setPostcode(nextState.postcode);
    setCountry(nextState.country);
    setRequestedDate(nextState.requestedDate);
    setNotes(nextState.notes);

    return summaries;
  };

  const validateForm = () => {
    const missingFields: string[] = [];
    if (!storedSession?.contactEmail) {
      missingFields.push("signed-in buyer email");
    }
    if (!buyerName.trim()) {
      missingFields.push("buyer name");
    }
    if (!street.trim()) {
      missingFields.push("delivery street");
    }
    if (!city.trim()) {
      missingFields.push("delivery city");
    }
    if (!state.trim()) {
      missingFields.push("delivery state");
    }
    if (!postcode.trim()) {
      missingFields.push("delivery postcode");
    }
    if (!country.trim()) {
      missingFields.push("delivery country");
    }
    if (!requestedDate.trim()) {
      missingFields.push("requested delivery date");
    }
    return missingFields;
  };

  const processOrders = async (mode: CheckoutMode): Promise<PlaceOrdersResult> => {
    if (!storedSession) {
      const message =
        mode === "draft"
          ? "Sign in again before saving draft orders."
          : "Sign in again before placing the order.";
      setCheckoutError(message);
      return { success: false, createdOrders: [], failures: [], errorMessage: message };
    }

    if (groupedOrders.length === 0) {
      const message =
        mode === "draft"
          ? "Add products in the marketplace before saving draft orders."
          : "Add products in the marketplace before placing an order.";
      setCheckoutError(message);
      return { success: false, createdOrders: [], failures: [], errorMessage: message };
    }

    const missingFields = validateForm();
    if (missingFields.length > 0) {
      const message = `Complete the required checkout fields: ${missingFields.join(", ")}.`;
      setCheckoutError(message);
      return { success: false, createdOrders: [], failures: [], errorMessage: message };
    }

    setSubmittingMode(mode);
    setCheckoutError(null);
    setCheckoutFailures([]);
    setPartialOrders([]);
    clearStoredMarketplaceCheckoutSuccess();

    const createdOrders: MarketplacePlacedOrder[] = [];
    const failures: CheckoutFailure[] = [];

    for (const group of groupedOrders) {
      try {
        const payload = buildGroupedOrderPayload(
          group,
          storedSession.contactEmail,
          buyerName.trim(),
          {
            street,
            city,
            state,
            postcode,
            country,
            requestedDate,
            notes,
            issueDate,
            currency,
          },
        );
        const created = await createOrder(storedSession, payload);
        if (mode === "submit") {
          await submitOrder(storedSession, created.orderId);
        }
        createdOrders.push({
          orderId: created.orderId,
          seller: group.seller,
          sellerEmail: group.sellerEmail,
          itemCount: group.itemCount,
          total: group.total,
        });
      } catch (error) {
        failures.push({
          seller: group.seller,
          message: buildFailureMessage(error, mode),
        });
      }
    }

    setSubmittingMode(null);

    if (failures.length > 0) {
      const errorMessage =
        mode === "draft"
          ? "Some seller draft orders could not be created. The cart has been left intact."
          : "Some seller orders could not be placed. The cart has been left intact.";
      setCheckoutError(errorMessage);
      setCheckoutFailures(failures);
      setPartialOrders(createdOrders);
      return {
        success: false,
        createdOrders,
        failures,
        errorMessage,
      };
    }

    clearStoredMarketplaceCart();

    if (createdOrders.length === 1) {
      navigate(`/orders/${createdOrders[0]!.orderId}/edit`);
      return { success: true, createdOrders, failures: [], errorMessage: null };
    }

    if (mode === "draft") {
      navigate("/orders");
      return { success: true, createdOrders, failures: [], errorMessage: null };
    }

    writeStoredMarketplaceCheckoutSuccess({
      buyerName: buyerName.trim(),
      orders: createdOrders,
    });
    navigate("/marketplace/success");
    return { success: true, createdOrders, failures: [], errorMessage: null };
  };

  const placeOrders = async (): Promise<PlaceOrdersResult> => processOrders("submit");

  const saveDraftOrders = async (): Promise<PlaceOrdersResult> => processOrders("draft");

  const handleCheckoutVoiceTranscript = async (
    transcript: string,
  ): Promise<AssistantActionResult> => {
    const checkoutCommand = parseCheckoutVoiceCommand(transcript);
    if (checkoutCommand?.kind === "save_checkout_draft") {
      const result = await saveDraftOrders();
      if (!result.success) {
        const failureSummary =
          result.failures.length > 0
            ? ` ${result.failures.map(failure => `${failure.seller}: ${failure.message}`).join(" ")}`
            : "";
        return {
          kind: "rejected",
          message:
            result.errorMessage ??
            `The checkout assistant could not save the draft order.${failureSummary}`.trim(),
        };
      }

      return {
        kind: "applied",
        message:
          result.createdOrders.length > 1
            ? `Saved ${result.createdOrders.length} seller drafts.`
            : "Saved the draft order.",
      };
    }

    if (checkoutCommand?.kind === "submit_checkout") {
      const result = await placeOrders();
      if (!result.success) {
        const failureSummary =
          result.failures.length > 0
            ? ` ${result.failures.map(failure => `${failure.seller}: ${failure.message}`).join(" ")}`
            : "";
        return {
          kind: "rejected",
          message:
            result.errorMessage ??
            `The checkout assistant could not place the order.${failureSummary}`.trim(),
        };
      }

      return {
        kind: "applied",
        message:
          result.createdOrders.length > 1
            ? `Placed ${result.createdOrders.length} seller orders.`
            : "Placed the order.",
      };
    }

    if (!storedSession) {
      return {
        kind: "rejected",
        message: "Sign in again before using checkout voice actions.",
      };
    }

    const primaryGroup = groupedOrders[0];
    if (!primaryGroup) {
      return {
        kind: "rejected",
        message: "Add items to the cart before using checkout voice actions.",
      };
    }

    const currentPayload = buildCheckoutAssistantPayload({
      buyerEmail: storedSession.contactEmail,
      buyerName,
      sellerEmail: primaryGroup.sellerEmail,
      sellerName: primaryGroup.seller,
      street,
      city,
      state,
      postcode,
      country,
      requestedDate,
      notes,
      issueDate,
      currency,
      lines: primaryGroup.lines.map(line => ({
        productId: line.productRecordId,
        productName: line.name,
        quantity: line.quantity,
        unitCode: line.unitCode,
        unitPrice: line.unitPrice.toFixed(2),
      })),
    });

    try {
      const result = await convertTranscriptToOrderPayload(storedSession, transcript, currentPayload);
      if (!result.payload) {
        return {
          kind: "rejected",
          message:
            result.issues[0] ??
            "The assistant could not derive checkout changes from that transcript.",
        };
      }

      const nextPayload = buildCheckoutAssistantPayload({
        buyerEmail: storedSession.contactEmail,
        buyerName: result.payload.buyerName,
        sellerEmail: primaryGroup.sellerEmail,
        sellerName: primaryGroup.seller,
        street: result.payload.delivery?.street ?? "",
        city: result.payload.delivery?.city ?? "",
        state: result.payload.delivery?.state ?? "",
        postcode: result.payload.delivery?.postcode ?? "",
        country: result.payload.delivery?.country ?? "",
        requestedDate: result.payload.delivery?.requestedDate ?? "",
        notes: result.payload.notes ?? "",
        issueDate,
        currency,
        lines: primaryGroup.lines.map(line => ({
          productId: line.productRecordId,
          productName: line.name,
          quantity: line.quantity,
          unitCode: line.unitCode,
          unitPrice: line.unitPrice.toFixed(2),
        })),
      });

      const summaries = applyCheckoutPayload(nextPayload);
      if (summaries.length === 0) {
        return {
          kind: "rejected",
          message: "No checkout fields changed from that transcript.",
        };
      }

      return {
        kind: "applied",
        message: summaries.join(" "),
      };
    } catch (error) {
      if (error instanceof Error && error.message.startsWith("order-convert:")) {
        const detail = error.message.slice(error.message.lastIndexOf(":") + 1).trim();
        return {
          kind: "rejected",
          message: detail || "The checkout assistant could not apply that transcript.",
        };
      }

      return {
        kind: "rejected",
        message: "The checkout assistant could not apply that transcript.",
      };
    }
  };

  return (
    <div className="landing-root">
      <div className="landing-container">
        <section className="landing-stage">
          <AppHeader />

          <main className="marketplace-page marketplace-review-page">
            <section className="marketplace-review-shell" aria-labelledby="marketplace-review-title">
              <div className="marketplace-review-header">
                <div>
                  <p className="marketplace-review-eyebrow">Marketplace checkout</p>
                  <h1 id="marketplace-review-title">Review your order</h1>
                </div>
                <div className="marketplace-review-pill-stack">
                  <span className="marketplace-count-chip">{cart.lines.length} lines selected</span>
                  <span className="marketplace-count-chip">{formatPrice(total)} total</span>
                </div>
              </div>

              <VoiceAssistantDock
                context="checkout"
                hint="Try “deliver to 123 Harbour Street next Tuesday”, “save as draft”, or “place order”."
                disabledReason={cart.lines.length === 0 ? "Add items before using checkout voice actions." : null}
                autoRestart
                onTranscript={handleCheckoutVoiceTranscript}
              />

              {cart.lines.length === 0 ? (
                <div className="marketplace-empty-state">
                  <strong>No items are ready for checkout.</strong>
                  <span>Add products in the marketplace before moving to this step.</span>
                </div>
              ) : (
                <>
                  <section className="marketplace-checkout-layout" aria-label="Checkout details">
                    <div className="marketplace-checkout-form">
                      <div className="marketplace-checkout-card">
                        <div className="marketplace-checkout-card-heading">
                          <h2>Buyer</h2>
                        </div>

                        <label className="marketplace-form-field">
                          <span>Buyer email</span>
                          <input type="email" value={storedSession?.contactEmail ?? ""} readOnly />
                        </label>

                        <label className="marketplace-form-field">
                          <span>Buyer name</span>
                          <input
                            type="text"
                            value={buyerName}
                            onChange={event => setBuyerName(event.target.value)}
                            placeholder="Buyer display name"
                          />
                        </label>
                      </div>

                      <div className="marketplace-checkout-card">
                        <div className="marketplace-checkout-card-heading">
                          <h2>Delivery</h2>
                        </div>

                        <div className="marketplace-form-grid">
                          <label className="marketplace-form-field marketplace-form-field-wide">
                            <span>Street</span>
                            <input
                              type="text"
                              value={street}
                              onChange={event => setStreet(event.target.value)}
                              placeholder="123 Harbour Street"
                            />
                          </label>

                          <label className="marketplace-form-field">
                            <span>City</span>
                            <input
                              type="text"
                              value={city}
                              onChange={event => setCity(event.target.value)}
                              placeholder="Sydney"
                            />
                          </label>

                          <label className="marketplace-form-field">
                            <span>State</span>
                            <input
                              type="text"
                              value={state}
                              onChange={event => setState(event.target.value)}
                              placeholder="NSW"
                            />
                          </label>

                          <label className="marketplace-form-field">
                            <span>Postcode</span>
                            <input
                              type="text"
                              value={postcode}
                              onChange={event => setPostcode(event.target.value)}
                              placeholder="2000"
                            />
                          </label>

                          <label className="marketplace-form-field">
                            <span>Country</span>
                            <input
                              type="text"
                              value={country}
                              onChange={event => setCountry(event.target.value)}
                              placeholder="AU"
                            />
                          </label>

                          <label className="marketplace-form-field">
                            <span>Requested date</span>
                            <input
                              type="date"
                              value={requestedDate}
                              onChange={event => setRequestedDate(event.target.value)}
                            />
                          </label>
                        </div>

                        <label className="marketplace-form-field">
                          <span>Notes</span>
                          <textarea
                            value={notes}
                            onChange={event => setNotes(event.target.value)}
                            placeholder="Optional delivery or fulfilment notes"
                            rows={4}
                          />
                        </label>

                        <div className="marketplace-checkout-meta">
                          <span>Issue date: {issueDate}</span>
                          <span>Currency: {currency}</span>
                        </div>
                      </div>
                    </div>

                    <div className="marketplace-review-groups">
                      {groupedOrders.map(group => (
                        <section key={group.sellerEmail} className="marketplace-checkout-card">
                          <div className="marketplace-checkout-card-heading">
                            <div>
                              <h2>{group.seller}</h2>
                              <p>{group.itemCount} items in this seller order.</p>
                            </div>
                            <span className="marketplace-count-chip">{formatPrice(group.total)}</span>
                          </div>

                          <div className="marketplace-review-lines">
                            {group.lines.map(line => (
                              <article key={line.productId} className="marketplace-review-line">
                                <div>
                                  <strong>{line.name}</strong>
                                  <span>
                                    {line.quantity} × {formatPrice(line.unitPrice)}
                                  </span>
                                </div>
                                <strong>{formatPrice(line.subtotal)}</strong>
                              </article>
                            ))}
                          </div>
                        </section>
                      ))}
                    </div>
                  </section>

                  {checkoutError ? (
                    <div className="marketplace-checkout-feedback" role="alert">
                  <strong>{checkoutError}</strong>
                      {checkoutFailures.length > 0 ? (
                        <ul className="marketplace-checkout-feedback-list">
                          {checkoutFailures.map(failure => (
                            <li key={`${failure.seller}-${failure.message}`}>
                              {failure.seller}: {failure.message}
                            </li>
                          ))}
                        </ul>
                      ) : null}
                      {partialOrders.length > 0 ? (
                        <div className="marketplace-partial-success">
                          <span>Orders already created:</span>
                          <div className="marketplace-partial-success-links">
                            {partialOrders.map(order => (
                              <AppLink
                                key={order.orderId}
                                href={`/orders/${order.orderId}/edit`}
                                className="marketplace-inline-link"
                              >
                                {order.seller}
                              </AppLink>
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </>
              )}

              <div className="marketplace-review-actions">
                <AppLink href="/marketplace" className="marketplace-secondary-action">
                  Back to marketplace
                </AppLink>
                <button
                  type="button"
                  className="marketplace-secondary-action"
                  onClick={() => {
                    void saveDraftOrders();
                  }}
                  disabled={cart.lines.length === 0 || submittingMode !== null}
                >
                  {submittingMode === "draft"
                    ? groupedOrders.length > 1
                      ? "Saving drafts..."
                      : "Saving draft..."
                    : groupedOrders.length > 1
                      ? "Save as drafts"
                      : "Save as draft"}
                </button>
                <button
                  type="button"
                  className="marketplace-primary-action"
                  onClick={() => {
                    void placeOrders();
                  }}
                  disabled={cart.lines.length === 0 || submittingMode !== null}
                >
                  {submittingMode === "submit"
                    ? "Placing orders..."
                    : groupedOrders.length > 1
                      ? "Place orders"
                      : "Place order"}
                </button>
              </div>
            </section>
          </main>
        </section>
      </div>
    </div>
  );
}
