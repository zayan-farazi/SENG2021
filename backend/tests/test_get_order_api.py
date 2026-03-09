from __future__ import annotations

from datetime import date
from decimal import Decimal
from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from app.api.routes import orders
from app.main import app
from app.models.schemas import Delivery, LineItem, OrderRequest
from app.services.ubl_order import generate_order_id, generate_ubl_order_xml

NS = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
}



def build_payload() -> OrderRequest:
    return OrderRequest(
        buyerName="Acme Books",
        sellerName="Digital Book Supply",
        currency="AUD",
        issueDate=date(2026, 3, 7),
        notes="Leave at loading dock",
        delivery=Delivery(
            street="123 Test St",
            city="Sydney",
            state="NSW",
            postcode="2000",
            country="AU",
            requestedDate=date(2026, 3, 10),
        ),
        lines=[
            LineItem(
                productName="Domain-Driven Design",
                quantity=2,
                unitCode="EA",
                unitPrice=Decimal("12.50"),
            ),
            LineItem(
                productName="Clean Architecture",
                quantity=1,
                unitCode="BX",
                unitPrice=None,
            ),
        ],
    )

@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def created_order():
    """Create an order directly in ORDERS to test GET endpoint."""
    req = build_payload()
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
     # Check only fields returned to the client
    assert body["orderId"] == record["orderId"]
    assert body["status"] == record["status"]
    assert body["createdAt"] == record["createdAt"]
    assert body["updatedAt"] == record["updatedAt"]
    assert body["ublXml"] == record["ublXml"]
    assert body["warnings"] == record["warnings"]

    # Check internal payload separately
    assert record["payload"]["buyerName"] == "Acme Books"
    assert record["payload"]["sellerName"] == "Digital Book Supply"
    assert record["payload"]["currency"] == "AUD"
    assert record["payload"]["lines"][0]["unitPrice"] == ("12.50")

    # parse XML and check key values
    root = ET.fromstring(body["ublXml"])
    assert root.find("cbc:ID", NS).text == order_id
    assert root.find(
        "cac:BuyerCustomerParty/cac:Party/cac:PartyName/cbc:Name", NS
    ).text == record["payload"]["buyerName"]
    assert root.find(
        "cac:SellerSupplierParty/cac:Party/cac:PartyName/cbc:Name", NS
    ).text == record["payload"]["sellerName"]


def test_get_nonexistent_order_returns_404(client):
    response = client.get("/v1/order/nonexistent123")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}

def test_get_order_with_invalid_id_format_returns_404(client):
    invalid_ids = ["", "!!!!", "123-abc!", " "]
    for order_id in invalid_ids:
        response = client.get(f"/v1/order/{order_id}")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}

def test_get_order_with_missing_ubl_xml_returns_error(client, created_order):
    order_id, record = created_order
    # Remove the UBL XML to simulate a failed generation
    record["ublXml"] = None

    response = client.get(f"/v1/order/{order_id}")
    # - Return 500? (internal error)
    assert response.status_code == 500
    assert response.json() == {"detail": "Order XML missing."}