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


def test_get_current_party_id_resolves_party_from_valid_app_key(monkeypatch):
    monkeypatch.setattr(
        app_key_auth,
        "findAppKeyByHash",
        lambda key_hash: {"party_id": "buyer-123"} if key_hash else None,
    )

    party_id = app_key_auth.get_current_party_id("Bearer appkey_secret")

    assert party_id == "buyer-123"


def test_get_current_party_id_rejects_unknown_app_key(monkeypatch):
    monkeypatch.setattr(app_key_auth, "findAppKeyByHash", lambda _key_hash: None)

    with pytest.raises(HTTPException) as exc_info:
        app_key_auth.get_current_party_id("Bearer appkey_secret")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Unauthorized"
