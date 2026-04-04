from __future__ import annotations

import hashlib
import re
import secrets

from app.models.schemas import PartyRegistrationRequest, PartyRegistrationResponse
from app.other import (
    deleteParty,
    findAppKeyByHash,
    findPartyByContactEmail,
    findPartyByPartyId,
    saveAppKey,
    saveParty,
)


class DuplicatePartyError(RuntimeError):
    """Raised when a party is already registered."""


class PartyRegistrationPersistenceError(RuntimeError):
    """Raised when registration persistence fails."""


def register_party(req: PartyRegistrationRequest) -> PartyRegistrationResponse:
    normalized_email = normalize_contact_email(req.contactEmail)
    if findPartyByContactEmail(normalized_email):
        raise DuplicatePartyError("A party with this contact email already exists.")

    party_id = normalized_email
    raw_app_key = generate_app_key()
    key_hash = hash_app_key(raw_app_key)

    try:
        saveParty(party_id, req.partyName.strip(), normalized_email)
        saveAppKey(party_id, key_hash)
    except Exception as exc:  # noqa: BLE001
        try:
            deleteParty(party_id)
        except Exception:  # noqa: BLE001
            pass
        raise PartyRegistrationPersistenceError("Unable to register party.") from exc

    return PartyRegistrationResponse(
        partyId=party_id,
        partyName=req.partyName.strip(),
        appKey=raw_app_key,
        message="Store this key securely. It will not be shown again.",
    )


def normalize_contact_email(contact_email: str) -> str:
    return contact_email.strip().lower()


def generate_party_id(party_name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", party_name.strip().lower()).strip("-") or "party"
    candidate = base
    suffix = 1
    while findPartyByPartyId(candidate):
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def generate_app_key() -> str:
    candidate = f"appkey_{secrets.token_urlsafe(32)}"
    while findAppKeyByHash(hash_app_key(candidate)):
        candidate = f"appkey_{secrets.token_urlsafe(32)}"
    return candidate


def hash_app_key(raw_app_key: str) -> str:
    return hashlib.sha256(raw_app_key.encode("utf-8")).hexdigest()
