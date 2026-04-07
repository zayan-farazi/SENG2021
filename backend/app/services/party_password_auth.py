from __future__ import annotations

import bcrypt
from fastapi import HTTPException

from app.models.schemas import (
    PartyAuthV2Response,
    PartyLoginV2Request,
    PartyRegistrationV2Request,
)
from app.other import deleteParty, findPartyByContactEmail, saveParty
from app.services.party_registration import normalize_contact_email


class DuplicatePartyV2Error(RuntimeError):
    """Raised when a v2 registration email already exists."""


class PartyAuthV2PersistenceError(RuntimeError):
    """Raised when a v2 registration cannot be persisted."""


def hash_password(raw_password: str) -> str:
    return bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw_password: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(raw_password.encode("utf-8"), stored_hash.encode("utf-8"))
    except ValueError:
        return False


def register_party_v2(req: PartyRegistrationV2Request) -> PartyAuthV2Response:
    normalized_email = normalize_contact_email(req.contactEmail)
    if findPartyByContactEmail(normalized_email):
        raise DuplicatePartyV2Error("A party with this contact email already exists.")

    party_id = normalized_email
    password_hash = hash_password(req.password)

    try:
        saveParty(req.partyName.strip(), normalized_email, password_hash)
    except Exception as exc:  # noqa: BLE001
        try:
            deleteParty(party_id)
        except Exception:  # noqa: BLE001
            pass
        raise PartyAuthV2PersistenceError("Unable to register party.") from exc

    return PartyAuthV2Response(
        partyId=party_id,
        partyName=req.partyName.strip(),
        contactEmail=normalized_email,
    )


def login_party_v2(req: PartyLoginV2Request) -> PartyAuthV2Response:
    return authenticate_party_v2(req.contactEmail, req.password)


def authenticate_party_v2(contact_email: str, password: str) -> PartyAuthV2Response:
    normalized_email = normalize_contact_email(contact_email)
    party = findPartyByContactEmail(normalized_email)

    if not party:
        raise HTTPException(status_code=401, detail="Unauthorized")

    stored_hash = party.get("key_hash")
    if not isinstance(stored_hash, str) or not stored_hash.strip():
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not verify_password(password, stored_hash):
        raise HTTPException(status_code=401, detail="Unauthorized")

    party_name = party.get("party_name")
    if not isinstance(party_name, str) or not party_name.strip():
        raise HTTPException(status_code=401, detail="Unauthorized")

    return PartyAuthV2Response(
        partyId=normalized_email,
        partyName=party_name.strip(),
        contactEmail=normalized_email,
    )
