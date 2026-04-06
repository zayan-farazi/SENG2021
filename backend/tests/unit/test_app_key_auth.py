from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services import app_key_auth


def test_extract_bearer_token_returns_token_for_valid_header():
    assert app_key_auth.extract_bearer_token("Bearer appkey_secret") == "appkey_secret"


@pytest.mark.parametrize("authorization", [None, "", "Basic token", "Bearer ", "token"])
def test_extract_bearer_token_rejects_missing_or_malformed_headers(authorization):
    with pytest.raises(HTTPException) as exc_info:
        app_key_auth.extract_bearer_token(authorization)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Unauthorized"


def test_get_current_party_email_resolves_email_from_valid_app_key(monkeypatch):
    monkeypatch.setattr(
        app_key_auth,
        "findAppKeyByHash",
        lambda key_hash: (
            {
                "contact_email": "buyer@example.com",
                "party_name": "Buyer Co",
            }
            if key_hash
            else None
        ),
    )

    contact_email = app_key_auth.get_current_party_email("Bearer appkey_secret")

    assert contact_email == "buyer@example.com"


def test_get_current_party_email_rejects_unknown_app_key(monkeypatch):
    monkeypatch.setattr(app_key_auth, "findAppKeyByHash", lambda _key_hash: None)

    with pytest.raises(HTTPException) as exc_info:
        app_key_auth.get_current_party_email("Bearer appkey_secret")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Unauthorized"


def test_get_current_party_email_accepts_v2_password_with_party_email_header(monkeypatch):
    monkeypatch.setattr(app_key_auth, "findAppKeyByHash", lambda _key_hash: None)
    monkeypatch.setattr(
        app_key_auth,
        "authenticate_party_v2",
        lambda party_email, raw_password: type(
            "PartyAuthResult",
            (),
            {
                "contactEmail": party_email if raw_password else None,
                "partyName": "Buyer Co",
            },
        )(),
    )

    contact_email = app_key_auth.get_current_party_email(
        "Bearer super-secure-password",
        "buyer@example.com",
    )

    assert contact_email == "buyer@example.com"


def test_get_current_party_email_rejects_missing_party_email(monkeypatch):
    monkeypatch.setattr(
        app_key_auth,
        "findAppKeyByHash",
        lambda key_hash: {"contact_email": ""} if key_hash else None,
    )

    with pytest.raises(HTTPException) as exc_info:
        app_key_auth.get_current_party_email("Bearer appkey_secret")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Unauthorized"
