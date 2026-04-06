from __future__ import annotations

from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any

from app.models.schemas import OrderRequest
from app.services.ubl_order import generate_order_id, generate_ubl_order_xml

ORDERS: dict[str, dict[str, Any]] = OrderedDict()
DEFAULT_ORDER_LIST_LIMIT = 20
DEFAULT_ORDER_LIST_OFFSET = 0
MAX_ORDER_LIST_LIMIT = 100
MAX_CACHED_ORDERS = 256


class OrderPersistenceError(RuntimeError):
    """Raised when the database verification step fails."""


class OrderNotFoundError(KeyError):
    """Raised when the requested orderId does not exist."""


class OrderConflictLockedError(ValueError):
    """Raised when the order cannot be updated/deleted due to its current state."""


def now_z() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def create_order_record(req: OrderRequest) -> dict[str, Any]:
    order_id = generate_order_id()
    created_at = now_z()
    ubl_xml = generate_ubl_order_xml(order_id, req)

    record = {
        "orderId": order_id,
        "status": "DRAFT",
        "createdAt": created_at,
        "updatedAt": created_at,
        "payload": req.model_dump(mode="json"),
        "ublXml": ubl_xml,
    }
    db_order_id = persist_order_to_database(req)
    record["dbOrderId"] = str(db_order_id)
    try:
        persist_order_runtime_metadata_to_database(
            db_order_id,
            external_order_id=order_id,
            ubl_xml=ubl_xml,
            created_at=created_at,
            updated_at=created_at,
        )
    except Exception:
        _rollback_created_order(db_order_id)
        raise
    _cache_order_record(order_id, record)
    return record


def build_order_response(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "orderId": record["orderId"],
        "status": record["status"],
        "createdAt": record["createdAt"],
        "ublXml": record["ublXml"],
    }


def delete_order_record(order_id: str) -> bool:
    record = get_order_record(order_id)
    if record is None:
        return False

    db_order_id = record.get("dbOrderId")
    if db_order_id:
        from app.other import deleteOrder

        try:
            deleteOrder(db_order_id)
        except Exception as exc:  # noqa: BLE001
            raise OrderPersistenceError("Order could not be deleted from Supabase.") from exc

    ORDERS.pop(order_id, None)
    return True


def get_order_record(order_id: str) -> dict[str, Any] | None:
    existing = ORDERS.get(order_id)
    if existing is not None:
        return existing

    record = load_order_record_from_database(order_id)
    if record is None:
        return None

    _cache_order_record(order_id, record)
    return record


def list_orders_for_party(
    current_party_email: str,
    *,
    limit: int = DEFAULT_ORDER_LIST_LIMIT,
    offset: int = DEFAULT_ORDER_LIST_OFFSET,
) -> dict[str, Any]:
    normalized_email = _normalize_email(current_party_email)
    if normalized_email is None:
        return {
            "items": [],
            "page": {"limit": limit, "offset": offset, "hasMore": False, "total": 0},
        }

    rows = _fetch_order_rows_for_party(normalized_email)
    summaries = [_order_summary_from_database_row(row) for row in rows]
    summaries.sort(key=lambda item: (item["updatedAt"], item["orderId"]), reverse=True)
    summaries = _dedupe_order_summaries(summaries)
    total = len(summaries)
    items = summaries[offset : offset + limit]
    has_more = offset + len(items) < total

    return {
        "items": items,
        "page": {"limit": limit, "offset": offset, "hasMore": has_more, "total": total},
    }


def persist_order_to_database(req: OrderRequest) -> Any:
    from app.other import findOrders, saveOrder, saveOrderDetails

    try:
        delivery = req.delivery
        db_order_id = saveOrder(
            buyeremail=req.buyerEmail,
            buyername=req.buyerName,
            selleremail=req.sellerEmail,
            sellername=req.sellerName,
            deliverystreet=delivery.street if delivery else None,
            deliverycity=delivery.city if delivery else None,
            deliverystate=delivery.state if delivery else None,
            deliverypostcode=delivery.postcode if delivery else None,
            deliverycountry=delivery.country if delivery else None,
            requesteddate=delivery.requestedDate.isoformat()
            if delivery and delivery.requestedDate
            else None,
            notes=req.notes,
            issueDate=req.issueDate,
            status="DRAFT",
            currency=req.currency or "AUD",
        )

        for line in req.lines:
            saveOrderDetails(
                db_order_id,
                line.productName,
                line.unitCode or "EA",
                line.quantity,
                float(line.unitPrice) if line.unitPrice is not None else None,
            )

        orders = findOrders(orderId=db_order_id)
    except Exception as exc:  # noqa: BLE001
        raise OrderPersistenceError("Order could not be persisted in Supabase.") from exc

    if not orders:
        raise OrderPersistenceError("Order could not be verified in Supabase.")

    return db_order_id


