from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.schemas import OrderRequest
from app.services.ubl_order import generate_order_id, generate_ubl_order_xml

ORDERS: dict[str, dict[str, Any]] = {}


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
        "warnings": [],
    }
    db_order_id = persist_order_to_database(req)
    record["dbOrderId"] = str(db_order_id)
    ORDERS[order_id] = record
    return record


def build_order_response(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "orderId": record["orderId"],
        "status": record["status"],
        "createdAt": record["createdAt"],
        "ublXml": record["ublXml"],
        "warnings": record["warnings"],
    }


def persist_order_to_database(req: OrderRequest) -> Any:
    from app.other import findOrders, saveOrder, saveOrderDetails

    try:
        delivery = req.delivery
        db_order_id = saveOrder(
            buyername=req.buyerName,
            sellername=req.sellerName,
            deliverystreet=delivery.street if delivery else None,
            deliverycity=delivery.city if delivery else None,
            deliverypostcode=delivery.postcode if delivery else None,
            deliverycountry=delivery.country if delivery else None,
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
                float(line.unitPrice) if line.unitPrice is not None else 0.0,
            )

        orders = findOrders(orderId=db_order_id)
    except Exception as exc:  # noqa: BLE001
        raise OrderPersistenceError("Order could not be persisted in Supabase.") from exc

    if not orders:
        raise OrderPersistenceError("Order could not be verified in Supabase.")

    return db_order_id


def update_order_record(order_id: str, req: OrderRequest) -> dict[str, Any]:
    existing = ORDERS.get(order_id)
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

    # Update in-memory record
    existing["updatedAt"] = updated_at
    existing["payload"] = req.model_dump(mode="json")
    existing["ublXml"] = ubl_xml
    existing["warnings"] = existing.get("warnings", [])

    ORDERS[order_id] = existing
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
            buyername=req.buyerName,
            sellername=req.sellerName,
            deliverystreet=delivery.street if delivery else None,
            deliverycity=delivery.city if delivery else None,
            deliverypostcode=delivery.postcode if delivery else None,
            deliverycountry=delivery.country if delivery else None,
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
                float(line.unitPrice) if line.unitPrice is not None else 0.0,
            )

        orders = findOrders(orderId=db_order_id)
    except Exception as exc:  # noqa: BLE001
        raise OrderPersistenceError("Order update could not be persisted in Supabase.") from exc

    if not orders:
        raise OrderPersistenceError("Order update could not be verified in Supabase.")
