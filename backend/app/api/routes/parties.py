from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import (
    PARTY_REGISTRATION_RESPONSE_EXAMPLE,
    PartyAuthV2Response,
    PartyLoginV2Request,
    PartyRegistrationRequest,
    PartyRegistrationResponse,
    PartyRegistrationV2Request,
    PartyUserFetchResponse,
)
from app.other import findPartyByContactEmail
from app.services.app_key_auth import get_current_party_email
from app.services.party_password_auth import (
    DuplicatePartyV2Error,
    PartyAuthV2PersistenceError,
    login_party_v2,
    register_party_v2,
)
from app.services.party_registration import (
    DuplicatePartyError,
    PartyRegistrationPersistenceError,
    register_party,
)

router = APIRouter(prefix="/v1/parties", tags=["Parties"])
router_v2 = APIRouter(prefix="/v2/parties", tags=["Parties"])
logger = logging.getLogger(__name__)


@router.post(
    "/register",
    response_model=PartyRegistrationResponse,
    status_code=201,
    summary="Register a party and issue an app key",
    description=(
        "Register a buyer or seller organization once to receive an app key. "
        "The returned `appKey` is only shown in this response and must be stored securely by the caller."
    ),
    responses={
        201: {
            "description": "Party registered successfully.",
            "content": {"application/json": {"example": PARTY_REGISTRATION_RESPONSE_EXAMPLE}},
        },
        409: {
            "description": "The contact email is already registered.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": (
                            "A party with contact email orders@acmebooks.example already exists."
                        )
                    }
                }
            },
        },
        500: {
            "description": "Party registration could not be persisted.",
            "content": {"application/json": {"example": {"detail": "Unable to register party."}}},
        },
    },
)
def register(req: PartyRegistrationRequest):
    try:
        return register_party(req)
    except DuplicatePartyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PartyRegistrationPersistenceError as exc:
        logger.exception("Party registration failed")
        raise HTTPException(status_code=500, detail="Unable to register party.") from exc


@router.get(
    "/userFetch",
    response_model=PartyUserFetchResponse,
    summary="Fetch the current party from an app key",
    description="Resolve the current party identity from the supplied bearer app key.",
    responses={
        200: {
            "description": "Party resolved successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "partyId": "orders@acmebooks.example",
                        "partyName": "Acme Books",
                        "contactEmail": "orders@acmebooks.example",
                    }
                }
            },
        },
        401: {
            "description": "The supplied app key is invalid.",
            "content": {"application/json": {"example": {"detail": "Unauthorized"}}},
        },
    },
)
def user_fetch(
    current_party_email: Annotated[str, Depends(get_current_party_email)],
) -> PartyUserFetchResponse:
    party = findPartyByContactEmail(current_party_email)
    if not party:
        raise HTTPException(status_code=401, detail="Unauthorized")

    party_name = party.get("party_name")
    if not isinstance(party_name, str) or not party_name.strip():
        raise HTTPException(status_code=401, detail="Unauthorized")

    contact_email = party.get("contact_email")
    if not isinstance(contact_email, str) or not contact_email.strip():
        raise HTTPException(status_code=401, detail="Unauthorized")

    normalized_email = contact_email.strip().lower()
    return PartyUserFetchResponse(
        partyId=normalized_email,
        partyName=party_name.strip(),
        contactEmail=normalized_email,
    )


@router_v2.post(
    "/register",
    response_model=PartyAuthV2Response,
    status_code=201,
    summary="Register a party with email and password",
    description=(
        "Register a buyer or seller organization using a contact email and password. "
        "This v2 flow does not issue a generated app key."
    ),
    responses={
        201: {
            "description": "Party registered successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "partyId": "orders@acmebooks.example",
                        "partyName": "Acme Books",
                        "contactEmail": "orders@acmebooks.example",
                    }
                }
            },
        },
        409: {
            "description": "The contact email is already registered.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": (
                            "A party with contact email orders@acmebooks.example already exists."
                        )
                    }
                }
            },
        },
        500: {
            "description": "Party registration could not be persisted.",
            "content": {"application/json": {"example": {"detail": "Unable to register party."}}},
        },
    },
)
def register_v2(req: PartyRegistrationV2Request):
    try:
        return register_party_v2(req)
    except DuplicatePartyV2Error as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PartyAuthV2PersistenceError as exc:
        logger.exception("Party registration v2 failed")
        raise HTTPException(status_code=500, detail="Unable to register party.") from exc


@router_v2.post(
    "/login",
    response_model=PartyAuthV2Response,
    summary="Log in with contact email and password",
    description="Resolve the current party identity from a v2 contact email and password pair.",
    responses={
        200: {
            "description": "Party resolved successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "partyId": "orders@acmebooks.example",
                        "partyName": "Acme Books",
                        "contactEmail": "orders@acmebooks.example",
                    }
                }
            },
        },
        401: {
            "description": "The supplied contact email or password is invalid.",
            "content": {"application/json": {"example": {"detail": "Unauthorized"}}},
        },
    },
)
def login_v2(req: PartyLoginV2Request):
    return login_party_v2(req)
