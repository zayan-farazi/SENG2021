from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.schemas import OrderRequest
from app.services.ubl_order import generate_order_id, generate_ubl_order_xml

ORDERS: dict[str, dict[str, Any]] = {}


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
