from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

import app.other as other
from app.main import app
from app.services.party_registration import hash_app_key

pytestmark = pytest.mark.integration


def build_payload() -> dict:
    return {
        "partyName": "Integration Party Registration",
        "contactEmail": "integration-registration@example.com",
    }


def test_register_party_persists_party_and_hashed_app_key_in_supabase():
    # To run this test, set SUPABASE_URL and SUPABASE_KEY in backend/.env or your shell,
    # then run `cd backend && ./.venv/bin/python -m pytest tests/test_party_registration_integration.py -q`.
    # This test verifies that party registration stores the hashed app key on the
    # parties row, and that the raw returned appKey is not stored directly in Supabase.
    if not (os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY")):
        other._load_local_env_files()
    if not (os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY")):
        pytest.skip("SUPABASE_URL and SUPABASE_KEY must be configured to run this test.")

    other._SUPABASE_CLIENT = None
    payload = build_payload()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/v1/parties/register", json=payload)

    assert response.status_code == 201
    body = response.json()
    party_id = body["partyId"]
    app_key = body["appKey"]

    try:
        party_row = other.findPartyByPartyId(party_id)
        app_key_row = other.findAppKeyByHash(hash_app_key(app_key))

        assert party_row is not None
        assert party_row["party_name"] == payload["partyName"]
        assert party_row["contact_email"] == payload["contactEmail"]
        assert app_key_row is not None
        assert app_key_row["contact_email"] == party_id
        assert app_key_row["key_hash"] != app_key
    finally:
        client = None
        try:
            client = other.get_supabase_client()
        except RuntimeError:
            client = None
        if client:
            client.table("parties").delete().eq("contact_email", party_id).execute()
        other._SUPABASE_CLIENT = None
