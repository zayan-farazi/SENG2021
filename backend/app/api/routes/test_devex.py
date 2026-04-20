from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.routes import orders
from app.main import app
from app.services import order_store
from app.services.app_key_auth import get_current_party_email


# -------------------------
# Helpers
# -------------------------

def build_record(order_id: str = "ord_despatch") -> dict:
    return {
        "orderId": order_id,
        "status": "DRAFT",
        "createdAt": "2026-04-20T00:00:00Z",
        "updatedAt": "2026-04-20T00:00:00Z",
        "payload": {
            "buyerEmail": "buyer@example.com",
            "sellerEmail": "seller@example.com",
        },
        "ublXml": "<Order />",
        "dbOrderId": "99",
    }


def auth_override(email: str):
    def _override():
        return email
    return _override


def auth_headers(app_key: str) -> dict:
    return {"Authorization": f"Bearer {app_key}"}


# -------------------------
# Fixtures
# -------------------------

@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_store(monkeypatch):
    store = {}

    def get_order(order_id: str):
        return store.get(order_id)

    def delete_order(order_id: str):
        store.pop(order_id, None)
        return True

    monkeypatch.setattr(order_store, "get_order_record", get_order)
    monkeypatch.setattr(order_store, "delete_order_record", delete_order)

    return store


# -------------------------
# DESPATCH TESTS (POST)
# -------------------------

def test_despatch_returns_404_if_order_missing(client):
    app.dependency_overrides[get_current_party_email] = auth_override("seller@example.com")

    response = client.post("/v1/order/missing/despatch")

    assert response.status_code == 404


def test_despatch_success_creates_and_returns_xml(client, monkeypatch, mock_store):
    mock_store["ord_despatch"] = build_record()

    app.dependency_overrides[get_current_party_email] = auth_override("seller@example.com")

    async def mock_create(xml):
        return {"adviceId": "ADV-123", "xml": "<DespatchAdvice>OK</DespatchAdvice>"}

    monkeypatch.setattr(orders, "create_despatch_from_order_xml", mock_create)
    monkeypatch.setattr(orders, "getXml", lambda *args, **kwargs: [])

    response = client.post("/v1/order/ord_despatch/despatch")

    assert response.status_code == 200
    assert response.json()["orderId"] == "ord_despatch"


def test_despatch_returns_existing_if_already_present(client, monkeypatch, mock_store):
    mock_store["ord_despatch"] = build_record()

    app.dependency_overrides[get_current_party_email] = auth_override("seller@example.com")

    monkeypatch.setattr(
        orders,
        "getXml",
        lambda *args, **kwargs: [{"ublxml": "<DespatchAdvice>EXISTING</DespatchAdvice>"}],
    )

    response = client.post("/v1/order/ord_despatch/despatch")

    assert response.status_code == 200
    assert "EXISTING" in response.json()["despatch"]["xml"]


def test_despatch_fails_if_not_seller(client, mock_store):
    mock_store["ord_despatch"] = build_record()

    app.dependency_overrides[get_current_party_email] = auth_override("buyer@example.com")

    response = client.post("/v1/order/ord_despatch/despatch")

    assert response.status_code == 403


def test_despatch_returns_500_if_no_xml(client, mock_store):
    record = build_record()
    record["ublXml"] = None
    mock_store["ord_despatch"] = record

    app.dependency_overrides[get_current_party_email] = auth_override("seller@example.com")

    response = client.post("/v1/order/ord_despatch/despatch")

    assert response.status_code == 500


def test_despatch_returns_500_if_devex_fails(client, monkeypatch, mock_store):
    mock_store["ord_despatch"] = build_record()

    app.dependency_overrides[get_current_party_email] = auth_override("seller@example.com")

    async def fail(*args, **kwargs):
        raise Exception("boom")

    monkeypatch.setattr(orders, "create_despatch_from_order_xml", fail)
    monkeypatch.setattr(orders, "getXml", lambda *args, **kwargs: [])

    response = client.post("/v1/order/ord_despatch/despatch")

    assert response.status_code == 500


# -------------------------
# GET DESPATCH XML TESTS
# -------------------------

def test_get_despatch_xml_success(client, monkeypatch, mock_store):
    mock_store["ord_despatch"] = build_record()

    app.dependency_overrides[get_current_party_email] = auth_override("seller@example.com")

    monkeypatch.setattr(
        orders,
        "getXml",
        lambda *args, **kwargs: [{"ublxml": "<DespatchAdvice>OK</DespatchAdvice>"}],
    )

    response = client.get("/v1/order/ord_despatch/despatch/xml")

    assert response.status_code == 200


def test_get_despatch_xml_403_if_not_participant(client, mock_store):
    mock_store["ord_despatch"] = build_record()

    app.dependency_overrides[get_current_party_email] = auth_override("other@example.com")

    response = client.get("/v1/order/ord_despatch/despatch/xml")

    assert response.status_code == 403