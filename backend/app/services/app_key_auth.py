from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.other import findAppKeyByHash, findPartyByEmail
from app.services.party_registration import hash_app_key

http_bearer = HTTPBearer(
    auto_error=False,
    description="Register once to receive an app key, then send it as 'Authorization: Bearer <appKey>'.",
)

def get_current_party_email(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)] = None,
) -> str:
    raw_app_key = extract_bearer_token(credentials)
    return resolve_party_from_app_key(raw_app_key)[0]

def get_current_party_info(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)] = None,
) -> list:
    raw_app_key = extract_bearer_token(credentials)
    return resolve_party_from_app_key(raw_app_key)

def resolve_party_from_app_key(raw_app_key: str) -> list:
    key_record = findAppKeyByHash(hash_app_key(raw_app_key))

    if not key_record:
        raise HTTPException(status_code=401, detail="Unauthorized")
                             
    contact_email = key_record.get("contact_email")                           
    if not contact_email or not contact_email.strip():
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    party_name = key_record.get("party_name")
    if not party_name or not party_name.strip():
        raise HTTPException(status_code=401, detail="Unauthorized")

    return contact_email.strip().lower(), party_name.strip().lower()


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
