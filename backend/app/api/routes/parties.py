from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    PARTY_REGISTRATION_RESPONSE_EXAMPLE,
    PartyRegistrationRequest,
    PartyRegistrationResponse,
)
from app.services.party_registration import (
    DuplicatePartyError,
    PartyRegistrationPersistenceError,
    register_party,
)

router = APIRouter(prefix="/v1/parties", tags=["Parties"])
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
