from __future__ import annotations

from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from app.api.routes import orders
from app.main import app
from app.services import app_key_auth, order_store
from app.services.order_store import OrderPersistenceError
from app.services.party_registration import hash_app_key
from app.services.ubl_order import OrderGenerationError

NS = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
}


def build_payload() -> dict:
    return {
        "buyerEmail": "buyer@example.com",
        "buyerName": "Acme Books",
        "sellerEmail": "seller@example.com",
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
                "unitPrice": "19.99",
            },
        ],
    }


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_orders_state():
    # Ensure each test starts clean
    orders.ORDERS.clear()


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
    monkeypatch.setattr(app_key_auth, "findPartyByPartyId", lambda party_id: party_map.get(party_id))
    yield
    app.dependency_overrides.clear()


def auth_headers(app_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {app_key}"}


def test_update_order_returns_200_and_updates_order_fields_and_xml(client, monkeypatch):
    # Create original payload
    create_payload = build_payload()

    # Dummy DB functions
    monkeypatch.setattr(order_store, "persist_order_to_database", lambda req: 123)
    monkeypatch.setattr(order_store, "persist_order_update_to_database", lambda dbid, req: None)

    # Create original order
    create_resp = client.post(
        "/v1/order/create", json=create_payload, headers=auth_headers("buyer-key")
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    order_id = created["orderId"]

    before_record = orders.ORDERS[order_id]
    before_updated_at = before_record["updatedAt"]
    assert before_record["status"] == "DRAFT"

    # Update payload
    update_payload = build_payload()
    update_payload["notes"] = "Deliver to reception"
    update_payload["delivery"]["street"] = "999 Updated St"
    update_payload["lines"][0]["quantity"] = 5
    update_payload["lines"][0]["unitPrice"] = "99.99"

    # Call update order
    update_resp = client.put(
        f"/v1/order/{order_id}",
        json=update_payload,
        headers=auth_headers("buyer-key"),
    )
    assert update_resp.status_code == 200

    # Check that order is the same order, but has updated
    body = update_resp.json()
    assert body["orderId"] == order_id
    assert body["status"] == "DRAFT"
    assert body["updatedAt"].endswith("Z")
    assert body["updatedAt"] != before_updated_at
    assert body["warnings"] == []

    # Check order details have been updated
    record = orders.ORDERS[order_id]
    assert record["payload"]["notes"] == "Deliver to reception"
    assert record["payload"]["delivery"]["street"] == "999 Updated St"
    assert record["payload"]["lines"][0]["quantity"] == 5
    assert record["payload"]["lines"][0]["unitPrice"] == "99.99"

    # UBL XML has been updated
    root = ET.fromstring(body["ublXml"])
    assert root.find("cbc:ID", NS).text == order_id
    assert root.find("cbc:Note", NS).text == "Deliver to reception"
    assert root.find("cac:Delivery/cac:DeliveryAddress/cbc:StreetName", NS).text == "999 Updated St"
    qty = root.find(".//cbc:Quantity", NS)
    assert qty.text == "5"
    price_amount = root.find(".//cac:Price/cbc:PriceAmount", NS)
    assert price_amount.text == "99.99"
    assert price_amount.attrib["currencyID"] == update_payload["currency"]


def test_update_order_returns_404_when_order_not_found(client):
    payload = build_payload()

    # Call update with no orderId
    resp = client.put("/v1/order/ord_doesnotexist", json=payload, headers=auth_headers("buyer-key"))
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not Found"}


def test_update_order_returns_409_when_order_not_editable(client, monkeypatch):
    # Dummy DB functions
    monkeypatch.setattr(order_store, "persist_order_to_database", lambda req: 123)
    monkeypatch.setattr(order_store, "persist_order_update_to_database", lambda dbid, req: None)

    # Create original order
    create_resp = client.post(
        "/v1/order/create", json=build_payload(), headers=auth_headers("buyer-key")
    )
    assert create_resp.status_code == 201
    order_id = create_resp.json()["orderId"]

    # Force status to something non-editable
    orders.ORDERS[order_id]["status"] = "SUBMITTED"

    # Call update
    update_resp = client.put(
        f"/v1/order/{order_id}",
        json=build_payload(),
        headers=auth_headers("buyer-key"),
    )
    assert update_resp.status_code == 409
    assert "cannot be updated" in update_resp.json()["detail"].lower()


@pytest.mark.parametrize(
    ("mutator", "expected_loc"),
    [
        (lambda payload: payload.pop("buyerName"), ["body", "buyerName"]),
        (lambda payload: payload.pop("buyerEmail"), ["body", "buyerEmail"]),
        (lambda payload: payload.update({"lines": []}), ["body", "lines"]),
        (
            lambda payload: payload["lines"][0].update({"quantity": 0}),
            ["body", "lines", 0, "quantity"],
        ),
    ],
)
def test_update_order_returns_422_for_invalid_payload(client, monkeypatch, mutator, expected_loc):
    # Dummy DB functions
    monkeypatch.setattr(order_store, "persist_order_to_database", lambda req: 123)
    monkeypatch.setattr(order_store, "persist_order_update_to_database", lambda dbid, req: None)

    # Create original order
    create_resp = client.post(
        "/v1/order/create", json=build_payload(), headers=auth_headers("buyer-key")
    )
    assert create_resp.status_code == 201
    order_id = create_resp.json()["orderId"]

    # Mutate payload
    payload = build_payload()
    mutator(payload)

    # Call update
    resp = client.put(f"/v1/order/{order_id}", json=payload, headers=auth_headers("buyer-key"))
    assert resp.status_code == 422
    assert expected_loc in [error["loc"] for error in resp.json()["detail"]]


def test_update_order_returns_500_when_xml_generation_fails(client, monkeypatch):
    # Dummy DB functions
    monkeypatch.setattr(order_store, "persist_order_to_database", lambda req: 123)
    monkeypatch.setattr(order_store, "persist_order_update_to_database", lambda dbid, req: None)

    # Create original order
    create_resp = client.post(
        "/v1/order/create", json=build_payload(), headers=auth_headers("buyer-key")
    )
    assert create_resp.status_code == 201
    order_id = create_resp.json()["orderId"]

    # Dummy OrderGenerationError
    def fail_generate_ubl_order_xml(order_id: str, req):  # noqa: ARG001
        raise OrderGenerationError("boom")

    monkeypatch.setattr(order_store, "generate_ubl_order_xml", fail_generate_ubl_order_xml)

    # Call update
    resp = client.put(
        f"/v1/order/{order_id}",
        json=build_payload(),
        headers=auth_headers("buyer-key"),
    )
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Unable to update order."}


def test_update_order_returns_500_when_database_update_fails(client, monkeypatch):
    # Dummy DB functions
    monkeypatch.setattr(order_store, "persist_order_to_database", lambda req: 123)

    # Create original order
    create_resp = client.post(
        "/v1/order/create", json=build_payload(), headers=auth_headers("buyer-key")
    )
    assert create_resp.status_code == 201
    order_id = create_resp.json()["orderId"]

    # Dummy OrderPersistenceError
    def fail_persist_update(dbid, req):  # noqa: ARG001
        raise OrderPersistenceError("db update failed")

    monkeypatch.setattr(order_store, "persist_order_update_to_database", fail_persist_update)

    # Call update
    resp = client.put(
        f"/v1/order/{order_id}",
        json=build_payload(),
        headers=auth_headers("buyer-key"),
    )
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Unable to persist updated order."}


def test_update_order_returns_401_when_auth_header_is_missing(client, monkeypatch):
    monkeypatch.setattr(order_store, "persist_order_to_database", lambda req: 123)
    monkeypatch.setattr(order_store, "persist_order_update_to_database", lambda dbid, req: None)

    create_resp = client.post(
        "/v1/order/create", json=build_payload(), headers=auth_headers("buyer-key")
    )
    assert create_resp.status_code == 201
    order_id = create_resp.json()["orderId"]

    resp = client.put(f"/v1/order/{order_id}", json=build_payload())

    assert resp.status_code == 401
    assert resp.json() == {"detail": "Unauthorized"}


def test_update_order_returns_401_for_malformed_auth_header(client, monkeypatch):
    monkeypatch.setattr(order_store, "persist_order_to_database", lambda req: 123)
    monkeypatch.setattr(order_store, "persist_order_update_to_database", lambda dbid, req: None)

    create_resp = client.post(
        "/v1/order/create", json=build_payload(), headers=auth_headers("buyer-key")
    )
    assert create_resp.status_code == 201
    order_id = create_resp.json()["orderId"]

    resp = client.put(
        f"/v1/order/{order_id}",
        json=build_payload(),
        headers={"Authorization": "Basic buyer-key"},
    )

    assert resp.status_code == 401
    assert resp.json() == {"detail": "Unauthorized"}


def test_update_order_returns_401_for_unknown_app_key(client, monkeypatch):
    monkeypatch.setattr(order_store, "persist_order_to_database", lambda req: 123)
    monkeypatch.setattr(order_store, "persist_order_update_to_database", lambda dbid, req: None)

    create_resp = client.post(
        "/v1/order/create", json=build_payload(), headers=auth_headers("buyer-key")
    )
    assert create_resp.status_code == 201
    order_id = create_resp.json()["orderId"]

    resp = client.put(
        f"/v1/order/{order_id}", json=build_payload(), headers=auth_headers("unknown-key")
    )

    assert resp.status_code == 401
    assert resp.json() == {"detail": "Unauthorized"}


def test_update_order_returns_403_for_non_party_caller(client, monkeypatch):
    monkeypatch.setattr(order_store, "persist_order_to_database", lambda req: 123)
    monkeypatch.setattr(order_store, "persist_order_update_to_database", lambda dbid, req: None)

    create_resp = client.post(
        "/v1/order/create", json=build_payload(), headers=auth_headers("buyer-key")
    )
    assert create_resp.status_code == 201
    order_id = create_resp.json()["orderId"]

    resp = client.put(
        f"/v1/order/{order_id}", json=build_payload(), headers=auth_headers("other-key")
    )

    assert resp.status_code == 403
    assert resp.json() == {"detail": "Forbidden"}


def test_update_order_allows_seller_party(client, monkeypatch):
    monkeypatch.setattr(order_store, "persist_order_to_database", lambda req: 123)
    monkeypatch.setattr(order_store, "persist_order_update_to_database", lambda dbid, req: None)

    create_resp = client.post(
        "/v1/order/create", json=build_payload(), headers=auth_headers("buyer-key")
    )
    assert create_resp.status_code == 201
    order_id = create_resp.json()["orderId"]

    resp = client.put(
        f"/v1/order/{order_id}", json=build_payload(), headers=auth_headers("seller-key")
    )

    assert resp.status_code == 200


def test_update_order_returns_409_when_request_changes_order_parties(client, monkeypatch):
    monkeypatch.setattr(order_store, "persist_order_to_database", lambda req: 123)
    monkeypatch.setattr(order_store, "persist_order_update_to_database", lambda dbid, req: None)

    create_resp = client.post(
        "/v1/order/create", json=build_payload(), headers=auth_headers("buyer-key")
    )
    assert create_resp.status_code == 201
    order_id = create_resp.json()["orderId"]

    payload = build_payload()
    payload["sellerEmail"] = "seller-updated@example.com"
    resp = client.put(f"/v1/order/{order_id}", json=payload, headers=auth_headers("buyer-key"))

    assert resp.status_code == 409
    assert resp.json() == {"detail": "Order participant emails cannot be changed."}
