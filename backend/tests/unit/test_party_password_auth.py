from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models.schemas import PartyLoginV2Request, PartyRegistrationV2Request
from app.services import party_password_auth
from app.services.party_password_auth import DuplicatePartyV2Error, PartyAuthV2PersistenceError


def build_register_request() -> PartyRegistrationV2Request:
    return PartyRegistrationV2Request(
        partyName="Acme Books",
        contactEmail="Team@AcmeBooks.com",
        password="super-secure-password",
    )


def test_party_registration_v2_request_normalizes_contact_email():
    req = build_register_request()

    assert req.contactEmail == "team@acmebooks.com"


def test_hash_password_does_not_store_raw_password():
    raw_password = "super-secure-password"

    password_hash = party_password_auth.hash_password(raw_password)

    assert password_hash != raw_password
    assert password_hash.startswith("$2")
    assert party_password_auth.verify_password(raw_password, password_hash) is True


def test_register_party_v2_rejects_duplicate_contact_email(monkeypatch):
    req = build_register_request()
    monkeypatch.setattr(
        party_password_auth,
        "findPartyByContactEmail",
        lambda contact_email: {"contact_email": contact_email},
    )

    with pytest.raises(
        DuplicatePartyV2Error, match="A party with this contact email already exists."
    ):
        party_password_auth.register_party_v2(req)


def test_register_party_v2_persists_password_hash(monkeypatch):
    req = build_register_request()
    saved_party = {}

    monkeypatch.setattr(party_password_auth, "findPartyByContactEmail", lambda _email: None)

    def fake_save_party(party_name, contact_email, key_hash):
        saved_party.update(
            {
                "party_name": party_name,
                "contact_email": contact_email,
                "key_hash": key_hash,
            }
        )
        return saved_party

    monkeypatch.setattr(party_password_auth, "saveParty", fake_save_party)

    result = party_password_auth.register_party_v2(req)

    assert result.partyId == "team@acmebooks.com"
    assert result.partyName == "Acme Books"
    assert result.contactEmail == "team@acmebooks.com"
    assert saved_party["party_name"] == "Acme Books"
    assert saved_party["contact_email"] == "team@acmebooks.com"
    assert saved_party["key_hash"] != req.password
    assert party_password_auth.verify_password(req.password, saved_party["key_hash"]) is True


def test_register_party_v2_wraps_persistence_failures(monkeypatch):
    req = build_register_request()

    monkeypatch.setattr(party_password_auth, "findPartyByContactEmail", lambda _email: None)
    monkeypatch.setattr(
        party_password_auth,
        "saveParty",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with pytest.raises(PartyAuthV2PersistenceError, match="Unable to register party."):
        party_password_auth.register_party_v2(req)


def test_login_party_v2_rejects_unknown_contact_email(monkeypatch):
    req = PartyLoginV2Request(
        contactEmail="team@acmebooks.com",
        password="super-secure-password",
    )
    monkeypatch.setattr(party_password_auth, "findPartyByContactEmail", lambda _email: None)

    with pytest.raises(HTTPException) as exc_info:
        party_password_auth.login_party_v2(req)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Unauthorized"


def test_login_party_v2_rejects_wrong_password(monkeypatch):
    req = PartyLoginV2Request(
        contactEmail="team@acmebooks.com",
        password="wrong-password",
    )
    stored_hash = party_password_auth.hash_password("super-secure-password")
    monkeypatch.setattr(
        party_password_auth,
        "findPartyByContactEmail",
        lambda email: {
            "contact_email": email,
            "party_name": "Acme Books",
            "key_hash": stored_hash,
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        party_password_auth.login_party_v2(req)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Unauthorized"


def test_login_party_v2_returns_party_identity_for_valid_credentials(monkeypatch):
    req = PartyLoginV2Request(
        contactEmail="team@acmebooks.com",
        password="super-secure-password",
    )
    stored_hash = party_password_auth.hash_password("super-secure-password")
    monkeypatch.setattr(
        party_password_auth,
        "findPartyByContactEmail",
        lambda email: {
            "contact_email": email,
            "party_name": "Acme Books",
            "key_hash": stored_hash,
        },
    )

    result = party_password_auth.login_party_v2(req)

    assert result.partyId == "team@acmebooks.com"
    assert result.partyName == "Acme Books"
    assert result.contactEmail == "team@acmebooks.com"