def update_order_record(order_id: str, req: OrderRequest) -> dict[str, Any]:
    existing = get_order_record(order_id)
    if existing is None:
        # Order can't be found with order_id
        raise OrderNotFoundError(order_id)

    status = existing.get("status", "DRAFT")
    if status != "DRAFT":
        # Order is not in an editable status
        raise OrderConflictLockedError(f"Order cannot be updated in status '{status}'.")

    updated_at = now_z()
    ubl_xml = generate_ubl_order_xml(order_id, req)

    db_order_id = existing.get("dbOrderId")
    if db_order_id is None:
        # Order is missing dbOrderId
        raise OrderPersistenceError("Order is missing dbOrderId for persistence.")

    # Persist to DB
    persist_order_update_to_database(db_order_id, req)
    persist_order_runtime_metadata_to_database(
        db_order_id,
        external_order_id=order_id,
        ubl_xml=ubl_xml,
        updated_at=updated_at,
    )

    # Update in-memory record
    existing["updatedAt"] = updated_at
    existing["payload"] = req.model_dump(mode="json")
    existing["ublXml"] = ubl_xml

    _cache_order_record(order_id, existing)
    return existing


def persist_order_update_to_database(db_order_id: Any, req: OrderRequest) -> None:
    from app.other import (
        deleteOrderDetails,
        findOrders,
        saveOrder,
        saveOrderDetails,
    )

    try:
        # Update order using orderId
        delivery = req.delivery
        saveOrder(
            buyeremail=req.buyerEmail,
            buyername=req.buyerName,
            selleremail=req.sellerEmail,
            sellername=req.sellerName,
            deliverystreet=delivery.street if delivery else None,
            deliverycity=delivery.city if delivery else None,
            deliverystate=delivery.state if delivery else None,
            deliverypostcode=delivery.postcode if delivery else None,
            deliverycountry=delivery.country if delivery else None,
            requesteddate=delivery.requestedDate.isoformat()
            if delivery and delivery.requestedDate
            else None,
            notes=req.notes,
            issueDate=req.issueDate,
            status="DRAFT",
            currency=req.currency or "AUD",
            orderId=db_order_id,
        )

        # Delete existing line items and re-insert
        deleteOrderDetails(orderId=db_order_id)

        for line in req.lines:
            saveOrderDetails(
                db_order_id,
                line.productName,
                line.unitCode or "EA",
                line.quantity,
                float(line.unitPrice) if line.unitPrice is not None else None,
            )

        orders = findOrders(orderId=db_order_id)
    except Exception as exc:  # noqa: BLE001
        raise OrderPersistenceError("Order update could not be persisted in Supabase.") from exc

    if not orders:
        raise OrderPersistenceError("Order update could not be verified in Supabase.")


def persist_order_runtime_metadata_to_database(
    db_order_id: Any,
    *,
    external_order_id: str,
    ubl_xml: str,
    created_at: str | None = None,
    updated_at: str | None = None,
) -> None:
    from app.other import updateOrderRuntimeMetadata

    try:
        updateOrderRuntimeMetadata(
            db_order_id,
            externalOrderId=external_order_id,
            ublXml=ubl_xml,
            createdAt=created_at,
            updatedAt=updated_at,
        )
    except Exception as exc:  # noqa: BLE001
        raise OrderPersistenceError("Order metadata could not be persisted in Supabase.") from exc


def load_order_record_from_database(order_id: str) -> dict[str, Any] | None:
    from app.other import findOrderByExternalId

    row = findOrderByExternalId(order_id)
    if row is None:
        return None

    return _record_from_database_row(order_id, row)


def _fetch_order_rows_for_party(current_party_email: str) -> list[dict[str, Any]]:
    from app.other import findOrders

    return findOrders(buyeremail=current_party_email) + findOrders(selleremail=current_party_email)


def _rollback_created_order(db_order_id: Any) -> None:
    from app.other import deleteOrder

    try:
        deleteOrder(db_order_id)
    except Exception:
        # Preserve the original persistence failure; cleanup is best-effort.
        pass


