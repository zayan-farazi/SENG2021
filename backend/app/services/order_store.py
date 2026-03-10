from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.schemas import OrderRequest
from app.services.ubl_order import generate_order_id, generate_ubl_order_xml

ORDERS: dict[str, dict[str, Any]] = {}


class OrderPersistenceError(RuntimeError):
    """Raised when the database verification step fails."""


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
