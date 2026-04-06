from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import Response
from pydantic import ValidationError

from app.models.schemas import (
    ORDER_CONVERSION_RESPONSE_INCOMPLETE_EXAMPLE,
    ORDER_CONVERSION_RESPONSE_SUCCESS_EXAMPLE,
    ORDER_CREATE_RESPONSE_EXAMPLE,
    ORDER_FETCH_RESPONSE_EXAMPLE,
    ORDER_LIST_FINAL_PAGE_RESPONSE_EXAMPLE,
    ORDER_LIST_RESPONSE_EXAMPLE,
    ORDER_PAYLOAD_FETCH_RESPONSE_EXAMPLE,
    ORDER_UPDATE_RESPONSE_EXAMPLE,
    AnalyticsResponse,
    OrderConversionResponse,
    OrderCreateResponse,
    OrderFetchResponse,
    OrderListResponse,
    OrderPayloadFetchResponse,
    OrderRequest,
    OrderUpdateResponse,
    TranscriptConversionRequest,
)
from app.services import groq_order_extractor, order_conversion, order_store
from app.services.analytics_service import get_user_analytics
from app.services.app_key_auth import get_current_party_email, resolve_party_email_from_app_key
from app.services.order_draft import (
    DraftSessionState,
    append_partial_transcript,
    apply_draft_patch,
    apply_transcript_interpretation,
    reset_state,
    serialize_state,
    validate_draft_for_commit,
)
from app.services.order_store import (
    OrderConflictLockedError,
    OrderNotFoundError,
    OrderPersistenceError,
)
from app.services.party_password_auth import authenticate_party_v2
from app.services.ubl_order import OrderGenerationError, generate_docs_example_ubl_order_xml

# from other import findOrders, saveOrder, saveOrderDetails, DBInfo

router = APIRouter(tags=["Orders"])
logger = logging.getLogger(__name__)
ORDERS = order_store.ORDERS
ANALYTICS_FROM_DATE_QUERY = Query(
    ...,
    description="Inclusive range start in ISO-8601 datetime form.",
)
ANALYTICS_TO_DATE_QUERY = Query(
    ...,
    description="Inclusive range end in ISO-8601 datetime form.",
)

UNAUTHORIZED_RESPONSE = {
    "description": "Missing, malformed, or unknown Bearer app key.",
    "content": {
        "application/json": {
            "example": {"detail": "Unauthorized"},
        }
    },
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
            },
        }
    },
}

NOT_FOUND_RESPONSE = {
    "description": "The requested order was not found.",
    "content": {
        "application/json": {
            "example": {"detail": "Not Found"},
        }
    },
}

VALIDATION_FAILURE_RESPONSE = {
    "description": "The order payload failed validation.",
    "content": {
        "application/json": {
            "example": {
                "detail": [
                    {"path": "buyerName", "issue": "buyerName is required"},
                ],
            }
        }
    },
}
ORDER_FETCH_XML_EXAMPLE = generate_docs_example_ubl_order_xml()


@router.post(
    "/v1/order/create",
    response_model=OrderCreateResponse,
    status_code=201,
    summary="Create an order (Bearer app key required)",
    description=(
        "Create a new order as either the buyer or the seller. "
        "Send `Authorization: Bearer <appKey>` and include the caller's registered email as "
        "either `buyerEmail` or `sellerEmail` in the request body."
    ),
    responses={
        201: {
            "description": "Order created successfully.",
            "content": {"application/json": {"example": ORDER_CREATE_RESPONSE_EXAMPLE}},
        },
        400: VALIDATION_FAILURE_RESPONSE,
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        500: {
            "description": "Order generation or persistence failed.",
            "content": {"application/json": {"example": {"detail": "Unable to create order."}}},
        },
    },
)
def create_order(req: OrderRequest, current_party_email: str = Depends(get_current_party_email)):
    _assert_email_access(current_party_email, req.buyerEmail, req.sellerEmail)

    issues = _validate_order(req)
    if issues:
        raise HTTPException(status_code=400, detail=issues)

    try:
        record = order_store.create_order_record(req)
    except OrderGenerationError as exc:
        logger.exception("Order creation failed")
        raise HTTPException(status_code=500, detail="Unable to create order.") from exc
    except OrderPersistenceError as exc:
        logger.exception("Order persistence verification failed")
        raise HTTPException(status_code=500, detail="Unable to persist order.") from exc

    return {
        "orderId": record["orderId"],
        "status": record["status"],
        "createdAt": record["createdAt"],
    }


