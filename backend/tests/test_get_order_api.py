from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.routes import orders
from app.main import app
from app.models.schemas import OrderRequest
from app.services.ubl_order import generate_ubl_order_xml, generate_order_id

@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def created_order():
    """Create an order directly in ORDERS to test GET endpoint."""
    req = OrderRequest(
        buyerName="Acme Books",
        sellerName="Digital Book Supply",
        currency="AUD",
        lines=[{"productName": "Test Book", "quantity": 1}],
    )
    order_id = generate_order_id()
    ubl_xml = generate_ubl_order_xml(order_id, req)

    record = {
        "orderId": order_id,
        "status": "DRAFT",
        "createdAt": "2026-03-09T00:00:00Z",
        "updatedAt": "2026-03-09T00:00:00Z",
        "payload": req.model_dump(mode="json"),
        "ublXml": ubl_xml,
        "warnings": [],
    }
    orders.ORDERS[order_id] = record
    return order_id, record


def test_get_existing_order_returns_order(client, created_order):
    order_id, record = created_order

    response = client.get(f"/v1/order/{order_id}")
    assert response.status_code == 200

    body = response.json()
    assert body["orderId"] == record["orderId"]
    assert body["status"] == record["status"]
    assert body["ublXml"] == record["ublXml"]
    assert body["warnings"] == record["warnings"]


def test_get_nonexistent_order_returns_404(client):
    response = client.get("/v1/order/nonexistent123")
    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found."}