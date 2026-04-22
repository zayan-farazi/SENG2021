from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.other import deleteXml, getXml, saveXml
from app.services import order_store
from app.services.app_key_auth import get_current_party_email
from app.services.despatch_service import create_despatch_from_order_xml

router = APIRouter(tags=["Despatch"])
logger = logging.getLogger(__name__)

PROTECTED_ORDER_AUTH_DESCRIPTION = (
    "Authenticate with either a legacy `v1` app key as `Authorization: Bearer <appKey>`, "
    "or the `v2` password flow as `Authorization: Bearer <password>` together with "
    "`X-Party-Email: <registered contact email>`."
)

UNAUTHORIZED_RESPONSE = {
    "description": (
        "Missing, malformed, or unknown bearer credential, or missing `X-Party-Email` for the "
        "`v2` password flow."
    ),
    "content": {"application/json": {"example": {"detail": "Unauthorized"}}},
}

FORBIDDEN_RESPONSE = {
    "description": (
        "The authenticated party's registered email does not match the order's "
        "`buyerEmail` or `sellerEmail`."
    ),
    "content": {
        "application/json": {
            "example": {
                "detail": (
                    "Forbidden: your registered email does not match this order's buyerEmail "
                    "or sellerEmail."
                )
            }
        }
    },
}

NOT_FOUND_RESPONSE = {
    "description": "The requested order was not found.",
    "content": {"application/json": {"example": {"detail": "Not Found"}}},
}


def _assert_order_access(current_party_email: str, payload: dict) -> None:
    buyer_email = payload.get("buyerEmail")
    seller_email = payload.get("sellerEmail")
    if not isinstance(buyer_email, str) or not isinstance(seller_email, str):
        raise HTTPException(status_code=500, detail="Order participant email information missing.")
    normalized_current = current_party_email.strip().lower()
    if normalized_current not in {buyer_email.strip().lower(), seller_email.strip().lower()}:
        raise HTTPException(
            status_code=403,
            detail=(
                "Forbidden: your registered email does not match this order's buyerEmail "
                "or sellerEmail."
            ),
        )


def _assert_seller_only(current_party_email: str, payload: dict, action: str) -> str:
    seller_email = payload.get("sellerEmail")
    if not isinstance(seller_email, str):
        raise HTTPException(status_code=500, detail="Order participant email missing.")
    if current_party_email.strip().lower() != seller_email.strip().lower():
        raise HTTPException(status_code=403, detail=f"Only the seller may {action}.")
    return seller_email


def _get_db_order_id(existing: dict) -> str:
    db_order_id = existing.get("dbOrderId")
    if not db_order_id:
        raise HTTPException(status_code=500, detail="Order missing database ID.")
    return db_order_id


