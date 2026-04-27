from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.integrations.lastminutepush_client import InvoiceServiceError
from app.main import app


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _override_auth(email: str):
    from app.services.app_key_auth import get_current_party_email

    app.dependency_overrides[get_current_party_email] = lambda: email


def test_generate_invoice_returns_500_when_order_missing_participant_emails(client, monkeypatch):
    """
    Covers:
      - _assert_invoice_access 500 path: missing buyerEmail or sellerEmail
    """
    _override_auth("buyer@example.com")

    fake_order = {
        "orderId": "ord_1",
        "payload": {
            "buyerName": "Buyer Co",
            # buyerEmail missing
            "sellerEmail": "seller@example.com",
            "sellerName": "Seller Pty Ltd",
            "lines": [
                {"productName": "Oranges", "quantity": 1, "unitCode": "EA", "unitPrice": "1.00"}
            ],
        },
    }

    monkeypatch.setattr(
        "app.api.routes.invoices.order_store.get_order_record",
        lambda order_id: fake_order if order_id == "ord_1" else None,
    )

    resp = client.post("/v1/order/ord_1/invoice")
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Order participant email information missing."}


def test_generate_invoice_returns_403_when_caller_not_buyer_or_seller(client, monkeypatch):
    """
    Covers:
      - _assert_invoice_access 403 path: caller email is neither buyer nor seller
    """
    _override_auth("intruder@example.com")

    fake_order = {
        "orderId": "ord_2",
        "payload": {
            "buyerEmail": "buyer@example.com",
            "buyerName": "Buyer Co",
            "sellerEmail": "seller@example.com",
            "sellerName": "Seller Pty Ltd",
            "lines": [
                {"productName": "Oranges", "quantity": 1, "unitCode": "EA", "unitPrice": "1.00"}
            ],
        },
    }

    monkeypatch.setattr(
        "app.api.routes.invoices.order_store.get_order_record",
        lambda order_id: fake_order if order_id == "ord_2" else None,
    )

    resp = client.post("/v1/order/ord_2/invoice")
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Forbidden"}


def test_generate_invoice_returns_400_when_unitprice_missing(client, monkeypatch):
    """
    Covers:
      - the 400 branch when any line has unitPrice missing
    """
    _override_auth("buyer@example.com")

    fake_order = {
        "orderId": "ord_3",
        "payload": {
            "buyerEmail": "buyer@example.com",
            "buyerName": "Buyer Co",
            "sellerEmail": "seller@example.com",
            "sellerName": "Seller Pty Ltd",
            "lines": [
                {"productName": "Oranges", "quantity": 1, "unitCode": "EA"},  # unitPrice missing
            ],
        },
    }

    monkeypatch.setattr(
        "app.api.routes.invoices.order_store.get_order_record",
        lambda order_id: fake_order if order_id == "ord_3" else None,
    )

    resp = client.post("/v1/order/ord_3/invoice")
    assert resp.status_code == 400
    body = resp.json()
    assert isinstance(body["detail"], list)
    assert body["detail"][0]["path"] == "lines[0].unitPrice"


def test_generate_invoice_returns_502_when_invoice_service_rejects_api_key(client, monkeypatch):
    """
    Covers downstream auth failures from the invoice service.
    """
    _override_auth("buyer@example.com")

    fake_order = {
        "orderId": "ord_4",
        "payload": {
            "buyerEmail": "buyer@example.com",
            "buyerName": "Buyer Co",
            "sellerEmail": "seller@example.com",
            "sellerName": "Seller Pty Ltd",
            "currency": "AUD",
            "issueDate": "2026-03-14",
            "lines": [
                {"productName": "Oranges", "quantity": 1, "unitCode": "EA", "unitPrice": "1.00"}
            ],
        },
    }

    monkeypatch.setattr(
        "app.api.routes.invoices.order_store.get_order_record",
        lambda order_id: fake_order if order_id == "ord_4" else None,
    )

    async def boom(_payload):  # noqa: ARG001
        raise InvoiceServiceError(
            reason="auth",
            message="unauthorized",
            status_code=401,
            response_body='{"error":"UNAUTHORIZED"}',
        )

    monkeypatch.setattr("app.api.routes.invoices.lastminutepush_client.create_invoice", boom)

    resp = client.post("/v1/order/ord_4/invoice")
    assert resp.status_code == 502
    assert resp.json() == {"detail": "Invoice service rejected the API key."}


def test_generate_invoice_returns_502_when_invoice_service_rejects_payload(client, monkeypatch):
    _override_auth("buyer@example.com")

    fake_order = {
        "orderId": "ord_5",
        "payload": {
            "buyerEmail": "buyer@example.com",
            "buyerName": "Buyer Co",
            "sellerEmail": "seller@example.com",
            "sellerName": "Seller Pty Ltd",
            "currency": "AUD",
            "issueDate": "2026-03-14",
            "lines": [
                {"productName": "Oranges", "quantity": 1, "unitCode": "EA", "unitPrice": "1.00"}
            ],
        },
    }

    monkeypatch.setattr(
        "app.api.routes.invoices.order_store.get_order_record",
        lambda order_id: fake_order if order_id == "ord_5" else None,
    )

    async def boom(_payload):  # noqa: ARG001
        raise InvoiceServiceError(
            reason="payload",
            message="unprocessable",
            status_code=422,
            response_body='{"error":"VALIDATION_ERROR"}',
        )

    monkeypatch.setattr("app.api.routes.invoices.lastminutepush_client.create_invoice", boom)

    resp = client.post("/v1/order/ord_5/invoice")
    assert resp.status_code == 502
    assert resp.json() == {"detail": "Invoice service rejected the payload."}


def test_generate_invoice_returns_502_when_invoice_service_is_unavailable(client, monkeypatch):
    _override_auth("buyer@example.com")

    fake_order = {
        "orderId": "ord_6",
        "payload": {
            "buyerEmail": "buyer@example.com",
            "buyerName": "Buyer Co",
            "sellerEmail": "seller@example.com",
            "sellerName": "Seller Pty Ltd",
            "currency": "AUD",
            "issueDate": "2026-03-14",
            "lines": [
                {"productName": "Oranges", "quantity": 1, "unitCode": "EA", "unitPrice": "1.00"}
            ],
        },
    }

    monkeypatch.setattr(
        "app.api.routes.invoices.order_store.get_order_record",
        lambda order_id: fake_order if order_id == "ord_6" else None,
    )

    async def boom(_payload):  # noqa: ARG001
        raise InvoiceServiceError(reason="unavailable", message="timeout")

    monkeypatch.setattr("app.api.routes.invoices.lastminutepush_client.create_invoice", boom)

    resp = client.post("/v1/order/ord_6/invoice")
    assert resp.status_code == 502
    assert resp.json() == {"detail": "Invoice service is unavailable."}
