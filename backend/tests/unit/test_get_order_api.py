from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal
from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from app.api.routes import orders
from app.main import app
from app.models.schemas import Delivery, LineItem, OrderRequest
from app.services import app_key_auth, order_store
from app.services.party_registration import hash_app_key
from app.services.ubl_order import generate_order_id, generate_ubl_order_xml

NS = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
}


def build_payload() -> OrderRequest:
    return OrderRequest(
        buyerEmail="buyer@example.com",
        buyerName="Acme Books",
        sellerEmail="seller@example.com",
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


@pytest.fixture(autouse=True)
def reset_order_cache():
    orders.ORDERS.clear()
    yield
    orders.ORDERS.clear()


@pytest.fixture(autouse=True)
def stub_database_lookup(monkeypatch):
    monkeypatch.setattr(order_store, "load_order_record_from_database", lambda order_id: None)


@pytest.fixture(autouse=True)
def stub_app_key_lookup(monkeypatch):
    app.dependency_overrides.clear()
    key_map = {
        hash_app_key("buyer-key"): {"party_id": "buyer-party"},
        hash_app_key("seller-key"): {"party_id": "seller-party"},
        hash_app_key("other-key"): {"party_id": "other-party"},
    }
    party_map = {
        "buyer-party": {"contact_email": "buyer@example.com"},
        "seller-party": {"contact_email": "seller@example.com"},
        "other-party": {"contact_email": "other@example.com"},
    }
    monkeypatch.setattr(app_key_auth, "findAppKeyByHash", lambda key_hash: key_map.get(key_hash))
    monkeypatch.setattr(
        app_key_auth, "findPartyByPartyId", lambda party_id: party_map.get(party_id)
    )
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def db_records(monkeypatch):
    records: dict[str, dict] = {}

    def load_order_record_from_database(order_id: str):
        record = records.get(order_id)
        return deepcopy(record) if record else None

    monkeypatch.setattr(
        order_store, "load_order_record_from_database", load_order_record_from_database
    )
    return records


@pytest.fixture
def created_order(db_records):
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
        "dbOrderId": "123",
    }
    db_records[order_id] = record
    return order_id, record


def auth_headers(app_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {app_key}"}


def test_get_existing_order_returns_order(client, created_order):
    order_id, record = created_order

    response = client.get(f"/v1/order/{order_id}", headers=auth_headers("buyer-key"))
    assert response.status_code == 200

    body = response.json()
    # Check only fields returned to the client
    assert body["orderId"] == record["orderId"]
    assert body["status"] == record["status"]
    assert body["createdAt"] == record["createdAt"]
    assert body["updatedAt"] == record["updatedAt"]
    assert body["warnings"] == record["warnings"]
    assert "ublXml" not in body
    assert orders.ORDERS[order_id]["dbOrderId"] == "123"

    # Check internal payload separately
    assert record["payload"]["buyerName"] == "Acme Books"
    assert record["payload"]["sellerName"] == "Digital Book Supply"
    assert record["payload"]["currency"] == "AUD"
    assert record["payload"]["lines"][0]["unitPrice"] == ("12.50")


def test_get_nonexistent_order_returns_404(client):
    response = client.get("/v1/order/nonexistent123", headers=auth_headers("buyer-key"))
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_get_order_with_invalid_id_format_returns_404(client):
    invalid_ids = ["", "!!!!", "123-abc!", " "]
    for order_id in invalid_ids:
        response = client.get(f"/v1/order/{order_id}", headers=auth_headers("buyer-key"))
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}


def test_get_order_with_missing_ubl_xml_still_returns_json_order(client, created_order):
    order_id, record = created_order
    record["ublXml"] = None

    response = client.get(f"/v1/order/{order_id}", headers=auth_headers("buyer-key"))
    assert response.status_code == 200
    assert response.json()["orderId"] == order_id
    assert "ublXml" not in response.json()


def test_get_order_returns_401_when_auth_header_is_missing(client, created_order):
    order_id, _record = created_order

    response = client.get(f"/v1/order/{order_id}")

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_get_order_returns_401_for_malformed_auth_header(client, created_order):
    order_id, _record = created_order

    response = client.get(
        f"/v1/order/{order_id}",
        headers={"Authorization": "Basic buyer-key"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_get_order_returns_401_for_unknown_app_key(client, created_order):
    order_id, _record = created_order

    response = client.get(f"/v1/order/{order_id}", headers=auth_headers("unknown-key"))

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_get_order_returns_403_for_non_party_caller(client, created_order):
    order_id, _record = created_order

    response = client.get(f"/v1/order/{order_id}", headers=auth_headers("other-key"))

    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}


def test_get_order_allows_seller_party(client, created_order):
    order_id, _record = created_order

    response = client.get(f"/v1/order/{order_id}", headers=auth_headers("seller-key"))

    assert response.status_code == 200


def test_get_order_ubl_returns_raw_xml_for_buyer(client, created_order):
    order_id, record = created_order

    response = client.get(f"/v1/order/{order_id}/ubl", headers=auth_headers("buyer-key"))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert response.text == record["ublXml"]

    root = ET.fromstring(response.text)
    assert root.find("cbc:ID", NS).text == order_id


def test_get_order_ubl_allows_seller_party(client, created_order):
    order_id, record = created_order

    response = client.get(f"/v1/order/{order_id}/ubl", headers=auth_headers("seller-key"))

    assert response.status_code == 200
    assert response.text == record["ublXml"]


def test_get_order_ubl_returns_404_when_order_not_found(client):
    response = client.get("/v1/order/nonexistent123/ubl", headers=auth_headers("buyer-key"))

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_get_order_ubl_returns_500_when_xml_is_missing(client, created_order):
    order_id, record = created_order
    record["ublXml"] = None

    response = client.get(f"/v1/order/{order_id}/ubl", headers=auth_headers("buyer-key"))

    assert response.status_code == 500
    assert response.json() == {"detail": "Order XML missing."}


def test_get_order_ubl_returns_401_when_auth_header_is_missing(client, created_order):
    order_id, _record = created_order

    response = client.get(f"/v1/order/{order_id}/ubl")

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_get_order_ubl_returns_401_for_malformed_auth_header(client, created_order):
    order_id, _record = created_order

    response = client.get(
        f"/v1/order/{order_id}/ubl",
        headers={"Authorization": "Basic buyer-key"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_get_order_ubl_returns_401_for_unknown_app_key(client, created_order):
    order_id, _record = created_order

    response = client.get(f"/v1/order/{order_id}/ubl", headers=auth_headers("unknown-key"))

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_get_order_ubl_returns_403_for_non_party_caller(client, created_order):
    order_id, _record = created_order

    response = client.get(f"/v1/order/{order_id}/ubl", headers=auth_headers("other-key"))

    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}
