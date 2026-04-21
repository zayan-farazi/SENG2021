from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _override_auth(email: str = "buyer@example.com"):
    from app.services.app_key_auth import get_current_party_email

    app.dependency_overrides[get_current_party_email] = lambda: email


def test_update_invoice_returns_200_and_payload(client, monkeypatch):
    _override_auth()

    async def fake_update(invoice_id: str, body: dict):  # noqa: ARG001
        return {
            "message": "Invoice updated successfully",
            "invoice_id": invoice_id,
            "updated_at": "2026-03-16T01:30:00Z",
        }

    monkeypatch.setattr("app.api.routes.invoices.lastminutepush_client.update_invoice", fake_update)

    resp = client.put("/v1/invoice/INV-1", json={"currency": "USD"})
    assert resp.status_code == 200
    assert resp.json()["invoice_id"] == "INV-1"


def test_update_invoice_returns_502_when_downstream_fails(client, monkeypatch):
    _override_auth()

    async def boom(invoice_id: str, body: dict):  # noqa: ARG001
        raise RuntimeError("downstream error")

    monkeypatch.setattr("app.api.routes.invoices.lastminutepush_client.update_invoice", boom)

    resp = client.put("/v1/invoice/INV-1", json={"currency": "USD"})
    assert resp.status_code == 502
    assert resp.json() == {"detail": "Invoice service failed."}


def test_delete_invoice_returns_204(client, monkeypatch):
    _override_auth()

    async def fake_delete(invoice_id: str):  # noqa: ARG001
        return None

    monkeypatch.setattr("app.api.routes.invoices.lastminutepush_client.delete_invoice", fake_delete)

    resp = client.delete("/v1/invoice/INV-1")
    assert resp.status_code == 204
    assert resp.content == b""


def test_delete_invoice_returns_502_when_downstream_fails(client, monkeypatch):
    _override_auth()

    async def boom(invoice_id: str):  # noqa: ARG001
        raise RuntimeError("downstream error")

    monkeypatch.setattr("app.api.routes.invoices.lastminutepush_client.delete_invoice", boom)

    resp = client.delete("/v1/invoice/INV-1")
    assert resp.status_code == 502
    assert resp.json() == {"detail": "Invoice service failed."}


def test_transition_status_returns_200(client, monkeypatch):
    _override_auth()

    async def fake_transition(invoice_id: str, body: dict):  # noqa: ARG001
        return {
            "message": "Invoice status updated successfully",
            "invoice_id": invoice_id,
            "previous_status": "draft",
            "status": body["status"],
            "payment_date": body.get("payment_date"),
            "updated_at": "2026-03-16T01:35:00Z",
        }

    monkeypatch.setattr(
        "app.api.routes.invoices.lastminutepush_client.transition_invoice_status", fake_transition
    )

    resp = client.post("/v1/invoice/INV-1/status", json={"status": "sent"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"


def test_transition_status_returns_502_when_downstream_fails(client, monkeypatch):
    _override_auth()

    async def boom(invoice_id: str, body: dict):  # noqa: ARG001
        raise RuntimeError("downstream error")

    monkeypatch.setattr(
        "app.api.routes.invoices.lastminutepush_client.transition_invoice_status", boom
    )

    resp = client.post("/v1/invoice/INV-1/status", json={"status": "sent"})
    assert resp.status_code == 502
    assert resp.json() == {"detail": "Invoice service failed."}
