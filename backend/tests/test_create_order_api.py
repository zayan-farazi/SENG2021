from __future__ import annotations

from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from app.api.routes import orders
from app.main import app
from app.services import order_store
from app.services.order_store import OrderPersistenceError
from app.services.ubl_order import OrderGenerationError

NS = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
}


def build_payload() -> dict:
    return {
        "buyerName": "Acme Books",
        "sellerName": "Digital Book Supply",
        "currency": "AUD",
        "issueDate": "2026-03-07",
        "notes": "Leave at loading dock",
        "delivery": {
            "street": "123 Test St",
            "city": "Sydney",
            "state": "NSW",
            "postcode": "2000",
            "country": "AU",
            "requestedDate": "2026-03-10",
        },
        "lines": [
            {
                "productName": "Domain-Driven Design",
                "quantity": 2,
                "unitCode": "EA",
                "unitPrice": "12.50",
            },
            {
                "productName": "Clean Architecture",
                "quantity": 1,
                "unitCode": "BX",
            },
        ],
    }


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_create_order_returns_201_and_persists_full_order(client):
    payload = build_payload()

    response = client.post("/v1/order/create", json=payload)

    assert response.status_code == 201
    body = response.json()

    assert body["orderId"].startswith("ord_")
    assert body["status"] == "DRAFT"
    assert body["createdAt"].endswith("Z")
    assert body["warnings"] == []

    record = orders.ORDERS[body["orderId"]]
    assert record["createdAt"] == body["createdAt"]
    assert record["updatedAt"] == body["createdAt"]
    assert record["payload"]["buyerName"] == payload["buyerName"]
    assert record["payload"]["sellerName"] == payload["sellerName"]
    assert record["payload"]["currency"] == payload["currency"]
    assert record["payload"]["issueDate"] == payload["issueDate"]
    assert record["payload"]["delivery"]["requestedDate"] == payload["delivery"]["requestedDate"]
    assert record["payload"]["lines"][0]["unitPrice"] == payload["lines"][0]["unitPrice"]
    assert record["warnings"] == []

    root = ET.fromstring(body["ublXml"])
    assert root.find("cbc:ID", NS).text == body["orderId"]
    assert root.find("cbc:IssueDate", NS).text == payload["issueDate"]
    assert root.find("cbc:Note", NS).text == payload["notes"]
    assert (
        root.find(
            "cac:BuyerCustomerParty/cac:Party/cac:PartyName/cbc:Name",
            NS,
        ).text
        == payload["buyerName"]
    )
    assert (
        root.find(
            "cac:SellerSupplierParty/cac:Party/cac:PartyName/cbc:Name",
            NS,
        ).text
        == payload["sellerName"]
    )
    assert root.find("cac:Delivery/cac:DeliveryAddress/cbc:StreetName", NS).text == "123 Test St"
    assert (
        root.find(
            "cac:Delivery/cac:RequestedDeliveryPeriod/cbc:StartDate",
            NS,
        ).text
        == payload["delivery"]["requestedDate"]
    )

    price_amount = root.find(".//cac:Price/cbc:PriceAmount", NS)
    assert price_amount.text == payload["lines"][0]["unitPrice"]
    assert price_amount.attrib["currencyID"] == payload["currency"]


def test_create_order_applies_defaults_for_optional_fields(client):
    payload = {
        "buyerName": "Acme Books",
        "sellerName": "Digital Book Supply",
        "lines": [{"productName": "Working Effectively with Legacy Code", "quantity": 1}],
    }

    response = client.post("/v1/order/create", json=payload)

    assert response.status_code == 201
    body = response.json()
    record = orders.ORDERS[body["orderId"]]

    assert record["payload"]["currency"] is None
    assert record["payload"]["issueDate"] is None
    assert record["payload"]["notes"] is None
    assert record["payload"]["delivery"] is None
    assert record["payload"]["lines"][0]["unitCode"] == "EA"
    assert record["payload"]["lines"][0]["unitPrice"] is None

    root = ET.fromstring(body["ublXml"])
    assert root.find("cbc:Note", NS) is None
    assert root.find("cac:Delivery", NS) is None
    quantity = root.find(".//cbc:Quantity", NS)
    assert quantity.attrib["unitCode"] == "EA"
    assert root.find(".//cbc:PriceAmount", NS) is None


@pytest.mark.parametrize(
    ("mutator", "expected_loc"),
    [
        (lambda payload: payload.pop("buyerName"), ["body", "buyerName"]),
        (lambda payload: payload.update({"lines": []}), ["body", "lines"]),
        (
            lambda payload: payload["lines"][0].update({"quantity": 0}),
            ["body", "lines", 0, "quantity"],
        ),
        (lambda payload: payload.update({"currency": "AU"}), ["body", "currency"]),
        (
            lambda payload: payload["lines"][0].update({"unitPrice": "-1.00"}),
            ["body", "lines", 0, "unitPrice"],
        ),
    ],
)
def test_create_order_rejects_invalid_payloads(client, mutator, expected_loc):
    payload = build_payload()
    mutator(payload)

    response = client.post("/v1/order/create", json=payload)

    assert response.status_code == 422
    assert expected_loc in [error["loc"] for error in response.json()["detail"]]
    assert orders.ORDERS == {}


def test_create_order_returns_500_when_id_generation_fails(client, monkeypatch):
    payload = build_payload()

    def fail_generate_order_id():
        raise OrderGenerationError("boom")

    monkeypatch.setattr(order_store, "generate_order_id", fail_generate_order_id)

    response = client.post("/v1/order/create", json=payload)

    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to create order."}
    assert orders.ORDERS == {}


def test_create_order_returns_500_when_xml_generation_fails(client, monkeypatch):
    payload = build_payload()

    def fail_generate_ubl_order_xml(order_id: str, req):
        raise OrderGenerationError(f"unable to serialize {order_id}")

    monkeypatch.setattr(order_store, "generate_order_id", lambda: "ord_fixedfailure01")
    monkeypatch.setattr(order_store, "generate_ubl_order_xml", fail_generate_ubl_order_xml)

    response = client.post("/v1/order/create", json=payload)

    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to create order."}
    assert orders.ORDERS == {}


def test_create_order_returns_500_when_database_verification_fails(client, monkeypatch):
    payload = build_payload()

    def fail_persist_order_to_database(req):  # noqa: ARG001
        raise OrderPersistenceError("Supabase verification failed")

    monkeypatch.setattr(order_store, "persist_order_to_database", fail_persist_order_to_database)

    response = client.post("/v1/order/create", json=payload)

    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to persist order."}
    assert orders.ORDERS == {}
