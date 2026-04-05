from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.routes import parties
from app.main import app
from app.models.schemas import PartyAuthV2Response, PartyRegistrationResponse, PartyUserFetchResponse
from app.services.party_registration import DuplicatePartyError
from app.services.party_password_auth import DuplicatePartyV2Error


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def build_payload() -> dict:
    return {
        "partyName": "Acme Books",
        "contactEmail": "team@acmebooks.com",
    }


def build_v2_register_payload() -> dict:
    return {
        "partyName": "Acme Books",
        "contactEmail": "team@acmebooks.com",
        "password": "super-secure-password",
    }


def build_v2_login_payload() -> dict:
    return {
        "contactEmail": "team@acmebooks.com",
        "password": "super-secure-password",
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


def test_user_fetch_returns_current_party_for_valid_app_key(client, monkeypatch):
    app.dependency_overrides[parties.get_current_party_email] = lambda: "orders@acmebooks.example"
    monkeypatch.setattr(
        parties,
        "findPartyByContactEmail",
        lambda email: {
            "party_id": email,
            "party_name": "Acme Books",
            "contact_email": email,
        },
    )

    response = client.get("/v1/parties/userFetch", headers={"Authorization": "Bearer appkey_test"})

    assert response.status_code == 200
    assert response.json() == PartyUserFetchResponse(
        partyId="orders@acmebooks.example",
        partyName="Acme Books",
        contactEmail="orders@acmebooks.example",
    ).model_dump()


def test_user_fetch_returns_401_when_party_lookup_fails(client, monkeypatch):
    app.dependency_overrides[parties.get_current_party_email] = lambda: "orders@acmebooks.example"
    monkeypatch.setattr(parties, "findPartyByContactEmail", lambda _email: None)

    response = client.get("/v1/parties/userFetch", headers={"Authorization": "Bearer appkey_test"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_register_party_v2_returns_201_with_party_identity(client, monkeypatch):
    monkeypatch.setattr(
        parties,
        "register_party_v2",
        lambda _req: PartyAuthV2Response(
            partyId="team@acmebooks.com",
            partyName="Acme Books",
            contactEmail="team@acmebooks.com",
        ),
    )

    response = client.post("/v2/parties/register", json=build_v2_register_payload())

    assert response.status_code == 201
    assert response.json() == {
        "partyId": "team@acmebooks.com",
        "partyName": "Acme Books",
        "contactEmail": "team@acmebooks.com",
    }


def test_register_party_v2_returns_409_for_duplicate_contact_email(client, monkeypatch):
    def fail_register_party(_req):
        raise DuplicatePartyV2Error("A party with this contact email already exists.")

    monkeypatch.setattr(parties, "register_party_v2", fail_register_party)

    response = client.post("/v2/parties/register", json=build_v2_register_payload())

    assert response.status_code == 409
    assert response.json() == {"detail": "A party with this contact email already exists."}


def test_login_party_v2_returns_200_with_party_identity(client, monkeypatch):
    monkeypatch.setattr(
        parties,
        "login_party_v2",
        lambda _req: PartyAuthV2Response(
            partyId="team@acmebooks.com",
            partyName="Acme Books",
            contactEmail="team@acmebooks.com",
        ),
    )

    response = client.post("/v2/parties/login", json=build_v2_login_payload())

    assert response.status_code == 200
    assert response.json() == {
        "partyId": "team@acmebooks.com",
        "partyName": "Acme Books",
        "contactEmail": "team@acmebooks.com",
    }


def test_login_party_v2_returns_401_for_invalid_credentials(client, monkeypatch):
    def fail_login(_req):
        raise HTTPException(status_code=401, detail="Unauthorized")

    monkeypatch.setattr(parties, "login_party_v2", fail_login)

    response = client.post("/v2/parties/login", json=build_v2_login_payload())

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


@pytest.mark.parametrize(
    "payload",
    [
        {"contactEmail": "team@acmebooks.com"},
        {"partyName": "Acme Books"},
        {"partyName": "", "contactEmail": "team@acmebooks.com"},
        {"partyName": "Acme Books", "contactEmail": ""},
        {"partyName": "Acme Books", "contactEmail": "test@test"},
        {"partyName": "Acme Books", "contactEmail": "testing@testing"},
        {"partyName": "Acme Books", "contactEmail": "lockedout@test"},
    ],
)
def test_register_party_rejects_invalid_payloads(client, payload):
    response = client.post("/v1/parties/register", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["message"] == "Request validation failed."
    assert body["errors"]


@pytest.mark.parametrize(
    "payload",
    [
        {"partyName": "Acme Books", "contactEmail": "team@acmebooks.com"},
        {"partyName": "Acme Books", "contactEmail": "team@acmebooks.com", "password": "short"},
    ],
)
def test_register_party_v2_rejects_invalid_payloads(client, payload):
    response = client.post("/v2/parties/register", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["message"] == "Request validation failed."
    assert body["errors"]


@pytest.mark.parametrize(
    "payload",
    [
        {"contactEmail": "team@acmebooks.com"},
        {"contactEmail": "team@acmebooks.com", "password": "short"},
    ],
)
def test_login_party_v2_rejects_invalid_payloads(client, payload):
    response = client.post("/v2/parties/login", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["message"] == "Request validation failed."
    assert body["errors"]
