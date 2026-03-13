from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.routes import parties
from app.main import app
from app.models.schemas import PartyRegistrationResponse
from app.services.party_registration import DuplicatePartyError


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def build_payload() -> dict:
    return {
        "partyName": "Acme Books",
        "contactEmail": "team@acmebooks.com",
    }


def test_register_party_returns_201_with_party_credentials(client, monkeypatch):
    monkeypatch.setattr(
        parties,
        "register_party",
        lambda _req: PartyRegistrationResponse(
            partyId="acme-books",
            partyName="Acme Books",
            appKey="appkey_test_value",
            message="Store this key securely. It will not be shown again.",
        ),
    )

    response = client.post("/v1/parties/register", json=build_payload())

    assert response.status_code == 201
    assert response.json() == {
        "partyId": "acme-books",
        "partyName": "Acme Books",
        "appKey": "appkey_test_value",
        "message": "Store this key securely. It will not be shown again.",
    }


def test_register_party_returns_409_for_duplicate_contact_email(client, monkeypatch):
    def fail_register_party(_req):
        raise DuplicatePartyError("A party with this contact email already exists.")

    monkeypatch.setattr(parties, "register_party", fail_register_party)

    response = client.post("/v1/parties/register", json=build_payload())

    assert response.status_code == 409
    assert response.json() == {"detail": "A party with this contact email already exists."}


@pytest.mark.parametrize(
    "payload",
    [
        {"contactEmail": "team@acmebooks.com"},
        {"partyName": "Acme Books"},
        {"partyName": "", "contactEmail": "team@acmebooks.com"},
        {"partyName": "Acme Books", "contactEmail": ""},
    ],
)
def test_register_party_rejects_invalid_payloads(client, payload):
    response = client.post("/v1/parties/register", json=payload)

    assert response.status_code == 422