@router.post(
    "/v1/orders/convert/transcript",
    response_model=OrderConversionResponse,
    summary="Convert transcript to order payload (Bearer app key required)",
    description=(
        "Interpret free-form transcript text and return an `OrderRequest`-shaped payload without "
        "creating an order. Use this to prepare payloads for create or update after authenticating "
        "with a Bearer app key. Transcripts work best when they mention the buyer and seller "
        "emails directly, or when those emails are already present in `currentPayload`."
    ),
    responses={
        200: {
            "description": "Transcript converted into a normalized order payload or partial draft.",
            "content": {
                "application/json": {
                    "examples": {
                        "success": {"value": ORDER_CONVERSION_RESPONSE_SUCCESS_EXAMPLE},
                        "incomplete": {"value": ORDER_CONVERSION_RESPONSE_INCOMPLETE_EXAMPLE},
                    }
                }
            },
        },
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
    },
)
async def convert_transcript_to_order_payload(
    request: TranscriptConversionRequest,
    current_party_email: str = Depends(get_current_party_email),
):
    conversion = await order_conversion.convert_transcript_to_draft(
        request.transcript,
        request.currentPayload,
    )
    return _build_conversion_response(
        source="transcript",
        draft=order_conversion.prefill_caller_email(conversion.draft, current_party_email),
        conversion_warnings=conversion.warnings,
        conversion_issues=conversion.issues,
        current_party_email=current_party_email,
    )


@router.get(
    "/v1/orders",
    response_model=OrderListResponse,
    summary="List orders (Bearer app key required)",
    description=(
        "List orders where the authenticated party is either the buyer or seller. "
        "Results are sorted newest-first by `updatedAt`, then `orderId`, and paginated with "
        "`limit` and `offset`."
    ),
    responses={
        200: {
            "description": "A paginated list of the caller's orders.",
            "content": {
                "application/json": {
                    "examples": {
                        "firstPage": {"value": ORDER_LIST_RESPONSE_EXAMPLE},
                        "finalPage": {"value": ORDER_LIST_FINAL_PAGE_RESPONSE_EXAMPLE},
                    }
                }
            },
        },
        401: UNAUTHORIZED_RESPONSE,
    },
)
def list_orders(
    limit: int = Query(
        default=order_store.DEFAULT_ORDER_LIST_LIMIT,
        ge=1,
        le=order_store.MAX_ORDER_LIST_LIMIT,
    ),
    offset: int = Query(default=order_store.DEFAULT_ORDER_LIST_OFFSET, ge=0),
    current_party_email: str = Depends(get_current_party_email),
):
    return order_store.list_orders_for_party(
        current_party_email,
        limit=limit,
        offset=offset,
    )


