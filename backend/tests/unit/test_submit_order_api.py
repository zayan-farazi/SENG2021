from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.api.routes import orders
from app.main import app
from app.services import app_key_auth, order_store
from app.services.party_registration import hash_app_key


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
            }
        ],
    }


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_orders_state():
    orders.ORDERS.clear()
    yield
    orders.ORDERS.clear()


@pytest.fixture(autouse=True)
def stub_database_lookup(monkeypatch):
    monkeypatch.setattr(order_store, "load_order_record_from_database", lambda order_id: None)


@pytest.fixture(autouse=True)
def stub_runtime_metadata_persistence(monkeypatch):
    monkeypatch.setattr(order_store, "persist_order_to_database", lambda req: 123)
    monkeypatch.setattr(
        order_store,
        "persist_order_runtime_metadata_to_database",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        order_store,
        "persist_order_status_to_database",
        lambda *args, **kwargs: None,
    )


@pytest.fixture(autouse=True)
def stub_app_key_lookup(monkeypatch):
    app.dependency_overrides.clear()
    key_map = {
        hash_app_key("buyer-key"): {
            "party_id": "buyer-party",
            "contact_email": "buyer@example.com",
            "party_name": "Acme Books",
        },
        hash_app_key("seller-key"): {
            "party_id": "seller-party",
            "contact_email": "seller@example.com",
            "party_name": "Digital Book Supply",
        },
        hash_app_key("other-key"): {
            "party_id": "other-party",
            "contact_email": "other@example.com",
            "party_name": "Other Company",
        },
    }
    monkeypatch.setattr(app_key_auth, "findAppKeyByHash", lambda key_hash: key_map.get(key_hash))
    yield
    app.dependency_overrides.clear()


def auth_headers(app_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {app_key}"}


def test_submit_order_transitions_draft_to_submitted(client):
    create_response = client.post(
        "/v1/order/create",
        json=build_payload(),
        headers=auth_headers("buyer-key"),
    )
    assert create_response.status_code == 201
    order_id = create_response.json()["orderId"]

    submit_response = client.post(
        f"/v1/order/{order_id}/submit",
        headers=auth_headers("buyer-key"),
    )

    assert submit_response.status_code == 200
    body = submit_response.json()
    assert body["orderId"] == order_id
    assert body["status"] == "SUBMITTED"
    assert body["updatedAt"].endswith("Z")
    assert orders.ORDERS[order_id]["status"] == "SUBMITTED"


def test_submit_order_returns_403_for_unrelated_party(client):
    create_response = client.post(
        "/v1/order/create",
        json=build_payload(),
        headers=auth_headers("buyer-key"),
    )
    assert create_response.status_code == 201
    order_id = create_response.json()["orderId"]

    submit_response = client.post(
        f"/v1/order/{order_id}/submit",
        headers=auth_headers("other-key"),
    )

    assert submit_response.status_code == 403
    assert "does not match" in submit_response.json()["detail"]


def test_submit_order_returns_409_when_order_is_already_locked(client, monkeypatch):
    create_response = client.post(
        "/v1/order/create",
        json=build_payload(),
        headers=auth_headers("buyer-key"),
    )
    assert create_response.status_code == 201
    order_id = create_response.json()["orderId"]

    original_record = deepcopy(orders.ORDERS[order_id])
    original_record["status"] = "SUBMITTED"
    orders.ORDERS.clear()
    monkeypatch.setattr(
        order_store,
        "load_order_record_from_database",
        lambda requested_order_id: deepcopy(original_record)
        if requested_order_id == order_id
        else None,
    )

    submit_response = client.post(
        f"/v1/order/{order_id}/submit",
        headers=auth_headers("buyer-key"),
    )

    assert submit_response.status_code == 409
    assert "cannot be submitted" in submit_response.json()["detail"].lower()


def test_update_order_returns_409_after_submit(client):
    payload = build_payload()
    create_response = client.post(
        "/v1/order/create",
        json=payload,
        headers=auth_headers("buyer-key"),
    )
    assert create_response.status_code == 201
    order_id = create_response.json()["orderId"]

    submit_response = client.post(
        f"/v1/order/{order_id}/submit",
        headers=auth_headers("buyer-key"),
    )
    assert submit_response.status_code == 200

    update_response = client.put(
        f"/v1/order/{order_id}",
        json=payload,
        headers=auth_headers("buyer-key"),
    )

    assert update_response.status_code == 409
    assert "cannot be updated" in update_response.json()["detail"].lower()
