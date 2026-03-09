from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from app.models.schemas import OrderRequest
from app.services.ubl_order import (
    OrderGenerationError,
    generate_order_id,
    generate_ubl_order_xml,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory store for quick testing (replace with Supabase later)
# orderId -> { orderId, status, createdAt, updatedAt, payload, ublXml, warnings }
ORDERS: dict[str, dict[str, Any]] = {}


def now_z() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@router.get("/")
def root():
    return {"message": "Hellooooooo"}


@router.post("/v1/order/create", status_code=201)
def create_order(req: OrderRequest):
    try:
        order_id = generate_order_id()
        created_at = now_z()
        ubl_xml = generate_ubl_order_xml(order_id, req)
    except OrderGenerationError as exc:
        logger.exception("Order creation failed")
        raise HTTPException(status_code=500, detail="Unable to create order.") from exc

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

    return {
        "orderId": order_id,
        "status": record["status"],
        "createdAt": record["createdAt"],
        "ublXml": record["ublXml"],
        "warnings": record["warnings"],
    }

@router.get("/v1/order/{order_id}")
def get_order(order_id: str):
    order = ORDERS.get(order_id)

    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")

    return {
        "orderId": order["orderId"],
        "status": order["status"],
        "createdAt": order["createdAt"],
        "updatedAt": order["updatedAt"],
        "ublXml": order["ublXml"],
        "warnings": order["warnings"],
    }