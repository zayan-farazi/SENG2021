from __future__ import annotations

import re

import pytest

from app.models.schemas import PartyRegistrationRequest
from app.services import party_registration
from app.services.party_registration import DuplicatePartyError, PartyRegistrationPersistenceError


def build_request() -> PartyRegistrationRequest:
    return PartyRegistrationRequest(
        partyName="Acme Books",
        contactEmail="Team@AcmeBooks.com",
    )


def test_party_registration_request_normalizes_contact_email():
    req = build_request()

    assert req.contactEmail == "team@acmebooks.com"


def test_generate_party_id_slugifies_party_name(monkeypatch):
    monkeypatch.setattr(party_registration, "findPartyByPartyId", lambda _party_id: None)

    party_id = party_registration.generate_party_id("Acme Books Pty Ltd")

    assert party_id == "acme-books-pty-ltd"


def test_generate_party_id_appends_suffix_when_slug_collides(monkeypatch):
    existing_ids = {"acme-books", "acme-books-1"}
    monkeypatch.setattr(
        party_registration,
        "findPartyByPartyId",
        lambda party_id: {"party_id": party_id} if party_id in existing_ids else None,
    )

    party_id = party_registration.generate_party_id("Acme Books")

    assert party_id == "acme-books-2"


def test_hash_app_key_does_not_store_raw_key():
    raw_app_key = "appkey_super_secret"

    key_hash = party_registration.hash_app_key(raw_app_key)

    assert key_hash != raw_app_key
    assert re.fullmatch(r"[0-9a-f]{64}", key_hash)


def test_register_party_rejects_duplicate_contact_email(monkeypatch):
    req = build_request()
    monkeypatch.setattr(
        party_registration,
        "findPartyByEmail",
        lambda contact_email: {"contact_email": contact_email},
    )

    with pytest.raises(
        DuplicatePartyError, match="A party with this contact email already exists."
    ):
        party_registration.register_party(req)


def test_register_party_persists_hashed_key_and_returns_raw_key(monkeypatch):
    req = build_request()
    saved_party = {}

    monkeypatch.setattr(party_registration, "findPartyByEmail", lambda _email: None)
    monkeypatch.setattr(party_registration, "findPartyByPartyId", lambda _party_id: None)
    monkeypatch.setattr(party_registration, "findAppKeyByHash", lambda _key_hash: None)
    monkeypatch.setattr(party_registration, "generate_app_key", lambda: "appkey_test_value")

    def fake_save_party(party_id, party_name, contact_email, key_hash):
        saved_party.update(
            {
                "party_id": party_id,
                "party_name": party_name,
                "contact_email": contact_email,
                "key_hash": key_hash,
            }
        )
        return saved_party

    monkeypatch.setattr(party_registration, "saveParty", fake_save_party)

    result = party_registration.register_party(req)

    assert result.partyId == "acme-books"
    assert result.partyName == "Acme Books"
    assert result.appKey == "appkey_test_value"
    assert saved_party == {
        "party_id": "acme-books",
        "party_name": "Acme Books",
        "contact_email": "team@acmebooks.com",
        "key_hash": party_registration.hash_app_key("appkey_test_value"),
    }


def test_register_party_wraps_persistence_failures(monkeypatch):
    req = build_request()

    monkeypatch.setattr(party_registration, "findPartyByEmail", lambda _email: None)
    monkeypatch.setattr(party_registration, "findPartyByPartyId", lambda _party_id: None)
    monkeypatch.setattr(
        party_registration, "generate_app_key", lambda: "appkey_test_value"
    )  # Mock this too
    monkeypatch.setattr(
        party_registration, "saveParty", lambda *_args: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    with pytest.raises(PartyRegistrationPersistenceError, match="Unable to register party."):
        party_registration.register_party(req)


def test_register_party_rolls_back_when_persistence_fails(monkeypatch):
    req = build_request()
    deleted_emails: list[str] = []

    monkeypatch.setattr(party_registration, "findPartyByEmail", lambda _email: None)
    monkeypatch.setattr(party_registration, "findPartyByPartyId", lambda _party_id: None)
    monkeypatch.setattr(party_registration, "findAppKeyByHash", lambda _key_hash: None)

    def fake_save_party_fail(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(party_registration, "saveParty", fake_save_party_fail)
    monkeypatch.setattr(
        party_registration, "deleteParty", lambda email: deleted_emails.append(email)
    )

    with pytest.raises(PartyRegistrationPersistenceError, match="Unable to register party."):
        party_registration.register_party(req)

    assert deleted_emails == ["team@acmebooks.com"]
