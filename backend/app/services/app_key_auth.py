from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException

from app.other import findAppKeyByHash
from app.services.party_registration import hash_app_key


def get_current_party_id(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    raw_app_key = extract_bearer_token(authorization)
    key_record = findAppKeyByHash(hash_app_key(raw_app_key))

    if not key_record:
        raise HTTPException(status_code=401, detail="Unauthorized")

    party_id = key_record.get("party_id")
    if not isinstance(party_id, str) or not party_id.strip():
        raise HTTPException(status_code=401, detail="Unauthorized")

    return party_id


def extract_bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Unauthorized")

    return token.strip()
