from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

import app.other as other
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
            "buyerEmail": "buyer@example.com",
            "buyerName": "Acme Books",
            "sellerEmail": "seller@example.com",
            "sellerName": "Digital Book Supply",
            "lines": [{"productName": "Book", "quantity": 1, "unitCode": "EA"}],
        },
        "ublXml": "<Order />",
        "dbOrderId": "42",
    }


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


@pytest.fixture
def db_records(monkeypatch):
    records: dict[str, dict] = {}

    def load_order_record_from_database(order_id: str):
        record = records.get(order_id)
        return deepcopy(record) if record else None

    def delete_order(order_db_id):
        doomed = next(
            (key for key, value in records.items() if value.get("dbOrderId") == str(order_db_id)),
            None,
        )
        if doomed is not None:
            records.pop(doomed, None)

    monkeypatch.setattr(
        order_store, "load_order_record_from_database", load_order_record_from_database
    )
    monkeypatch.setattr(other, "deleteOrderDetails", lambda order_id: None)
    monkeypatch.setattr(other, "deleteOrder", delete_order)
    return records


def auth_headers(app_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {app_key}"}


def test_delete_order_returns_204_for_buyer(client, db_records):
    db_records["ord_delete_me"] = build_record()

    response = client.delete("/v1/order/ord_delete_me", headers=auth_headers("buyer-key"))

    assert response.status_code == 204
    assert "ord_delete_me" not in orders.ORDERS


def test_delete_order_returns_204_for_seller(client, db_records):
    db_records["ord_delete_me"] = build_record()

    response = client.delete("/v1/order/ord_delete_me", headers=auth_headers("seller-key"))

    assert response.status_code == 204
    assert "ord_delete_me" not in orders.ORDERS


def test_delete_order_returns_401_when_auth_header_is_missing(client, db_records):
    db_records["ord_delete_me"] = build_record()

    response = client.delete("/v1/order/ord_delete_me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}
    assert "ord_delete_me" not in orders.ORDERS


def test_delete_order_returns_401_for_malformed_auth_header(client, db_records):
    db_records["ord_delete_me"] = build_record()

    response = client.delete(
        "/v1/order/ord_delete_me",
        headers={"Authorization": "Basic buyer-key"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}
    assert "ord_delete_me" not in orders.ORDERS


def test_delete_order_returns_401_for_unknown_app_key(client, db_records):
    db_records["ord_delete_me"] = build_record()

    response = client.delete("/v1/order/ord_delete_me", headers=auth_headers("unknown-key"))

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}
    assert "ord_delete_me" not in orders.ORDERS


def test_delete_order_returns_403_for_non_party_caller(client, db_records):
    db_records["ord_delete_me"] = build_record()

    response = client.delete("/v1/order/ord_delete_me", headers=auth_headers("other-key"))

    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}
    assert "ord_delete_me" in orders.ORDERS


def test_delete_order_returns_404_for_missing_order(client):
    response = client.delete("/v1/order/ord_missing", headers=auth_headers("buyer-key"))

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_delete_order_returns_500_when_persistence_delete_fails(client, monkeypatch, db_records):
    db_records["ord_delete_me"] = build_record()

    def fail_delete_order_record(order_id: str):  # noqa: ARG001
        raise OrderPersistenceError("boom")

    monkeypatch.setattr(order_store, "delete_order_record", fail_delete_order_record)

    response = client.delete("/v1/order/ord_delete_me", headers=auth_headers("buyer-key"))

    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to delete order."}
    assert "ord_delete_me" in orders.ORDERS


def test_delete_order_removes_order_so_follow_up_get_returns_404(client, db_records):
    db_records["ord_delete_me"] = build_record()

    delete_response = client.delete("/v1/order/ord_delete_me", headers=auth_headers("buyer-key"))
    get_response = client.get("/v1/order/ord_delete_me", headers=auth_headers("buyer-key"))

    assert delete_response.status_code == 204
    assert get_response.status_code == 404
