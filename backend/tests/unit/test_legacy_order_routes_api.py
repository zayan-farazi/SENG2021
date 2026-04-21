from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.api.routes import invoices, orders
from app.main import app
from app.services import app_key_auth, order_store
from app.services.party_registration import hash_app_key


def auth_headers(app_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {app_key}"}


def build_legacy_record(order_id: str = "ord_legacy_42", status: str = "SUBMITTED") -> dict:
    return {
        "orderId": order_id,
        "status": status,
        "createdAt": "2026-03-12T10:00:00Z",
        "updatedAt": "2026-03-14T10:00:00Z",
        "payload": {
            "buyerEmail": "buyer@example.com",
            "buyerName": "Buyer Co",
            "sellerEmail": "seller@example.com",
            "sellerName": "Seller Co",
            "currency": "AUD",
            "issueDate": "2026-03-12",
            "notes": "Legacy order",
            "lines": [
                {
                    "productName": "Legacy Product",
                    "quantity": 1,
                    "unitCode": "EA",
                    "unitPrice": "10.00",
                }
            ],
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
def stub_app_key_lookup(monkeypatch):
    app.dependency_overrides.clear()
    key_map = {
        hash_app_key("buyer-key"): {
            "party_id": "buyer-party",
            "contact_email": "buyer@example.com",
            "party_name": "Buyer Co",
        },
        hash_app_key("seller-key"): {
            "party_id": "seller-party",
            "contact_email": "seller@example.com",
            "party_name": "Seller Co",
        },
        hash_app_key("other-key"): {
            "party_id": "other-party",
            "contact_email": "other@example.com",
            "party_name": "Other Co",
        },
    }
    monkeypatch.setattr(app_key_auth, "findAppKeyByHash", lambda key_hash: key_map.get(key_hash))
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def legacy_record(monkeypatch):
    record = build_legacy_record()

    def _get_order_record(order_id: str):
        if order_id == record["orderId"]:
            return deepcopy(record)
        return None

    monkeypatch.setattr(order_store, "get_order_record", _get_order_record)
    return record


def test_legacy_order_id_route_gets_order(client, legacy_record):
    response = client.get(
        f"/v1/order/{legacy_record['orderId']}", headers=auth_headers("buyer-key")
    )

    assert response.status_code == 200
    assert response.json()["orderId"] == legacy_record["orderId"]


def test_legacy_order_id_route_gets_payload(client, legacy_record):
    response = client.get(
        f"/v1/order/{legacy_record['orderId']}/payload",
        headers=auth_headers("seller-key"),
    )

    assert response.status_code == 200
    assert response.json()["payload"]["buyerEmail"] == "buyer@example.com"


def test_legacy_order_id_route_gets_ubl(client, legacy_record):
    response = client.get(
        f"/v1/order/{legacy_record['orderId']}/ubl",
        headers=auth_headers("buyer-key"),
    )

    assert response.status_code == 200
    assert response.text == "<Order />"


def test_legacy_order_id_route_deletes_order(client, legacy_record, monkeypatch):
    deleted: list[str] = []
    monkeypatch.setattr(
        order_store, "delete_order_record", lambda order_id: deleted.append(order_id) or True
    )

    response = client.delete(
        f"/v1/order/{legacy_record['orderId']}",
        headers=auth_headers("buyer-key"),
    )

    assert response.status_code == 204
    assert deleted == [legacy_record["orderId"]]


def test_legacy_order_id_route_submits_order(client, legacy_record, monkeypatch):
    draft_record = build_legacy_record(status="DRAFT")
    monkeypatch.setattr(
        order_store,
        "get_order_record",
        lambda order_id: deepcopy(draft_record) if order_id == draft_record["orderId"] else None,
    )
    monkeypatch.setattr(
        order_store,
        "submit_order_record",
        lambda order_id: {
            **deepcopy(draft_record),
            "status": "SUBMITTED",
            "updatedAt": "2026-03-14T11:00:00Z",
        },
    )

    response = client.post(
        f"/v1/order/{draft_record['orderId']}/submit",
        headers=auth_headers("buyer-key"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "SUBMITTED"


def test_legacy_order_id_route_fetches_despatch_xml(client, legacy_record, monkeypatch):
    monkeypatch.setattr(
        orders,
        "getXml",
        lambda table_name, order_id: (
            [{"xml": "<DespatchAdvice />"}]
            if table_name == "dispatch_xml" and order_id == legacy_record["orderId"]
            else []
        ),
    )

    response = client.get(
        f"/v1/order/{legacy_record['orderId']}/despatch",
        headers=auth_headers("seller-key"),
    )

    assert response.status_code == 200
    assert response.text == "<DespatchAdvice />"


def test_legacy_order_id_route_generates_invoice(client, legacy_record, monkeypatch):
    async def fake_create_invoice(payload):  # noqa: ARG001
        return {"invoiceId": "inv_123", "status": "draft"}

    monkeypatch.setattr(invoices.lastminutepush_client, "create_invoice", fake_create_invoice)

    response = client.post(
        f"/v1/order/{legacy_record['orderId']}/invoice",
        headers=auth_headers("buyer-key"),
    )

    assert response.status_code == 200
    assert response.json()["orderId"] == legacy_record["orderId"]
    assert response.json()["invoice"]["invoiceId"] == "inv_123"
