from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.other import findAppKeyByHash, findPartyByPartyId
from app.services.party_password_auth import authenticate_party_v2
from app.services.party_registration import hash_app_key

PARTY_EMAIL_HEADER_DESCRIPTION = (
    "Registered contact email for the `v2` password flow. "
    "Required when sending `Authorization: Bearer <password>`, and ignored for legacy `v1` app keys."
)

http_bearer = HTTPBearer(
    auto_error=False,
    description=(
        "Send either a legacy `v1` app key as `Authorization: Bearer <appKey>` or a `v2` "
        "password as `Authorization: Bearer <password>`. When using the `v2` password flow, "
        "also send `X-Party-Email: <registered contact email>`."
    ),
)


def get_current_party_email(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)] = None,
    party_email: Annotated[
        str | None,
        Header(alias="X-Party-Email", description=PARTY_EMAIL_HEADER_DESCRIPTION),
    ] = None,
) -> str:
    raw_app_key = extract_bearer_token(credentials)
    return resolve_party_from_app_key(raw_app_key, party_email)[0]


def get_current_party_info(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)] = None,
    party_email: Annotated[
        str | None,
        Header(alias="X-Party-Email", description=PARTY_EMAIL_HEADER_DESCRIPTION),
    ] = None,
) -> tuple[str, str]:
    raw_app_key = extract_bearer_token(credentials)
    return resolve_party_from_app_key(raw_app_key, party_email)


def resolve_party_from_app_key(
    raw_app_key: str,
    party_email: str | None = None,
) -> tuple[str, str]:
    key_record = findAppKeyByHash(hash_app_key(raw_app_key))

    if not key_record:
        if isinstance(party_email, str) and party_email.strip():
            result = authenticate_party_v2(party_email.strip(), raw_app_key)
            return result.contactEmail, result.partyName
        raise HTTPException(status_code=401, detail="Unauthorized")

    contact_email = key_record.get("contact_email")
    if isinstance(contact_email, str) and contact_email.strip():
        party_name = key_record.get("party_name")
        if not isinstance(party_name, str) or not party_name.strip():
            raise HTTPException(status_code=401, detail="Unauthorized")
        return contact_email.strip().lower(), party_name.strip()

    party_id = key_record.get("party_id")
    if not isinstance(party_id, str) or not party_id.strip():
        raise HTTPException(status_code=401, detail="Unauthorized")

    party_record = findPartyByPartyId(party_id)
    if not party_record:
        raise HTTPException(status_code=401, detail="Unauthorized")

    contact_email = party_record.get("contact_email")
    if not isinstance(contact_email, str) or not contact_email.strip():
        raise HTTPException(status_code=401, detail="Unauthorized")

    party_name = party_record.get("party_name")
    if not isinstance(party_name, str) or not party_name.strip():
        raise HTTPException(status_code=401, detail="Unauthorized")

    return contact_email.strip().lower(), party_name.strip()


def resolve_party_email_from_app_key(raw_app_key: str, party_email: str | None = None) -> str:
    return resolve_party_from_app_key(raw_app_key, party_email)[0]


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
