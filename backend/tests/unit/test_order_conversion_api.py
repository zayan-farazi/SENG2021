from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import OrderRequest
from app.services import app_key_auth, order_conversion
from app.services.party_registration import hash_app_key


def build_payload() -> dict:
    return {
        "buyerEmail": "buyer@example.com",
        "buyerName": "Buyer Co",
        "sellerEmail": "seller@example.com",
        "sellerName": "Seller Co",
        "currency": "AUD",
        "issueDate": "2026-03-14",
        "notes": "Created from helper",
        "delivery": {
            "street": "1 Helper St",
            "city": "Sydney",
            "state": "NSW",
            "postcode": "2000",
            "country": "AU",
            "requestedDate": "2026-03-20",
        },
        "lines": [{"productName": "Oranges", "quantity": 3, "unitCode": "EA", "unitPrice": "4.25"}],
    }


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
            "party_name": "Acme Books"
        },
        hash_app_key("seller-key"): {
            "party_id": "seller-party", 
            "contact_email": "seller@example.com", 
            "party_name": "Digital Book Supply"
        },
        hash_app_key("other-key"): {
            "party_id": "other-party", 
            "contact_email": "other@example.com", 
            "party_name": "Other Company"
        },
    }
    monkeypatch.setattr(app_key_auth, "findAppKeyByHash", lambda key_hash: key_map.get(key_hash))
    yield
    app.dependency_overrides.clear()


def test_transcript_conversion_returns_payload_for_authorized_buyer(client, monkeypatch):
    async def fake_convert(transcript, current_payload):  # noqa: ARG001
        return order_conversion.ConversionResult(
            draft=order_conversion.order_request_to_draft(
                OrderRequest.model_validate(build_payload())
            ),
            warnings=[],
            issues=[],
        )

    monkeypatch.setattr(order_conversion, "convert_transcript_to_draft", fake_convert)

    response = client.post(
        "/v1/orders/convert/transcript",
        json={"transcript": "turn this into an order"},
        headers=auth_headers("buyer-key"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["source"] == "transcript"
    assert body["issues"] == []
    assert "warnings" not in body
    assert body["payload"]["buyerEmail"] == "buyer@example.com"


def test_transcript_conversion_returns_403_for_unrelated_party(client, monkeypatch):
    async def fake_convert(transcript, current_payload):  # noqa: ARG001
        return order_conversion.ConversionResult(
            draft=order_conversion.order_request_to_draft(
                OrderRequest.model_validate(build_payload())
            ),
            warnings=[],
            issues=[],
        )

    monkeypatch.setattr(order_conversion, "convert_transcript_to_draft", fake_convert)

    response = client.post(
        "/v1/orders/convert/transcript",
        json={"transcript": "turn this into an order"},
        headers=auth_headers("other-key"),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}


def test_transcript_conversion_returns_401_when_auth_header_is_missing(client):
    response = client.post("/v1/orders/convert/transcript", json={"transcript": "hello"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}