def _cache_order_record(order_id: str, record: dict[str, Any]) -> None:
    ORDERS.pop(order_id, None)
    ORDERS[order_id] = record
    while len(ORDERS) > MAX_CACHED_ORDERS:
        if isinstance(ORDERS, OrderedDict):
            ORDERS.popitem(last=False)
            continue
        oldest_order_id = next(iter(ORDERS))
        ORDERS.pop(oldest_order_id, None)


def _record_from_database_row(order_id: str, row: dict[str, Any]) -> dict[str, Any]:
    buyer_email = _first_non_empty(row.get("buyer_id"), row.get("buyeremail"))
    seller_email = _first_non_empty(row.get("seller_id"), row.get("selleremail"))

    payload = {
        "buyerEmail": _normalize_email(buyer_email),
        "buyerName": _first_non_empty(row.get("buyername"), _resolve_party_name(buyer_email)),
        "sellerEmail": _normalize_email(seller_email),
        "sellerName": _first_non_empty(row.get("sellername"), _resolve_party_name(seller_email)),
        "currency": row.get("currency"),
        "issueDate": _coerce_date_string(row.get("issuedate")),
        "notes": row.get("notes"),
        "delivery": _build_delivery_payload(row),
        "lines": _build_lines_payload(row.get("details")),
    }

    created_at = _first_non_empty(row.get("createdat"), row.get("issuedate")) or now_z()
    updated_at = _first_non_empty(row.get("updatedat"), row.get("lastchanged"), created_at)
    status = row.get("status") or "DRAFT"

    return {
        "orderId": order_id,
        "status": status,
        "createdAt": created_at,
        "updatedAt": updated_at,
        "payload": payload,
        "ublXml": row.get("ublxml"),
        "dbOrderId": str(row["id"]) if row.get("id") is not None else None,
    }


def _order_summary_from_database_row(row: dict[str, Any]) -> dict[str, Any]:
    order_id = row.get("order_id")
    if not isinstance(order_id, str) or not order_id:
        raise OrderPersistenceError("Order row is missing order_id.")

    buyer_email = _first_non_empty(row.get("buyer_id"), row.get("buyeremail"))
    seller_email = _first_non_empty(row.get("seller_id"), row.get("selleremail"))
    created_at = _first_non_empty(row.get("createdat"), row.get("issuedate")) or now_z()
    updated_at = _first_non_empty(row.get("updatedat"), row.get("lastchanged"), created_at)

    return {
        "orderId": order_id,
        "status": row.get("status") or "DRAFT",
        "createdAt": created_at,
        "updatedAt": updated_at,
        "buyerName": _first_non_empty(row.get("buyername"), _resolve_party_name(buyer_email)),
        "sellerName": _first_non_empty(row.get("sellername"), _resolve_party_name(seller_email)),
        "issueDate": _coerce_date_string(row.get("issuedate")),
    }


def _build_delivery_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    delivery = {
        "street": row.get("deliverystreet"),
        "city": row.get("deliverycity"),
        "state": row.get("deliverystate"),
        "postcode": row.get("deliverypostcode"),
        "country": row.get("deliverycountry"),
        "requestedDate": _coerce_date_string(row.get("requesteddate")),
    }
    if not any(value is not None for value in delivery.values()):
        return None
    return delivery


def _build_lines_payload(details: Any) -> list[dict[str, Any]]:
    if not isinstance(details, list):
        return []

    lines: list[dict[str, Any]] = []
    for detail in details:
        if not isinstance(detail, dict):
            continue
        line = {
            "productName": detail.get("productname"),
            "quantity": _coerce_quantity(detail.get("quantity")),
            "unitCode": detail.get("unitcode"),
            "unitPrice": _coerce_price(detail.get("unitprice")),
        }
        lines.append(line)
    return lines


def _coerce_date_string(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if "T" in value:
        return value.split("T", 1)[0]
    return value


def _coerce_quantity(value: Any) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _coerce_price(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _normalize_email(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip().lower()


def _resolve_party_name(contact_email: Any) -> str | None:
    from app.other import findPartyByContactEmail

    normalized_email = _normalize_email(contact_email)
    if normalized_email is None:
        return None

    try:
        party = findPartyByContactEmail(normalized_email)
    except Exception:
        return normalized_email

    if isinstance(party, dict):
        party_name = party.get("party_name")
        if isinstance(party_name, str) and party_name.strip():
            return party_name.strip()
    return normalized_email


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None


def _dedupe_order_summaries(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique_items: list[dict[str, Any]] = []
    seen_order_ids: set[str] = set()
    for item in items:
        order_id = item["orderId"]
        if order_id in seen_order_ids:
            continue
        seen_order_ids.add(order_id)
        unique_items.append(item)
    return unique_items
