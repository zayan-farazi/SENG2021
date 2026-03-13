from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.models.schemas import PartyRegistrationRequest, PartyRegistrationResponse
from app.services.party_registration import (
    DuplicatePartyError,
    PartyRegistrationPersistenceError,
    register_party,
)

router = APIRouter(prefix="/v1/parties", tags=["Parties"])
logger = logging.getLogger(__name__)


@router.post("/register", response_model=PartyRegistrationResponse, status_code=201)
def register(req: PartyRegistrationRequest):
    try:
        return register_party(req)
    except DuplicatePartyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PartyRegistrationPersistenceError as exc:
        logger.exception("Party registration failed")
        raise HTTPException(status_code=500, detail="Unable to register party.") from exc
