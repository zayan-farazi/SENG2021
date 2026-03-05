from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter

from app.models.schemas import OrderRequest
from app.services.ubl_order import generate_order_id, generate_ubl_order_xml

router = APIRouter()

# In-memory store for quick testing (replace with Supabase later)
# orderId -> { orderId, status, createdAt, updatedAt, payload, ublXml, warnings }
ORDERS: dict[str, dict[str, Any]] = {}


def now_z() -> str:
    return datetime.utcnow().isoformat() + "Z"


@router.get("/")
def root():
    return {"message": "Hellooooooo"}


@router.post("/v1/order/create", status_code=201)
def create_order(req: OrderRequest):
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

    return {
        "orderId": order_id,
        "status": record["status"],
        "createdAt": record["createdAt"],
        "ublXml": record["ublXml"],
        "warnings": record["warnings"],
    }