@router.delete(
    "/v1/order/{order_id}",
    status_code=204,
    summary="Delete an order (Bearer app key required)",
    description=(
        "Delete an existing order as either the buyer or the seller. "
        "The caller must authenticate with a Bearer app key whose registered email matches "
        "the stored `buyerEmail` or `sellerEmail`."
    ),
    responses={
        204: {"description": "Order deleted successfully."},
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        500: {
            "description": "The order could not be deleted from persistent storage.",
            "content": {"application/json": {"example": {"detail": "Unable to delete order."}}},
        },
    },
)
def delete_order(order_id: str, current_party_email: str = Depends(get_current_party_email)):
    existing = order_store.get_order_record(order_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Not Found")

    payload = existing.get("payload", {})
    _assert_order_access(current_party_email, payload)

    try:
        deleted = order_store.delete_order_record(order_id)
    except OrderPersistenceError as exc:
        logger.exception("Order delete failed")
        raise HTTPException(status_code=500, detail="Unable to delete order.") from exc

    if not deleted:
        raise HTTPException(status_code=404, detail="Not Found")


@router.websocket("/v1/order/draft/ws")
async def order_draft_session(websocket: WebSocket):
    await websocket.accept()
    state = DraftSessionState()
    await websocket.send_json({"type": "session.ready", "payload": serialize_state(state)})

    try:
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                await _send_error(
                    websocket, "invalid_message", "WebSocket messages must be JSON objects."
                )
                continue

            event_type = message.get("type")
            payload = message.get("payload") or {}

            if not isinstance(payload, dict):
                await _send_error(
                    websocket, "invalid_payload", "Event payloads must be JSON objects."
                )
                continue

            if event_type == "session.start":
                await _handle_session_start(websocket, state, payload)
            elif event_type == "transcript.partial":
                await _handle_partial_transcript(websocket, state, payload)
            elif event_type == "transcript.final":
                await _handle_final_transcript(websocket, state, payload)
            elif event_type == "draft.patch":
                await _handle_draft_patch(websocket, state, payload)
            elif event_type == "session.commit":
                await _handle_commit(websocket, state, payload)
            elif event_type == "session.reset":
                reset_state(state)
                await _send_draft_update(websocket, state, ["Draft reset."])
            else:
                await _send_error(
                    websocket, "unknown_event", f"Unsupported event type: {event_type}"
                )
    except WebSocketDisconnect:
        logger.info("Draft session disconnected")


async def _handle_session_start(
    websocket: WebSocket,
    state: DraftSessionState,
    payload: dict[str, Any],
):
    draft_payload = payload.get("draft")
    if draft_payload is None:
        await _send_draft_update(websocket, state, ["Draft session started."])
        return

    if not isinstance(draft_payload, dict):
        await _send_error(websocket, "invalid_draft", "Draft payload must be a JSON object.")
        return

    try:
        applied_changes = apply_draft_patch(state, draft_payload)
    except ValidationError as exc:
        await _send_error(
            websocket, "invalid_draft", "Draft payload failed validation.", exc.errors()
        )
        return

    await _send_draft_update(websocket, state, applied_changes)


async def _handle_partial_transcript(
    websocket: WebSocket,
    state: DraftSessionState,
    payload: dict[str, Any],
):
    text = payload.get("text")
    if not isinstance(text, str):
        await _send_error(
            websocket, "invalid_transcript", "Partial transcript text must be a string."
        )
        return

    append_partial_transcript(state, text)
    await websocket.send_json(
        {
            "type": "transcript.echo",
            "payload": {"kind": "partial", "text": state.current_partial},
        }
    )


async def _handle_final_transcript(
    websocket: WebSocket,
    state: DraftSessionState,
    payload: dict[str, Any],
):
    text = payload.get("text")
    if not isinstance(text, str):
        await _send_error(
            websocket, "invalid_transcript", "Final transcript text must be a string."
        )
        return

    cleaned = text.strip()
    await websocket.send_json(
        {"type": "transcript.echo", "payload": {"kind": "final", "text": cleaned}}
    )
    interpretation = await groq_order_extractor.extract_transcript_patch(
        state.draft,
        state.transcript_log,
        cleaned,
    )
    result = apply_transcript_interpretation(state, cleaned, interpretation)
    await _send_draft_update(websocket, state, result.applied_changes)


async def _handle_draft_patch(
    websocket: WebSocket,
    state: DraftSessionState,
    payload: dict[str, Any],
):
    draft_payload = payload.get("draft")
    if not isinstance(draft_payload, dict):
        await _send_error(websocket, "invalid_draft", "Draft payload must be a JSON object.")
        return

    try:
        applied_changes = apply_draft_patch(state, draft_payload)
    except ValidationError as exc:
        await _send_error(
            websocket, "invalid_draft", "Draft payload failed validation.", exc.errors()
        )
        return

    await _send_draft_update(websocket, state, applied_changes)


async def _handle_commit(
    websocket: WebSocket,
    state: DraftSessionState,
    payload: dict[str, Any],
):
    req, errors = validate_draft_for_commit(state.draft)
    if req is None:
        await websocket.send_json(
            {
                "type": "commit.blocked",
                "payload": {"errors": errors, "state": serialize_state(state)},
            }
        )
        return

    raw_app_key = payload.get("appKey")
    credential = payload.get("credential")
    contact_email = payload.get("contactEmail")

    if not (
        (isinstance(raw_app_key, str) and raw_app_key.strip())
        or (
            isinstance(credential, str)
            and credential.strip()
            and isinstance(contact_email, str)
            and contact_email.strip()
        )
    ):
        await _send_error(
            websocket,
            "unauthorized",
            "session.commit requires valid credentials.",
        )
        return

    try:
        if isinstance(raw_app_key, str) and raw_app_key.strip():
            current_party_email = resolve_party_email_from_app_key(raw_app_key.strip())
        else:
            current_party_email = authenticate_party_v2(
                contact_email.strip(),
                credential.strip(),
            ).contactEmail
        _assert_email_access(current_party_email, req.buyerEmail, req.sellerEmail)
    except HTTPException as exc:
        await _send_error(websocket, "unauthorized", exc.detail)
        return

    try:
        record = order_store.create_order_record(req)
    except OrderGenerationError:
        logger.exception("WebSocket order creation failed")
        await _send_error(websocket, "order_creation_failed", "Unable to create order.")
        return
    except OrderPersistenceError:
        logger.exception("WebSocket order persistence failed")
        await _send_error(websocket, "order_persistence_failed", "Unable to persist order.")
        return

    await websocket.send_json(
        {
            "type": "order.created",
            "payload": {
                "order": order_store.build_order_response(record),
                "state": serialize_state(state),
            },
        }
    )


async def _send_draft_update(
    websocket: WebSocket,
    state: DraftSessionState,
    applied_changes: list[str],
):
    await websocket.send_json(
        {
            "type": "draft.updated",
            "payload": {"state": serialize_state(state), "appliedChanges": applied_changes},
        }
    )


async def _send_error(
    websocket: WebSocket,
    code: str,
    message: str,
    details: Any | None = None,
):
    payload = {"code": code, "message": message}
    if details is not None:
        payload["details"] = details
    await websocket.send_json({"type": "error", "payload": payload})


@router.get(
    "/v1/order/{order_id}",
    response_model=OrderFetchResponse,
    summary="Get an order (Bearer app key required)",
    description=(
        "Fetch the latest persisted order by its public `orderId`. "
        "Only the buyer or seller on the order may access it."
    ),
    responses={
        200: {
            "description": "Order fetched successfully.",
            "content": {"application/json": {"example": ORDER_FETCH_RESPONSE_EXAMPLE}},
        },
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)
def get_order(order_id: str, current_party_email: str = Depends(get_current_party_email)):
    order = order_store.get_order_record(order_id)

    if order is None:
        raise HTTPException(status_code=404, detail="Not Found")

    payload = order.get("payload", {})
    _assert_order_access(current_party_email, payload)

    return {
        "orderId": order["orderId"],
        "status": order["status"],
        "createdAt": order["createdAt"],
        "updatedAt": order["updatedAt"],
    }


@router.get(
    "/v1/order/{order_id}/payload",
    response_model=OrderPayloadFetchResponse,
    summary="Get order payload (Bearer app key required)",
    description=(
        "Fetch the latest persisted editable payload for an order by its public `orderId`. "
        "Only the buyer or seller on the order may access it."
    ),
    responses={
        200: {
            "description": "Order payload fetched successfully.",
            "content": {"application/json": {"example": ORDER_PAYLOAD_FETCH_RESPONSE_EXAMPLE}},
        },
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)
def get_order_payload(order_id: str, current_party_email: str = Depends(get_current_party_email)):
    order = order_store.get_order_record(order_id)

    if order is None:
        raise HTTPException(status_code=404, detail="Not Found")

    payload = order.get("payload", {})
    _assert_order_access(current_party_email, payload)

    return {
        "orderId": order["orderId"],
        "status": order["status"],
        "createdAt": order["createdAt"],
        "updatedAt": order["updatedAt"],
        "payload": payload,
    }


@router.get(
    "/v1/order/{order_id}/ubl",
    operation_id="get_order_ubl_xml",
    response_class=Response,
    summary="Get order UBL XML (Bearer app key required)",
    description=(
        "Fetch the raw persisted UBL XML for an order by its public `orderId`. "
        "Only the buyer or seller on the order may access it."
    ),
    responses={
        200: {
            "description": "Order XML fetched successfully.",
            "content": {"application/xml": {"example": ORDER_FETCH_XML_EXAMPLE}},
        },
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        500: {
            "description": "The stored order XML is missing.",
            "content": {"application/json": {"example": {"detail": "Order XML missing."}}},
        },
    },
)
def get_order_ubl(order_id: str, current_party_email: str = Depends(get_current_party_email)):
    order = order_store.get_order_record(order_id)

    if order is None:
        raise HTTPException(status_code=404, detail="Not Found")

    payload = order.get("payload", {})
    _assert_order_access(current_party_email, payload)

    if not order.get("ublXml"):
        raise HTTPException(status_code=500, detail="Order XML missing.")

    return Response(content=order["ublXml"], media_type="application/xml")


@router.put(
    "/v1/order/{order_id}",
    response_model=OrderUpdateResponse,
    summary="Update an order (Bearer app key required)",
    description=(
        "Update an existing order as either the buyer or the seller. "
        "`buyerEmail` and `sellerEmail` are immutable after create; changing parties requires a new order."
    ),
    responses={
        200: {
            "description": "Order updated successfully.",
            "content": {"application/json": {"example": ORDER_UPDATE_RESPONSE_EXAMPLE}},
        },
        400: VALIDATION_FAILURE_RESPONSE,
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        409: {
            "description": "The order is locked or the participant emails were changed.",
            "content": {
                "application/json": {
                    "examples": {
                        "immutableParticipants": {
                            "value": {"detail": "Order participant emails cannot be changed."}
                        },
                        "locked": {
                            "value": {"detail": "Order cannot be updated in status 'SUBMITTED'."}
                        },
                    }
                }
            },
        },
        500: {
            "description": "The order could not be regenerated or persisted.",
            "content": {
                "application/json": {
                    "examples": {
                        "updateFailed": {"value": {"detail": "Unable to update order."}},
                        "persistFailed": {"value": {"detail": "Unable to persist updated order."}},
                    }
                }
            },
        },
    },
)
def update_order(
    order_id: str, req: OrderRequest, current_party_email: str = Depends(get_current_party_email)
):
    existing = order_store.get_order_record(order_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Not Found")

    payload = existing.get("payload", {})
    _assert_order_access(current_party_email, payload)
    if req.buyerEmail != payload.get("buyerEmail") or req.sellerEmail != payload.get("sellerEmail"):
        raise HTTPException(status_code=409, detail="Order participant emails cannot be changed.")

    issues = _validate_order(req)
    if issues:
        raise HTTPException(status_code=400, detail=issues)

    try:
        record = order_store.update_order_record(order_id, req)

    except OrderNotFoundError as exc:
        # Order could not be found with order_id
        raise HTTPException(status_code=404, detail="Not Found") from exc

    except OrderConflictLockedError as exc:
        # Order is not in an editable status
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    except OrderGenerationError as exc:
        logger.exception("Order update failed")
        raise HTTPException(status_code=500, detail="Unable to update order.") from exc

    except OrderPersistenceError as exc:
        logger.exception("Order update persistence verification failed")
        raise HTTPException(status_code=500, detail="Unable to persist updated order.") from exc

    return {
        "orderId": record["orderId"],
        "status": record["status"],
        "updatedAt": record["updatedAt"],
    }


def _build_conversion_response(
    *,
    source: str,
    draft: Any,
    conversion_warnings: list[str],
    conversion_issues: list[Any],
    current_party_email: str,
) -> OrderConversionResponse:
    issues = [_format_conversion_issue(issue.path, issue.issue) for issue in conversion_issues]
    issues.extend(f"conversion: {message}" for message in conversion_warnings if message.strip())

    payload, draft_errors = order_conversion.finalize_payload(draft)
    if payload is not None:
        _assert_email_access(current_party_email, payload.buyerEmail, payload.sellerEmail)
        issues.extend(_describe_order_completeness_issues(payload))
        return OrderConversionResponse(
            payload=payload,
            valid=len(issues) == 0,
            issues=issues,
            source=source,
        )

    issues.extend(_draft_errors_to_issues(draft_errors))
    return OrderConversionResponse(
        payload=None,
        valid=False,
        issues=issues,
        source=source,
    )


def _format_conversion_issue(path: str, message: str) -> str:
    normalized_path = path.strip()
    normalized_message = message.strip()
    if not normalized_path:
        return normalized_message
    return f"{normalized_path}: {normalized_message}"


def _assert_order_access(current_party_email: str, payload: dict[str, Any]) -> None:
    buyer_email = payload.get("buyerEmail")
    seller_email = payload.get("sellerEmail")
    if not isinstance(buyer_email, str) or not isinstance(seller_email, str):
        raise HTTPException(status_code=500, detail="Order participant email information missing.")

    _assert_email_access(current_party_email, buyer_email, seller_email)


def _assert_email_access(current_party_email: str, buyer_email: str, seller_email: str) -> None:
    normalized_current = current_party_email.strip().lower()
    normalized_buyer = buyer_email.strip().lower()
    normalized_seller = seller_email.strip().lower()
    if normalized_current not in {normalized_buyer, normalized_seller}:
        raise HTTPException(
            status_code=403,
            detail=(
                "Forbidden: your registered email does not match this order's buyerEmail "
                "or sellerEmail."
            ),
        )


def _draft_errors_to_issues(errors: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    for error in errors:
        location = error.get("loc", ())
        path = ".".join(str(part) for part in location) if location else "payload"
        issues.append(_format_conversion_issue(path, error.get("msg", "Invalid payload.")))
    return issues


def _validate_buyer_seller(order: OrderRequest, issues: list[dict[str, str]]) -> None:
    if not order.buyerEmail:
        issues.append({"path": "buyerEmail", "issue": "buyerEmail is required"})
    if not order.buyerName:
        issues.append({"path": "buyerName", "issue": "buyerName is required"})
    if not order.sellerEmail:
        issues.append({"path": "sellerEmail", "issue": "sellerEmail is required"})
    if not order.sellerName:
        issues.append({"path": "sellerName", "issue": "sellerName is required"})


def _validate_lines(order: OrderRequest, issues: list[dict[str, str]]) -> None:
    for i, line in enumerate(order.lines):
        if not line.productName:
            issues.append({"path": f"lines[{i}].productName", "issue": "productName is required"})


def _validate_order(order: OrderRequest) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    _validate_buyer_seller(order, issues)
    _validate_lines(order, issues)
    return issues


def _describe_order_completeness_issues(order: OrderRequest) -> list[str]:
    issues: list[str] = []
    for line_index, line in enumerate(order.lines):
        if line.unitPrice is None:
            issues.append(
                _format_conversion_issue(
                    f"lines[{line_index}].unitPrice",
                    "unitPrice is recommended before create or update.",
                )
            )
        if line.unitCode is None:
            issues.append(
                _format_conversion_issue(
                    f"lines[{line_index}].unitCode",
                    "unitCode is recommended before create or update.",
                )
            )

    if order.delivery is None:
        issues.append(
            _format_conversion_issue(
                "delivery",
                "delivery is recommended before create or update.",
            )
        )
    else:
        for field in ("street", "city", "country", "postcode", "state", "requestedDate"):
            if not getattr(order.delivery, field):
                issues.append(
                    _format_conversion_issue(
                        f"delivery.{field}",
                        f"delivery.{field} is recommended before create or update.",
                    )
                )

    if order.currency is None:
        issues.append(
            _format_conversion_issue("currency", "currency is recommended before create or update.")
        )
    if order.issueDate is None:
        issues.append(
            _format_conversion_issue(
                "issueDate",
                "issueDate is recommended before create or update.",
            )
        )
    return issues


@router.get(
    "/v1/analytics/orders",
    response_model=AnalyticsResponse,
    status_code=200,
    summary="Get order analytics (Bearer app key required)",
    description=(
        "Return buyer, seller, or combined buyer-and-seller analytics for the authenticated "
        "party across the requested date range."
    ),
    responses={
        200: {
            "description": "Analytics for the authenticated party over the requested date range.",
            "content": {
                "application/json": {
                    "examples": {
                        "seller": {
                            "summary": "Seller analytics",
                            "value": {
                                "role": "seller",
                                "analytics": {
                                    "totalOrders": 1,
                                    "totalIncome": 12.75,
                                    "itemsSold": 3,
                                    "averageItemSoldPrice": 4.25,
                                    "averageOrderAmount": 12.75,
                                    "averageOrderItemNumber": 3.0,
                                    "averageDailyIncome": 4.25,
                                    "averageDailyOrders": 0.33,
                                    "ordersPending": 0,
                                    "ordersCompleted": 0,
                                    "ordersCancelled": 0,
                                    "mostSuccessfulDay": "2026-03-14",
                                    "mostSalesMade": 1,
                                    "mostPopularProductCode": "EA",
                                    "mostPopularProductName": "Oranges",
                                    "mostPopularProductSales": 3,
                                },
                            },
                        },
                        "buyer": {
                            "summary": "Buyer analytics",
                            "value": {
                                "role": "buyer",
                                "analytics": {
                                    "totalOrders": 1,
                                    "totalSpent": 15.0,
                                    "itemsBought": 2,
                                    "averageItemPrice": 7.5,
                                    "averageOrderAmount": 15.0,
                                    "averageItemsPerOrder": 2.0,
                                    "averageDailySpend": 5.0,
                                    "averageDailyOrders": 0.33,
                                },
                            },
                        },
                        "buyerAndSeller": {
                            "summary": "Combined buyer and seller analytics",
                            "value": {
                                "role": "buyer_and_seller",
                                "sellerAnalytics": {
                                    "totalOrders": 1,
                                    "totalIncome": 20.0,
                                    "itemsSold": 4,
                                    "averageItemSoldPrice": 5.0,
                                    "averageOrderAmount": 20.0,
                                    "averageOrderItemNumber": 4.0,
                                    "averageDailyIncome": 6.67,
                                    "averageDailyOrders": 0.33,
                                    "ordersPending": 0,
                                    "ordersCompleted": 0,
                                    "ordersCancelled": 0,
                                    "mostSuccessfulDay": "2026-03-14",
                                    "mostSalesMade": 1,
                                    "mostPopularProductCode": "EA",
                                    "mostPopularProductName": "Oranges",
                                    "mostPopularProductSales": 4,
                                },
                                "buyerAnalytics": {
                                    "totalOrders": 1,
                                    "totalSpent": 9.5,
                                    "itemsBought": 1,
                                    "averageItemPrice": 9.5,
                                    "averageOrderAmount": 9.5,
                                    "averageItemsPerOrder": 1.0,
                                    "averageDailySpend": 3.17,
                                    "averageDailyOrders": 0.33,
                                },
                                "netProfit": 10.5,
                            },
                        },
                        "noOrders": {
                            "summary": "No orders in date range",
                            "value": {"message": "No orders found"},
                        },
                    }
                }
            },
        },
        400: {
            "description": "The analytics date range is invalid.",
            "content": {
                "application/json": {
                    "examples": {
                        "invertedRange": {
                            "value": {"detail": "fromDate must be on or before toDate."}
                        },
                    }
                }
            },
        },
        401: UNAUTHORIZED_RESPONSE,
        500: {
            "description": "Analytics generation failed.",
            "content": {
                "application/json": {"example": {"detail": "Unable to generate analytics."}}
            },
        },
    },
)
def get_order_analytics(
    fromDate: datetime = ANALYTICS_FROM_DATE_QUERY,
    toDate: datetime = ANALYTICS_TO_DATE_QUERY,
    current_party_email: str = Depends(get_current_party_email),
):
    if current_party_email is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if fromDate > toDate:
        raise HTTPException(status_code=400, detail="fromDate must be on or before toDate.")

    try:
        analytics = get_user_analytics(
            username=current_party_email,
            fromDate=fromDate,
            toDate=toDate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Analytics generation failed")
        raise HTTPException(status_code=500, detail="Unable to generate analytics.") from exc

    return analytics
