from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.other import findAppKeyByHash, findPartyByPartyId
from app.services.party_registration import hash_app_key
from app.services.party_password_auth import authenticate_party_v2

http_bearer = HTTPBearer(
    auto_error=False,
    description="Register once to receive an app key, then send it as 'Authorization: Bearer <appKey>'.",
)


def get_current_party_email(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)] = None,
    party_email: Annotated[
        str | None, Header(alias="X-Party-Email", include_in_schema=False)
    ] = None,
) -> str:
    raw_app_key = extract_bearer_token(credentials)
    return resolve_party_email_from_app_key(raw_app_key, party_email)


def resolve_party_email_from_app_key(raw_app_key: str, party_email: str | None = None) -> str:
    key_record = findAppKeyByHash(hash_app_key(raw_app_key))

    if not key_record:
        if isinstance(party_email, str) and party_email.strip():
            return authenticate_party_v2(party_email.strip(), raw_app_key).contactEmail
        raise HTTPException(status_code=401, detail="Unauthorized")

    contact_email = key_record.get("contact_email")
    if isinstance(contact_email, str) and contact_email.strip():
        return contact_email.strip().lower()

    party_id = key_record.get("party_id")
    if not isinstance(party_id, str) or not party_id.strip():
        raise HTTPException(status_code=401, detail="Unauthorized")

    party_record = findPartyByPartyId(party_id)
    if not party_record:
        raise HTTPException(status_code=401, detail="Unauthorized")

    contact_email = party_record.get("contact_email")
    if not isinstance(contact_email, str) or not contact_email.strip():
        raise HTTPException(status_code=401, detail="Unauthorized")

    return contact_email.strip().lower()


get_current_party_id = get_current_party_email


def extract_bearer_token(credentials: HTTPAuthorizationCredentials | str | None) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if isinstance(credentials, HTTPAuthorizationCredentials):
        scheme = credentials.scheme
        token = credentials.credentials
    else:
        scheme, _, token = credentials.partition(" ")

    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Unauthorized")

    return token.strip()
