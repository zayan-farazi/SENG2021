from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.routes import orders
from app.main import app
from app.services import app_key_auth, order_store
from app.services.order_store import OrderPersistenceError
from app.services.party_registration import hash_app_key


def build_record(order_id: str = "ord_delete_me") -> dict:
    return {
        "orderId": order_id,
        "status": "DRAFT",
        "createdAt": "2026-03-14T00:00:00Z",
        "updatedAt": "2026-03-14T00:00:00Z",
        "payload": {
            "buyerId": "buyer-123",
            "buyerName": "Acme Books",
            "sellerId": "seller-456",
            "sellerName": "Digital Book Supply",
            "lines": [{"productName": "Book", "quantity": 1, "unitCode": "EA"}],
        },
        "ublXml": "<Order />",
        "warnings": [],
    }


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def stub_app_key_lookup(monkeypatch):
    app.dependency_overrides.clear()
    key_map = {
        hash_app_key("buyer-key"): {"party_id": "buyer-123"},
        hash_app_key("seller-key"): {"party_id": "seller-456"},
        hash_app_key("other-key"): {"party_id": "other-party"},
    }
    monkeypatch.setattr(app_key_auth, "findAppKeyByHash", lambda key_hash: key_map.get(key_hash))
    yield
    app.dependency_overrides.clear()


def auth_headers(app_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {app_key}"}


def test_delete_order_returns_204_for_buyer(client):
    orders.ORDERS["ord_delete_me"] = build_record()

    response = client.delete("/v1/order/ord_delete_me", headers=auth_headers("buyer-key"))

    assert response.status_code == 204
    assert "ord_delete_me" not in orders.ORDERS


def test_delete_order_returns_204_for_seller(client):
    orders.ORDERS["ord_delete_me"] = build_record()

    response = client.delete("/v1/order/ord_delete_me", headers=auth_headers("seller-key"))

    assert response.status_code == 204
    assert "ord_delete_me" not in orders.ORDERS


def test_delete_order_returns_401_when_auth_header_is_missing(client):
    orders.ORDERS["ord_delete_me"] = build_record()

    response = client.delete("/v1/order/ord_delete_me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}
    assert "ord_delete_me" in orders.ORDERS


def test_delete_order_returns_401_for_malformed_auth_header(client):
    orders.ORDERS["ord_delete_me"] = build_record()

    response = client.delete(
        "/v1/order/ord_delete_me",
        headers={"Authorization": "Basic buyer-key"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}
    assert "ord_delete_me" in orders.ORDERS


def test_delete_order_returns_401_for_unknown_app_key(client):
    orders.ORDERS["ord_delete_me"] = build_record()

    response = client.delete("/v1/order/ord_delete_me", headers=auth_headers("unknown-key"))

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}
    assert "ord_delete_me" in orders.ORDERS


def test_delete_order_returns_403_for_non_party_caller(client):
    orders.ORDERS["ord_delete_me"] = build_record()

    response = client.delete("/v1/order/ord_delete_me", headers=auth_headers("other-key"))

    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}
    assert "ord_delete_me" in orders.ORDERS


def test_delete_order_returns_404_for_missing_order(client):
    response = client.delete("/v1/order/ord_missing", headers=auth_headers("buyer-key"))

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_delete_order_returns_500_when_persistence_delete_fails(client, monkeypatch):
    orders.ORDERS["ord_delete_me"] = build_record()

    def fail_delete_order_record(order_id: str):  # noqa: ARG001
        raise OrderPersistenceError("boom")

    monkeypatch.setattr(order_store, "delete_order_record", fail_delete_order_record)

    response = client.delete("/v1/order/ord_delete_me", headers=auth_headers("buyer-key"))

    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to delete order."}
    assert "ord_delete_me" in orders.ORDERS


def test_delete_order_removes_order_so_follow_up_get_returns_404(client):
    orders.ORDERS["ord_delete_me"] = build_record()

    delete_response = client.delete("/v1/order/ord_delete_me", headers=auth_headers("buyer-key"))
    get_response = client.get("/v1/order/ord_delete_me", headers=auth_headers("buyer-key"))

    assert delete_response.status_code == 204
    assert get_response.status_code == 404
