from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import app_key_auth, order_store
from app.services.party_registration import hash_app_key


def auth_headers(app_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {app_key}"}


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


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


def test_list_orders_returns_paginated_summaries(client, monkeypatch):
    monkeypatch.setattr(
        order_store,
        "list_orders_for_party",
        lambda email, *, limit, offset: {
            "items": [
                {
                    "orderId": "ord_abc123def456",
                    "status": "DRAFT",
                    "createdAt": "2026-03-14T10:30:00Z",
                    "updatedAt": "2026-03-14T11:00:00Z",
                    "buyerName": "Buyer Co",
                    "sellerName": "Supplier Pty Ltd",
                    "issueDate": "2026-03-14",
                }
            ],
            "page": {"limit": limit, "offset": offset, "hasMore": False, "total": 1},
        },
    )

    response = client.get(
        "/v1/orders?limit=5&offset=10",
        headers=auth_headers("buyer-key"),
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "orderId": "ord_abc123def456",
                "status": "DRAFT",
                "createdAt": "2026-03-14T10:30:00Z",
                "updatedAt": "2026-03-14T11:00:00Z",
                "buyerName": "Buyer Co",
                "sellerName": "Supplier Pty Ltd",
                "issueDate": "2026-03-14",
            }
        ],
        "page": {"limit": 5, "offset": 10, "hasMore": False, "total": 1},
    }


def test_list_orders_passes_authenticated_party_email_to_store(client, monkeypatch):
    captured: list[tuple[str, int, int]] = []

    def fake_list(email: str, *, limit: int, offset: int):
        captured.append((email, limit, offset))
        return {
            "items": [],
            "page": {"limit": limit, "offset": offset, "hasMore": False, "total": 0},
        }

    monkeypatch.setattr(order_store, "list_orders_for_party", fake_list)

    response = client.get("/v1/orders?limit=3&offset=6", headers=auth_headers("seller-key"))

    assert response.status_code == 200
    assert captured == [("seller@example.com", 3, 6)]


def test_list_orders_returns_401_when_auth_header_is_missing(client):
    response = client.get("/v1/orders")

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_list_orders_returns_422_for_invalid_limit(client):
    response = client.get("/v1/orders?limit=0", headers=auth_headers("buyer-key"))

    assert response.status_code == 422
    body = response.json()
    assert body["message"] == "Request validation failed."
    assert body["errors"][0]["source"] == "query"
    assert body["errors"][0]["path"] == "limit"


def test_list_orders_returns_422_for_invalid_offset(client):
    response = client.get("/v1/orders?offset=-1", headers=auth_headers("buyer-key"))

    assert response.status_code == 422
    body = response.json()
    assert body["message"] == "Request validation failed."
    assert body["errors"][0]["source"] == "query"
    assert body["errors"][0]["path"] == "offset"