@router.post(
    "/v1/order/{order_id}/despatch",
    status_code=200,
    summary="Generate despatch advice (authenticated)",
    description=(
        "Generate a despatch advice document for an order via the DevEx API and persist it. "
        f"{PROTECTED_ORDER_AUTH_DESCRIPTION} Only the seller may despatch an order. "
        "If a despatch already exists, the stored version is returned. "
        "This operation does NOT change the order status."
    ),
    responses={
        200: {
            "description": "Despatch advice generated or retrieved successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "orderId": "ORD-2026-001",
                        "updatedAt": "2026-04-20T12:00:00Z",
                        "despatch": {
                            "adviceId": None,
                            "xml": "<DespatchAdvice>...</DespatchAdvice>",
                        },
                    }
                }
            },
        },
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        500: {
            "description": "Despatch generation or persistence failed.",
            "content": {
                "application/json": {"example": {"detail": "Unable to generate despatch advice."}}
            },
        },
    },
)
async def despatch_order(
    order_id: str,
    current_party_email: str = Depends(get_current_party_email),
):
    existing = order_store.get_order_record(order_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Not Found")

    payload = existing.get("payload", {})
    _assert_order_access(current_party_email, payload)
    _assert_seller_only(current_party_email, payload, "despatch an order")

    db_order_id = _get_db_order_id(existing)

    try:
        existing_xml = getXml("dispatched_xml", db_order_id)
    except Exception as exc:
        logger.exception("Failed to fetch despatch XML")
        raise HTTPException(status_code=500, detail="Unable to fetch despatch XML.") from exc

    if existing_xml:
        return {
            "orderId": existing["orderId"],
            "updatedAt": existing["updatedAt"],
            "despatch": {"adviceId": None, "xml": existing_xml[0].get("xml")},
        }

    ubl_xml = existing.get("ublXml")
    if not ubl_xml:
        raise HTTPException(status_code=500, detail="Order XML missing.")

    try:
        despatch = await create_despatch_from_order_xml(ubl_xml)
    except Exception as exc:
        logger.exception("Despatch generation failed")
        raise HTTPException(status_code=500, detail="Unable to generate despatch advice.") from exc

    try:
        saveXml(
            "dispatched_xml",
            db_order_id,
            payload.get("buyerEmail"),
            payload.get("sellerEmail"),
            despatch["xml"],
        )
    except Exception as exc:
        logger.exception("Failed to persist despatch XML")
        raise HTTPException(status_code=500, detail="Unable to persist despatch advice.") from exc

    return {
        "orderId": existing["orderId"],
        "updatedAt": existing["updatedAt"],
        "despatch": despatch,
    }


@router.get(
    "/v1/order/{order_id}/despatch",
    status_code=200,
    summary="Get despatch XML (authenticated)",
    description=(
        "Fetch the stored despatch advice XML for an order. "
        f"{PROTECTED_ORDER_AUTH_DESCRIPTION} Only the buyer or seller may access it. "
        "Returns 404 if no despatch exists."
    ),
    responses={
        200: {
            "description": "Despatch XML retrieved successfully.",
            "content": {"application/xml": {"example": "<DespatchAdvice>...</DespatchAdvice>"}},
        },
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        500: {
            "description": "Despatch retrieval failed.",
            "content": {
                "application/json": {"example": {"detail": "Unable to fetch despatch XML."}}
            },
        },
    },
)
def get_despatch_xml(
    order_id: str,
    current_party_email: str = Depends(get_current_party_email),
):
    order = order_store.get_order_record(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Not Found")

    payload = order.get("payload", {})
    _assert_order_access(current_party_email, payload)

    db_order_id = _get_db_order_id(order)

    try:
        result = getXml("dispatched_xml", db_order_id)
    except Exception as exc:
        logger.exception("Failed to fetch despatch XML")
        raise HTTPException(status_code=500, detail="Unable to fetch despatch XML.") from exc

    if not result:
        raise HTTPException(status_code=404, detail="Not Found")

    xml = result[0].get("xml")
    if not xml:
        logger.error("Missing despatch XML for order_id=%s", order_id)
        raise HTTPException(status_code=500, detail="Despatch XML missing or corrupted.")

    return Response(content=xml, media_type="application/xml")


@router.delete(
    "/v1/order/{order_id}/despatch",
    status_code=200,
    summary="Delete despatch advice (authenticated)",
    description=(
        "Delete the stored despatch advice document for an order. "
        f"{PROTECTED_ORDER_AUTH_DESCRIPTION} Only the seller may delete a despatch. "
        "Returns 404 if no despatch exists. "
        "This operation does NOT change the order status."
    ),
    responses={
        200: {
            "description": "Despatch advice deleted successfully.",
            "content": {
                "application/json": {
                    "example": {"orderId": "ORD-2026-001", "detail": "Despatch advice deleted."}
                }
            },
        },
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        500: {
            "description": "Despatch deletion failed.",
            "content": {
                "application/json": {"example": {"detail": "Unable to delete despatch advice."}}
            },
        },
    },
)
def delete_despatch_order(
    order_id: str,
    current_party_email: str = Depends(get_current_party_email),
):
    existing = order_store.get_order_record(order_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Not Found")

    payload = existing.get("payload", {})
    _assert_order_access(current_party_email, payload)
    _assert_seller_only(current_party_email, payload, "delete a despatch")

    db_order_id = _get_db_order_id(existing)

    try:
        existing_xml = getXml("dispatched_xml", db_order_id)
    except Exception as exc:
        logger.exception("Failed to fetch despatch XML for deletion check")
        raise HTTPException(status_code=500, detail="Unable to fetch despatch XML.") from exc

    if not existing_xml:
        raise HTTPException(status_code=404, detail="No despatch exists for this order.")

    try:
        deleteXml("dispatched_xml", db_order_id)
    except Exception as exc:
        logger.exception("Failed to delete despatch XML")
        raise HTTPException(status_code=500, detail="Unable to delete despatch advice.") from exc

    return {"orderId": existing["orderId"], "detail": "Despatch advice deleted."}
